"""
Shared pytest fixtures for all tests.

Setup required (once):
    pip install pytest pytest-playwright
    playwright install chromium
"""
from __future__ import annotations

import time
import threading
from unittest.mock import patch

import pytest
import requests as _req

import server.game as game_module
import server.timers as timers_module

# One question per round so the full game completes in a single turn.
SINGLE_ROUND_CONFIG = [
    {"round_number": 1, "score_multiplier": 1, "questions_in_round": 1},
]

# Phase timeouts long enough for Playwright assertions but short enough to keep
# timer-driven transitions (round_results) from stalling the test suite.
UI_TIMEOUTS = {k: 2.0 for k in [
    "category_pick", "lie_submission", "voting", "likes", "round_results", "appeal_vote",
]}

BASE_URL = "http://localhost:6767"


@pytest.fixture(scope="session")
def live_server():
    """Start a real Flask+SocketIO server that Playwright (and requests) can reach."""
    from server import create_app, socketio

    app = create_app()
    app.config["TESTING"] = True

    patches = [
        patch.object(game_module, "ROUND_CONFIG", SINGLE_ROUND_CONFIG),
        patch.object(timers_module, "PHASE_TIMEOUTS", UI_TIMEOUTS),
    ]
    for p in patches:
        p.start()

    def _run():
        socketio.run(app, port=6767, use_reloader=False, log_output=False, allow_unsafe_werkzeug=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            _req.get(f"{BASE_URL}/api/game/state", timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("live_server did not start within 8 seconds")

    yield BASE_URL

    for p in patches:
        p.stop()


@pytest.fixture(scope="session")
def browser(playwright):
    """Session-scoped Chromium browser shared across all test files."""
    b = playwright.chromium.launch()
    yield b
    b.close()


@pytest.fixture(autouse=True)
def reset_game_state(live_server):
    """Reset to lobby before and after every test."""
    _req.post(f"{live_server}/api/game/reset")
    yield
    _req.post(f"{live_server}/api/game/reset")
