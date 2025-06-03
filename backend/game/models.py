from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


class Player(BaseModel):
    """Player state."""

    id: str
    nickname: str
    avatar: str
    score: int = 0
    connected: bool = True


class Lobby(BaseModel):
    """Lobby container for players."""

    code: str
    players: list[Player]
    round_count: int
    state: Literal["LOBBY", "IN_GAME", "GAME_OVER"] = "LOBBY"
