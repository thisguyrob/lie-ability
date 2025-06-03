from __future__ import annotations

import asyncio
import os
import time
from typing import Dict, List

from .models import Lobby, Phase
from .state import (
    AUTO_LIE_PENALTY,
    FOOL_POINTS,
    GameState,
    TRUTH_POINTS,
    compute_multiplier,
    get_prompt,
    make_choice,
)

# Timers (seconds)
PROMPT_DELAY = int(os.getenv("PROMPT_DELAY", 1))
LIE_TIMER = int(os.getenv("LIE_TIMER", 30))
VOTE_TIMER = int(os.getenv("VOTE_TIMER", 20))
SCOREBOARD_TIMER = int(os.getenv("SCOREBOARD_TIMER", 8))

_games: Dict[str, GameState] = {}
_broadcast_handlers: Dict[str, List] = {}


def register_broadcaster(code: str, handler) -> None:
    """Subscribe to broadcast events for a lobby."""
    _broadcast_handlers.setdefault(code, []).append(handler)


def unregister_broadcaster(code: str, handler) -> None:
    """Remove broadcast subscriber."""
    if code in _broadcast_handlers:
        _broadcast_handlers[code].remove(handler)
        if not _broadcast_handlers[code]:
            del _broadcast_handlers[code]


async def broadcast(code: str, msg: dict) -> None:
    """Send JSON message to all subscribers."""
    handlers = list(_broadcast_handlers.get(code, []))
    for handler in handlers:
        await handler(msg)


# ------------------ Game actions ------------------


def start_game(lobby: Lobby) -> GameState:
    """Create a game instance for the given lobby and launch the loop."""
    game = GameState(lobby=lobby, round_count=lobby.round_count)
    _games[lobby.code] = game
    asyncio.create_task(_run_game(game))
    return game


def get_game(code: str) -> GameState | None:
    """Return the active GameState for a lobby, if any."""
    return _games.get(code)


async def submit_lie(code: str, player_id: str, text: str) -> None:
    """Record a lie from a player during the submission phase."""
    game = _games.get(code)
    if not game or game.phase != "LIE_SUBMISSION":
        return
    game.lies[player_id] = text.strip() or "Auto Lie"


async def submit_vote(code: str, player_id: str, choice_id: str) -> None:
    """Record a vote from a player during the voting phase."""
    game = _games.get(code)
    if not game or game.phase != "VOTING":
        return
    if player_id in game.votes:
        return
    choice = next((c for c in game.choices if c.id == choice_id), None)
    if not choice or choice.author_id == player_id:
        return
    game.votes[player_id] = choice_id


# ------------------ Game loop ------------------
async def _run_game(game: GameState) -> None:
    """Main asynchronous loop progressing through all rounds."""
    code = game.lobby.code
    for rnd in range(1, game.round_count + 1):
        game.round_number = rnd
        prompt = get_prompt()
        game.prompt_id = prompt["id"]
        game.prompt_category = prompt["category"]
        game.prompt_text = prompt["text"]
        await broadcast(
            code,
            {
                "type": "prompt",
                "payload": {
                    "id": game.prompt_id,
                    "category": game.prompt_category,
                    "text": game.prompt_text,
                },
                "ts": int(time.time() * 1000),
            },
        )
        await _phase(game, "LIE_SUBMISSION", LIE_TIMER)
        # Build choices
        game.choices = [make_choice(prompt["answer"], None)]
        for pid, text in game.lies.items():
            game.choices.append(make_choice(text, pid))
        await broadcast(
            code,
            {
                "type": "choices",
                "payload": {"list": [c.model_dump() for c in game.choices]},
                "ts": int(time.time() * 1000),
            },
        )
        await _phase(game, "VOTING", VOTE_TIMER)
        await _reveal(game, prompt)
        await _scoreboard(game)
    await _game_over(game)


async def _phase(game: GameState, phase: Phase, duration: int) -> None:
    """Broadcast a phase change and sleep for the given duration."""
    game.phase = phase
    game.deadline = time.time() + duration
    await broadcast(
        game.lobby.code,
        {
            "type": "phase_change",
            "payload": {"phase": phase, "deadline": int(game.deadline * 1000)},
            "ts": int(time.time() * 1000),
        },
    )
    if duration:
        await asyncio.sleep(duration)


async def _reveal(game: GameState, prompt: dict) -> None:
    """Calculate scores and broadcast reveal results."""
    code = game.lobby.code
    game.phase = "REVEAL"
    await broadcast(
        code,
        {
            "type": "phase_change",
            "payload": {"phase": "REVEAL", "deadline": int(time.time() * 1000)},
            "ts": int(time.time() * 1000),
        },
    )
    truth_choice = next(c for c in game.choices if c.author_id is None)
    fooled = []
    delta: Dict[str, int] = {pid: 0 for pid in game.scores}
    multiplier = compute_multiplier(game.round_number)
    for voter, cid in game.votes.items():
        choice = next(c for c in game.choices if c.id == cid)
        if choice.author_id is None:
            delta[voter] += TRUTH_POINTS * multiplier
        elif choice.author_id == "AUTO":
            delta[voter] -= AUTO_LIE_PENALTY * multiplier
        else:
            fooled.append({"victimId": voter, "liarId": choice.author_id})
            delta[choice.author_id] += FOOL_POINTS * multiplier
    for pid, pts in delta.items():
        game.scores[pid] += pts
    await broadcast(
        code,
        {
            "type": "reveal",
            "payload": {
                "truthId": truth_choice.id,
                "fooled": fooled,
                "scoresDelta": delta,
            },
            "ts": int(time.time() * 1000),
        },
    )
    await asyncio.sleep(max(1, len(game.choices) * 2))


async def _scoreboard(game: GameState) -> None:
    """Broadcast cumulative scores for all players."""
    await _phase(game, "SCOREBOARD", SCOREBOARD_TIMER)
    scores = [
        {"playerId": pid, "total": total}
        for pid, total in sorted(game.scores.items(), key=lambda p: -p[1])
    ]
    await broadcast(
        game.lobby.code,
        {
            "type": "scoreboard",
            "payload": {"scores": scores},
            "ts": int(time.time() * 1000),
        },
    )
    if SCOREBOARD_TIMER:
        await asyncio.sleep(SCOREBOARD_TIMER)


async def _game_over(game: GameState) -> None:
    """Finalize the game and broadcast winners."""
    game.phase = "GAME_OVER"
    await broadcast(
        game.lobby.code,
        {
            "type": "phase_change",
            "payload": {"phase": "GAME_OVER", "deadline": int(time.time() * 1000)},
            "ts": int(time.time() * 1000),
        },
    )
    scores = [
        {"playerId": pid, "total": total}
        for pid, total in sorted(game.scores.items(), key=lambda p: -p[1])
    ]
    await broadcast(
        game.lobby.code,
        {
            "type": "game_over",
            "payload": {"final": scores},
            "ts": int(time.time() * 1000),
        },
    )
    _games.pop(game.lobby.code, None)
