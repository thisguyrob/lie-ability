from app import can_start_game, count_joined_players, format_countdown_text


def test_count_joined_players_only_counts_connected_players():
    state = {
        "players": [
            {"player_id": "a", "connected": True},
            {"player_id": "b", "connected": False},
            {"player_id": "c", "connected": True},
        ]
    }

    assert count_joined_players(state) == 2


def test_can_start_game_requires_lobby_phase_and_two_connected_players():
    assert not can_start_game({"phase": "lobby", "players": [{"connected": True}]})
    assert not can_start_game({"phase": "voting", "players": [{"connected": True}, {"connected": True}]})
    assert can_start_game({"phase": "lobby", "players": [{"connected": True}, {"connected": True}]})


def test_format_countdown_text_uses_phase_deadline():
    state = {"phase": "category_pick", "phase_deadline_ts": 130.0}

    assert format_countdown_text(state, now_ts=100.0) == "Category pick timer: 00:30"


def test_format_countdown_text_clamps_elapsed_timer_to_zero():
    state = {"phase": "lie_submission", "phase_deadline_ts": 95.0}

    assert format_countdown_text(state, now_ts=100.0) == "Lie submission timer: 00:00"


def test_format_countdown_text_hides_missing_deadline():
    assert format_countdown_text({"phase": "lobby"}, now_ts=100.0) == "Current timer: --"
