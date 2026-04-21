"""
Integration test: play a complete game from player join through game_over via the REST API.

Run with:  pytest tests/test_game_flow.py -v
Requires:  pip install pytest
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import server.game as game_module
import server.routes as routes_module
import server.timers as timers_module

# One question per round so the test completes in ~3 turns instead of 17.
FAST_ROUND_CONFIG = [
    {"round_number": 1, "score_multiplier": 1, "questions_in_round": 1},
    {"round_number": 2, "score_multiplier": 2, "questions_in_round": 1},
    {"round_number": 3, "score_multiplier": 3, "questions_in_round": 1},
]

# Short timeouts so timer-driven transitions fire in < 200 ms.
FAST_TIMEOUTS = {k: 0.15 for k in [
    "category_pick", "lie_submission", "voting", "likes", "round_results", "appeal_vote",
]}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    from server import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    game_module.reset_game()
    with app.test_client() as c:
        yield c
    game_module.reset_game()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_state(client) -> dict:
    return client.get("/api/game/state").get_json()


def api_post(client, path: str, data: dict):
    return client.post(path, json=data)


def wait_for(client, *phases: str, timeout: float = 2.0) -> dict:
    """Poll game state until one of the expected phases is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = get_state(client)
        if s["phase"] in phases:
            return s
        time.sleep(0.02)
    s = get_state(client)
    raise AssertionError(
        f"Timed out waiting for {phases!r}; current phase: {s['phase']!r}"
    )


def cast_vote(client, player_id: str) -> None:
    """Vote for the first answer the player is allowed to choose."""
    answers = get_state(client)["current_turn"]["answers"]
    for a in answers:
        r = api_post(client, "/api/game/vote", {
            "player_id": player_id,
            "answer_id": a["answer_id"],
        })
        if r.status_code == 200:
            return
    raise AssertionError(f"Player {player_id!r} could not find a valid answer to vote for")


def cast_like(client, player_id: str) -> None:
    """Like the first answer the player is allowed to react to (skips own answer)."""
    answers = get_state(client)["current_turn"]["answers"]
    for a in answers:
        r = api_post(client, "/api/game/like", {
            "player_id": player_id,
            "answer_id": a["answer_id"],
        })
        if r.status_code == 200:
            return
    # No likeable answer — acceptable edge case, timer will advance the phase.


