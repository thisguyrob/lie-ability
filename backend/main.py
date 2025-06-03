from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
import os

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


@app.websocket("/ws/lobbies/{code}")
async def lobby_ws(websocket: WebSocket, code: str) -> None:
    """Accepts a WebSocket connection and sends a ping."""
    await websocket.accept()
    await websocket.send_json({"type": "ping"})
