"""
Full-game frontend test for the main display (/main/).

Drives a complete game through every phase via the REST API and asserts
that the browser renders the correct scene at each step.

All assertions are unconditional: the suite stays red until every scene
template is implemented in templates/main/index.html.

Run with:
    pytest tests/test_main_display.py -v
"""
from __future__ import annotations

import re
import time

import pytest
import requests
from playwright.sync_api import Page, expect

BASE = "http://localhost:6767"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def api(method: str, path: str, **kwargs) -> requests.Response:
    return requests.request(method, f"{BASE}{path}", **kwargs)


def add_player(name: str) -> str:
    r = api("POST", "/api/players", json={
        "name": name,
        "avatar_emoji": "🎭",
        "avatar_bg_color": "#336699",
    })
    assert r.status_code == 200, r.json()
    return r.json()["player_id"]


def get_state() -> dict:
    return api("GET", "/api/game/state").json()


def wait_for_phase_api(*phases: str, timeout: float = 8.0) -> dict:
    """Poll the API until one of *phases* is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = get_state()
        if s["phase"] in phases:
            return s
        time.sleep(0.05)
    raise AssertionError(
        f"API timed out waiting for {phases!r}; current phase: {get_state()['phase']!r}"
    )


def wait_for_phase_ui(page: Page, phase: str, timeout: int = 6_000) -> None:
    """Block until the browser's #scene-<phase> carries the 'active' class.

    Times out (and fails the test) if the element never appears — this is the
    primary mechanism that catches missing scene templates.
    """
    page.wait_for_function(
        f"document.getElementById('scene-{phase}')?.classList.contains('active')",
        timeout=timeout,
    )


def cast_vote(player_id: str) -> None:
    answers = get_state()["current_turn"]["answers"]
    for a in answers:
        r = api("POST", "/api/game/vote", json={"player_id": player_id, "answer_id": a["answer_id"]})
        if r.status_code == 200:
            return
    raise AssertionError(f"No valid answer to vote on for player {player_id!r}")


def cast_like(player_id: str) -> None:
    answers = get_state()["current_turn"]["answers"]
    for a in answers:
        r = api("POST", "/api/game/like", json={"player_id": player_id, "answer_id": a["answer_id"]})
        if r.status_code == 200:
            return


def setup_two_players() -> tuple[str, str]:
    """Join Alice and Bob and return their player IDs."""
    alice = add_player("Alice")
    bob = add_player("Bob")
    return alice, bob


def drive_to_voting(alice: str, bob: str) -> None:
    """Drive the game from lobby through category pick and lie submission."""
    api("POST", "/api/game/start", json={})
    s = wait_for_phase_api("category_pick")

    picker = s["active_player_id"]
    cats = api("GET", "/api/categories").json()
    assert cats, "No categories in database"
    r = api("POST", "/api/game/category", json={"player_id": picker, "category_id": cats[0]["id"]})
    assert r.status_code == 200, r.json()

    wait_for_phase_api("lie_submission")
    for i, pid in enumerate([alice, bob]):
        r = api("POST", "/api/game/lie", json={"player_id": pid, "text": f"Plausible lie {i} from {pid[:4]}"})
        assert r.status_code == 200, r.json()


def drive_to_likes(alice: str, bob: str) -> None:
    drive_to_voting(alice, bob)
    wait_for_phase_api("voting")
    cast_vote(alice)
    cast_vote(bob)


def drive_to_round_results(alice: str, bob: str) -> None:
    drive_to_likes(alice, bob)
    wait_for_phase_api("likes")
    cast_like(alice)
    cast_like(bob)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def page(live_server, browser):
    """Open a fresh browser page pointed at the main display."""
    context = browser.new_context()
    p = context.new_page()
    p.goto(f"{live_server}/main/")
    yield p
    context.close()


# ------------------------------------------------------------------
# Tests — Lobby
# ------------------------------------------------------------------

def test_lobby_initial_render(page: Page) -> None:
    """Lobby scene is active on first load with no players."""
    expect(page.locator("#scene-lobby")).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator(".logo")).to_contain_text("Lie-Ability")
    expect(page.locator("#player-count")).to_have_text("0")
    expect(page.locator("#qr-canvas img")).to_be_visible()
    expect(page.locator("#qr-url-label")).to_contain_text("6767")
    expect(page.locator(".no-players")).to_be_visible()


def test_lobby_players_update(page: Page) -> None:
    """Player list and count update in real time as players join."""
    add_player("Alice")
    expect(page.locator("#player-count")).to_have_text("1")
    expect(page.locator(".player-name", has_text="Alice")).to_be_visible()
    expect(page.locator(".no-players")).not_to_be_visible()

    add_player("Bob")
    expect(page.locator("#player-count")).to_have_text("2")
    expect(page.locator(".player-card")).to_have_count(2)
    expect(page.locator(".player-name", has_text="Bob")).to_be_visible()

    # Avatar background colour is set via inline style
    avatar = page.locator(".player-card").first.locator(".avatar")
    expect(avatar).to_have_attribute("style", re.compile(r"background.*#336699", re.IGNORECASE))


# ------------------------------------------------------------------
# Tests — In-game phases
# ------------------------------------------------------------------

def test_phase_category_pick(page: Page) -> None:
    """Lobby is hidden; category-pick scene is active after game start."""
    alice, bob = setup_two_players()
    api("POST", "/api/game/start", json={})

    wait_for_phase_ui(page, "category_pick")

    expect(page.locator("#scene-lobby")).not_to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator("#scene-category_pick")).to_have_class(re.compile(r"\bactive\b"))

    s = get_state()
    active_name = next(
        p["name"] for p in s["players"] if p["player_id"] == s["active_player_id"]
    )
    expect(page.locator("#scene-category_pick")).to_contain_text(active_name)


def test_phase_lie_submission(page: Page) -> None:
    """Lie-submission scene shows the question prompt and a submission counter."""
    alice, bob = setup_two_players()
    api("POST", "/api/game/start", json={})

    s = wait_for_phase_api("category_pick")
    cats = api("GET", "/api/categories").json()
    api("POST", "/api/game/category", json={"player_id": s["active_player_id"], "category_id": cats[0]["id"]})

    wait_for_phase_ui(page, "lie_submission")

    scene = page.locator("#scene-lie_submission")
    expect(scene).to_have_class(re.compile(r"\bactive\b"))

    s = get_state()
    prompt = s["current_turn"]["question_prompt"]
    expect(scene).to_contain_text(prompt)

    # Submission counter must show 0 out of 2 at this point
    expect(scene).to_contain_text(re.compile(r"0\s*/\s*2|0 of 2", re.IGNORECASE))


def test_phase_voting(page: Page) -> None:
    """Voting scene shows exactly 3 shuffled answer options."""
    alice, bob = setup_two_players()
    drive_to_voting(alice, bob)

    wait_for_phase_ui(page, "voting")

    scene = page.locator("#scene-voting")
    expect(scene).to_have_class(re.compile(r"\bactive\b"))

    # Real answer + 2 player lies = 3 options (game pads with bot fills if needed)
    answer_items = scene.locator("[data-answer-id]")
    expect(answer_items).to_have_count(3)


def test_phase_likes(page: Page) -> None:
    """Likes scene shows answers with their vote counts."""
    alice, bob = setup_two_players()
    drive_to_likes(alice, bob)

    wait_for_phase_ui(page, "likes")

    scene = page.locator("#scene-likes")
    expect(scene).to_have_class(re.compile(r"\bactive\b"))

    # Every answer should display how many votes it received
    vote_counts = scene.locator("[data-vote-count]")
    expect(vote_counts).to_have_count(3)


def test_phase_round_results(page: Page) -> None:
    """Round-results scene reveals the real answer and shows score deltas."""
    alice, bob = setup_two_players()
    drive_to_round_results(alice, bob)

    wait_for_phase_ui(page, "round_results")

    scene = page.locator("#scene-round_results")
    expect(scene).to_have_class(re.compile(r"\bactive\b"))

    s = get_state()
    real_answer = s["current_turn"]["real_answer_text"]
    expect(scene).to_contain_text(real_answer)

    # At least one score change should be rendered (could be 0 pts but element present)
    expect(scene.locator("[data-score-change]")).not_to_have_count(0)


def test_phase_game_over(page: Page) -> None:
    """Game-over scene is active after the round completes; lobby is hidden."""
    alice, bob = setup_two_players()
    drive_to_round_results(alice, bob)

    # round_results auto-advances to game_over after the UI_TIMEOUTS["round_results"] (2 s)
    wait_for_phase_api("game_over", timeout=10.0)
    wait_for_phase_ui(page, "game_over", timeout=8_000)

    expect(page.locator("#scene-lobby")).not_to_have_class(re.compile(r"\bactive\b"))

    scene = page.locator("#scene-game_over")
    expect(scene).to_have_class(re.compile(r"\bactive\b"))

    # Both player names must appear in the final scores
    expect(scene).to_contain_text("Alice")
    expect(scene).to_contain_text("Bob")

    # Scores are non-negative integers
    s = get_state()
    assert all(p["score"] >= 0 for p in s["final_scores"])