def play_turn(client, player_ids: list[str]) -> dict:
    """
    Drive one complete turn starting from category_pick.
    Returns the game state after the round_results timer has fired
    (i.e. the state is category_pick for the next turn or game_over).
    """
    s = wait_for(client, "category_pick")

    # --- Category pick (done by the active/picker player) ---
    picker_id = s["active_player_id"]
    categories = client.get("/api/categories").get_json()
    assert categories, "No categories available in DB"

    r = api_post(client, "/api/game/category", {
        "player_id": picker_id,
        "category_id": categories[0]["id"],
    })
    assert r.status_code == 200, f"category pick failed: {r.get_json()}"

    # --- Lie submission ---
    wait_for(client, "lie_submission")
    for i, pid in enumerate(player_ids):
        r = api_post(client, "/api/game/lie", {
            "player_id": pid,
            "text": f"Totally plausible answer number {i} by {pid[:6]}",
        })
        assert r.status_code == 200, f"lie submission failed for player {i}: {r.get_json()}"

    # --- Voting ---
    wait_for(client, "voting")
    for pid in player_ids:
        cast_vote(client, pid)

    # --- Likes ---
    wait_for(client, "likes")
    for pid in player_ids:
        cast_like(client, pid)

    # After the last like, the game enters round_results.
    # Wait for the round_results timer to fire and advance to the next phase.
    return wait_for(client, "category_pick", "game_over")


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_full_game(client):
    """Three players join and play all 3 rounds (1 question each) to game_over."""
    with (
        patch.object(game_module, "ROUND_CONFIG", FAST_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", FAST_TIMEOUTS),
    ):
        # --- Lobby: players join ---
        player_ids = []
        for name in ["Alice", "Bob", "Carol"]:
            r = api_post(client, "/api/players", {
                "name": name,
                "avatar_emoji": "🎭",
                "avatar_bg_color": "#336699",
            })
            assert r.status_code == 200, r.get_json()
            player_ids.append(r.get_json()["player_id"])

        s = get_state(client)
        assert s["phase"] == "lobby"
        assert len(s["players"]) == 3

        # --- Start game ---
        r = api_post(client, "/api/game/start", {})
        assert r.status_code == 200, r.get_json()

        s = get_state(client)
        assert s["phase"] == "category_pick"

        # --- Play all 3 rounds ---
        for round_num in range(1, 4):
            s = play_turn(client, player_ids)
            assert s["phase"] in ("category_pick", "game_over"), (
                f"Unexpected phase after round {round_num}: {s['phase']!r}"
            )
            if s["phase"] == "game_over":
                assert round_num == 3, f"Game ended at round {round_num}, expected round 3"
                break
        else:
            pytest.fail("Game did not reach game_over after 3 rounds")

        # --- Verify final state ---
        s = get_state(client)
        assert s["phase"] == "game_over"
        assert "final_scores" in s, "final_scores missing from game_over state"

        final = s["final_scores"]
        assert len(final) == 3, f"Expected 3 players in final_scores, got {len(final)}"

        names = {p["name"] for p in final}
        assert names == {"Alice", "Bob", "Carol"}

        # Scores must be non-negative and sorted descending
        scores = [p["score"] for p in final]
        assert all(sc >= 0 for sc in scores), f"Negative score found: {scores}"
        assert scores == sorted(scores, reverse=True), f"final_scores not sorted: {scores}"


def test_player_cannot_like_own_lie(client):
    """Likes payload identifies authors and the API rejects self-likes."""
    with (
        patch.object(game_module, "ROUND_CONFIG", FAST_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", FAST_TIMEOUTS),
    ):
        player_ids = []
        for name in ["Alice", "Bob"]:
            r = api_post(client, "/api/players", {
                "name": name,
                "avatar_emoji": "🎭",
                "avatar_bg_color": "#336699",
            })
            assert r.status_code == 200, r.get_json()
            player_ids.append(r.get_json()["player_id"])

        alice_id, bob_id = player_ids

        r = api_post(client, "/api/game/start", {})
        assert r.status_code == 200, r.get_json()

        s = wait_for(client, "category_pick")
        categories = client.get("/api/categories").get_json()
        assert categories, "No categories available in DB"
        r = api_post(client, "/api/game/category", {
            "player_id": s["active_player_id"],
            "category_id": categories[0]["id"],
        })
        assert r.status_code == 200, f"category pick failed: {r.get_json()}"

        wait_for(client, "lie_submission")
        assert api_post(client, "/api/game/lie", {
            "player_id": alice_id,
            "text": "Alice lie",
        }).status_code == 200
        assert api_post(client, "/api/game/lie", {
            "player_id": bob_id,
            "text": "Bob lie",
        }).status_code == 200

        wait_for(client, "voting")
        for pid in player_ids:
            cast_vote(client, pid)

        s = wait_for(client, "likes")
        alice_answer = next(a for a in s["current_turn"]["answers"] if a.get("author_id") == alice_id)

        r = api_post(client, "/api/game/like", {
            "player_id": alice_id,
            "answer_id": alice_answer["answer_id"],
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "You cannot like your own answer"


def test_last_lie_submission_stops_clock_before_advancing(client):
    with (
        patch.object(game_module, "ROUND_CONFIG", FAST_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", FAST_TIMEOUTS),
        patch.object(routes_module.socketio, "emit") as emit_mock,
    ):
        player_ids = []
        for name in ["Alice", "Bob"]:
            r = api_post(client, "/api/players", {
                "name": name,
                "avatar_emoji": "🎭",
                "avatar_bg_color": "#336699",
            })
            assert r.status_code == 200, r.get_json()
            player_ids.append(r.get_json()["player_id"])

        r = api_post(client, "/api/game/start", {})
        assert r.status_code == 200, r.get_json()

        s = wait_for(client, "category_pick")
        categories = client.get("/api/categories").get_json()
        assert categories, "No categories available in DB"
        r = api_post(client, "/api/game/category", {
            "player_id": s["active_player_id"],
            "category_id": categories[0]["id"],
        })
        assert r.status_code == 200, f"category pick failed: {r.get_json()}"

        wait_for(client, "lie_submission")
        assert api_post(client, "/api/game/lie", {
            "player_id": player_ids[0],
            "text": "Alice lie",
        }).status_code == 200

        emit_mock.reset_mock()

        r = api_post(client, "/api/game/lie", {
            "player_id": player_ids[1],
            "text": "Bob lie",
        })
        assert r.status_code == 200, r.get_json()

        s = wait_for(client, "voting")
        assert s["phase"] == "voting"

        emitted_events = [call.args[0] for call in emit_mock.call_args_list]
        assert "timer_stop" in emitted_events
        assert "phase_change" in emitted_events

        timer_stop_index = emitted_events.index("timer_stop")
        phase_change_index = emitted_events.index("phase_change")
        assert timer_stop_index < phase_change_index

        timer_stop_payload = emit_mock.call_args_list[timer_stop_index].args[1]
        phase_change_payload = emit_mock.call_args_list[phase_change_index].args[1]
        assert timer_stop_payload == {"phase": "lie_submission"}
        assert phase_change_payload["phase"] == "voting"


def test_player_can_like_during_voting_after_voting(client):
    with (
        patch.object(game_module, "ROUND_CONFIG", FAST_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", FAST_TIMEOUTS),
    ):
        player_ids = []
        for name in ["Alice", "Bob"]:
            r = api_post(client, "/api/players", {
                "name": name,
                "avatar_emoji": "🎭",
                "avatar_bg_color": "#336699",
            })
            assert r.status_code == 200, r.get_json()
            player_ids.append(r.get_json()["player_id"])

        alice_id, bob_id = player_ids

        r = api_post(client, "/api/game/start", {})
        assert r.status_code == 200, r.get_json()

        s = wait_for(client, "category_pick")
        categories = client.get("/api/categories").get_json()
        assert categories, "No categories available in DB"
        r = api_post(client, "/api/game/category", {
            "player_id": s["active_player_id"],
            "category_id": categories[0]["id"],
        })
        assert r.status_code == 200, f"category pick failed: {r.get_json()}"

        wait_for(client, "lie_submission")
        assert api_post(client, "/api/game/lie", {
            "player_id": alice_id,
            "text": "Alice lie",
        }).status_code == 200
        assert api_post(client, "/api/game/lie", {
            "player_id": bob_id,
            "text": "Bob lie",
        }).status_code == 200

        s = wait_for(client, "voting")
        like_answer_id = next(
            a["answer_id"] for a in s["current_turn"]["answers"]
            if a.get("author_id") != alice_id
        )

        r = api_post(client, "/api/game/like", {
            "player_id": alice_id,
            "answer_id": like_answer_id,
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "You must vote before liking an answer"

        cast_vote(client, alice_id)
        s = get_state(client)
        assert s["phase"] == "voting"

        r = api_post(client, "/api/game/like", {
            "player_id": alice_id,
            "answer_id": like_answer_id,
        })
        assert r.status_code == 200, r.get_json()

        s = get_state(client)
        assert s["phase"] == "voting"
        assert game_module.get_game().players[alice_id].has_liked is True


def test_player_can_like_the_truth(client):
    with (
        patch.object(game_module, "ROUND_CONFIG", FAST_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", FAST_TIMEOUTS),
    ):
        player_ids = []
        for name in ["Alice", "Bob"]:
            r = api_post(client, "/api/players", {
                "name": name,
                "avatar_emoji": "🎭",
                "avatar_bg_color": "#336699",
            })
            assert r.status_code == 200, r.get_json()
            player_ids.append(r.get_json()["player_id"])

        alice_id, bob_id = player_ids

        r = api_post(client, "/api/game/start", {})
        assert r.status_code == 200, r.get_json()

        s = wait_for(client, "category_pick")
        categories = client.get("/api/categories").get_json()
        assert categories, "No categories available in DB"
        r = api_post(client, "/api/game/category", {
            "player_id": s["active_player_id"],
            "category_id": categories[0]["id"],
        })
        assert r.status_code == 200, f"category pick failed: {r.get_json()}"

        wait_for(client, "lie_submission")
        assert api_post(client, "/api/game/lie", {
            "player_id": alice_id,
            "text": "Alice lie",
        }).status_code == 200
        assert api_post(client, "/api/game/lie", {
            "player_id": bob_id,
            "text": "Bob lie",
        }).status_code == 200

        s = wait_for(client, "voting")
        truth_answer_id = next(
            a["answer_id"] for a in s["current_turn"]["answers"]
            if a.get("author_id") is None
        )

        cast_vote(client, alice_id)

        r = api_post(client, "/api/game/like", {
            "player_id": alice_id,
            "answer_id": truth_answer_id,
        })
        assert r.status_code == 200, r.get_json()

        truth = next(
            a for a in game_module.get_game().current_round.current_turn.answers
            if a.answer_id == truth_answer_id
        )
        assert truth.is_real is True
        assert truth.likes == 1


def test_voting_answers_include_normalized_text(client):
    with (
        patch.object(game_module, "ROUND_CONFIG", FAST_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", FAST_TIMEOUTS),
    ):
        player_ids = []
        for name in ["Alice", "Bob"]:
            r = api_post(client, "/api/players", {
                "name": name,
                "avatar_emoji": "🎭",
                "avatar_bg_color": "#336699",
            })
            assert r.status_code == 200, r.get_json()
            player_ids.append(r.get_json()["player_id"])

        alice_id, bob_id = player_ids

        r = api_post(client, "/api/game/start", {})
        assert r.status_code == 200, r.get_json()

        s = wait_for(client, "category_pick")
        categories = client.get("/api/categories").get_json()
        assert categories, "No categories available in DB"
        r = api_post(client, "/api/game/category", {
            "player_id": s["active_player_id"],
            "category_id": categories[0]["id"],
        })
        assert r.status_code == 200, f"category pick failed: {r.get_json()}"

        wait_for(client, "lie_submission")
        assert api_post(client, "/api/game/lie", {
            "player_id": alice_id,
            "text": "twenty-four",
        }).status_code == 200
        assert api_post(client, "/api/game/lie", {
            "player_id": bob_id,
            "text": "Bob lie",
        }).status_code == 200

        s = wait_for(client, "voting")
        normalized_answer = next(
            a for a in s["current_turn"]["answers"]
            if a["text"] == "twenty-four"
        )
        assert normalized_answer["normalized_text"] == "24"
