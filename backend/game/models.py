from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


Phase = Literal[
    "LOBBY",
    "LIE_SUBMISSION",
    "VOTING",
    "REVEAL",
    "SCOREBOARD",
    "GAME_OVER",
]


class Choice(BaseModel):
    """Selectable option shown during voting."""

    id: str
    text: str
    author_id: str | None


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
