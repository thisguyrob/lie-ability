from __future__ import annotations
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

PHASE_TIMEOUTS: dict[str, int] = {
    "category_pick": 15,
    "lie_submission": 30,
    "voting": 30,
    "likes": 30,
    "round_results": 10,
    "appeal_vote": 15,
}


def set_phase_deadline(game, phase: str) -> None:
    seconds = PHASE_TIMEOUTS.get(phase, 0)
    if seconds > 0:
        game.phase_deadline = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    else:
        game.phase_deadline = None


def start_phase_timer(game, advance_fn: Callable[[], None]) -> None:
    token = game.phase_token
    seconds = PHASE_TIMEOUTS.get(game.phase, 0)
    if seconds <= 0:
        return

    def _body():
        time.sleep(seconds)
        # advance_fn acquires game_state_lock internally; don't hold it here
        if game.phase_token != token:
            return
        advance_fn()

    threading.Thread(target=_body, daemon=True).start()


def start_tick_loop(socketio) -> None:
    def _tick():
        while True:
            time.sleep(1)
            from server.game import get_game
            game = get_game()
            if game.phase_deadline:
                remaining = (game.phase_deadline - datetime.now(timezone.utc)).total_seconds()
                socketio.emit("timer_tick", {"seconds_remaining": max(0, int(remaining))})

    threading.Thread(target=_tick, daemon=True).start()
