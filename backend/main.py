from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Header,
)
from fastapi.responses import Response

from . import lobbies
from .auth import decode
from .game.models import Lobby

app = FastAPI(title="Lie-Ability")


@app.get("/healthz", status_code=204)
async def healthz() -> Response:
    """Health check endpoint."""
    return Response(status_code=204)


@app.get("/version")
async def version() -> dict[str, str]:
    """Return current git SHA."""
    sha = os.getenv("GIT_SHA", "dev")
    return {"version": sha}


# ------------------ Auth dependency ------------------


def get_payload(authorization: str = Header(default="")) -> dict:
    """Extract and verify JWT from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split()[1]
    try:
        return decode(token)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=401, detail="Invalid token") from exc


# ------------------ Lobby CRUD ------------------


@app.post("/api/v1/lobbies", status_code=201)
async def create_lobby(body: dict) -> dict:
    round_count = int(body.get("roundCount", 3))
    lobby, token = lobbies.create_lobby(round_count)
    return {"code": lobby.code, "hostToken": token}


@app.post("/api/v1/lobbies/{code}/join")
async def join_lobby(code: str, body: dict) -> dict:
    lobby = lobbies.get_lobby(code)
    if not lobby:
        raise HTTPException(status_code=404, detail="LOBBY_NOT_FOUND")
    nickname = body.get("nickname")
    avatar = body.get("avatar")
    if not nickname or not avatar:
        raise HTTPException(status_code=400, detail="Invalid body")
    try:
        player, token = lobbies.add_player(code, nickname, avatar)
    except ValueError:
        raise HTTPException(status_code=409, detail="NAME_TAKEN")
    return {"playerToken": token, "playerId": player.id}


@app.get("/api/v1/lobbies/{code}")
async def get_lobby(code: str, payload: dict = Depends(get_payload)) -> Lobby:
    lobby = lobbies.get_lobby(code)
    if not lobby:
        raise HTTPException(status_code=404, detail="LOBBY_NOT_FOUND")
    if payload.get("lobby") != code:
        raise HTTPException(status_code=403, detail="Wrong lobby")
    return lobby


@app.post("/api/v1/lobbies/{code}/start")
async def start_lobby(code: str, payload: dict = Depends(get_payload)) -> Response:
    if payload.get("role") != "host":
        raise HTTPException(status_code=403, detail="Host only")
    lobby = lobbies.get_lobby(code)
    if not lobby:
        raise HTTPException(status_code=404, detail="LOBBY_NOT_FOUND")
    lobbies.start_game(code)
    return Response(status_code=204)


# ------------------ WebSocket ------------------

_connections: Dict[str, List[WebSocket]] = defaultdict(list)


async def broadcast_lobby_update(code: str) -> None:
    lobby = lobbies.get_lobby(code)
    if not lobby:
        return
    message = {
        "type": "lobby_update",
        "payload": {"players": [p.dict() for p in lobby.players]},
        "ts": int(time.time() * 1000),
    }
    for ws in list(_connections[code]):
        try:
            await ws.send_json(message)
        except WebSocketDisconnect:
            _connections[code].remove(ws)


@app.websocket("/ws/lobbies/{code}")
async def lobby_ws(websocket: WebSocket, code: str, token: str | None = None) -> None:
    if token is None:
        await websocket.close(code=4401)
        return
    try:
        payload = decode(token)
    except Exception:
        await websocket.close(code=4401)
        return
    if payload.get("lobby") != code:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    _connections[code].append(websocket)
    await broadcast_lobby_update(code)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections[code].remove(websocket)
        await broadcast_lobby_update(code)
