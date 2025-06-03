from __future__ import annotations

import secrets
import string
import uuid
from typing import Dict

from .auth import encode
from .game.models import Lobby, Player
from .game import engine

_lobbies: Dict[str, Lobby] = {}


def _generate_code() -> str:
    return "".join(
        secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)
    )


def create_lobby(round_count: int) -> tuple[Lobby, str]:
    code = _generate_code()
    lobby = Lobby(code=code, players=[], round_count=round_count)
    _lobbies[code] = lobby
    host_id = str(uuid.uuid4())
    token = encode({"sub": host_id, "lobby": code, "role": "host"})
    return lobby, token


def get_lobby(code: str) -> Lobby | None:
    return _lobbies.get(code)


def add_player(code: str, nickname: str, avatar: str) -> tuple[Player, str]:
    lobby = _lobbies[code]
    if any(p.nickname == nickname for p in lobby.players):
        raise ValueError("NAME_TAKEN")
    player = Player(id=str(uuid.uuid4()), nickname=nickname, avatar=avatar)
    lobby.players.append(player)
    token = encode({"sub": player.id, "lobby": code, "role": "player"})
    return player, token


def start_game(code: str) -> None:
    lobby = _lobbies[code]
    lobby.state = "IN_GAME"
    engine.start_game(lobby)
