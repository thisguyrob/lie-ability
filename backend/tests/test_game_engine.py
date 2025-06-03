import asyncio

import pytest

from backend import lobbies
from backend.game import engine


@pytest.mark.asyncio
async def test_game_reaches_game_over(monkeypatch) -> None:
    monkeypatch.setattr(engine, "LIE_TIMER", 0)
    monkeypatch.setattr(engine, "VOTE_TIMER", 0)
    monkeypatch.setattr(engine, "SCOREBOARD_TIMER", 0)
    lobby, _ = lobbies.create_lobby(1)
    lobbies.add_player(lobby.code, "A", "🐍")
    lobbies.add_player(lobby.code, "B", "🐍")
    events: list[dict] = []

    async def handler(msg: dict) -> None:
        events.append(msg)

    engine.register_broadcaster(lobby.code, handler)
    engine.start_game(lobby)
    await asyncio.sleep(0.05)
    assert any(e["type"] == "game_over" for e in events)
