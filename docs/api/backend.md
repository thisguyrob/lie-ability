# Backend API

**Version:** `v1`  |  **Base URL:** `http(s)://<host>:8000` (native) / `http://localhost` (Docker) 

This document specifies all HTTP & WebSocket interfaces exposed by the Lie‑Ability game server.  All routes are mounted under `/api/v1` except the WebSocket, which is `/ws`.

> **Tech stack**: FastAPI + Uvicorn + SQLAlchemy + Redis Pub/Sub.
> JSON payloads use **camelCase** keys.  All examples are truncated for brevity.

---

## 1 · Authentication & Headers

| Header          | Example                    | Notes                             |
| --------------- | -------------------------- | --------------------------------- |
| `Authorization` | `Bearer eyJhbGciOiJIUzI1…` | JWT issued by `/login/anonymous`  |
| `X-Client-Id`   | `0d6171b0-…`               | Random UUID; helps correlate logs |
| `Content-Type`  | `application/json`         | Always JSON except file upload    |

JWT claims:

```json
{
  "sub": "player:73c51e2e",
  "lobby": "A1B2C3",
  "role": "player",   // or host
  "exp": 1717000000
}
```

---

## 2 · REST Endpoints

### 2.1 Health & Meta

| Verb  | Path       | Response                    | Purpose              |
| ----- | ---------- | --------------------------- | -------------------- |
| `GET` | `/healthz` | `200 OK` / `204 No Content` | Liveness probe       |
| `GET` | `/version` | `{ "version": "1.2.0" }`    | Git SHA & build date |

### 2.2 Lobby Lifecycle

| Verb   | Path                    | Req Body                                | Response                                                 |
| ------ | ----------------------- | --------------------------------------- | -------------------------------------------------------- |
| `POST` | `/lobbies`              | `{ "roundCount": 7 }`                   | `201 Created` → `{ "code": "A1B2C3", "hostToken": "…" }` |
| `POST` | `/lobbies/{code}/join`  | `{ "nickname": "Rob", "avatar": "🦊" }` | `200` → `{ "playerToken": "…", "playerId": "…" }`        |
| `GET`  | `/lobbies/{code}`       | —                                       | Lobby state (player list, settings)                      |
| `POST` | `/lobbies/{code}/start` | —                                       |  Start game (host only)                                  |

### 2.3 Gameplay Actions

| Verb   | Path                   | Req Body                 | Response                           |
| ------ | ---------------------- | ------------------------ | ---------------------------------- |
| `POST` | `/games/{gameId}/lie`  | `{ "text": "Theodore" }` | `204`                              |
| `POST` | `/games/{gameId}/vote` | `{ "choiceId": 3 }`      | `204`                              |
| `POST` | `/games/{gameId}/next` | —                        | Skip to next phase (host shortcut) |

### 2.4 Prompts API *(Admin)*

| Verb     | Path                    | Notes                          |
| -------- | ----------------------- | ------------------------------ |
| `GET`    | `/prompts/packs`        | List available packs           |
| `POST`   | `/prompts/packs/upload` | `multipart/form-data` CSV file |
| `DELETE` | `/prompts/{id}`         | Remove custom prompt           |

---

## 3 · WebSocket Protocol

### 3.1 Connection

```
wss://<host>/ws/lobbies/{code}?token=<jwt>
```

* Requires a valid JWT; server disconnects after 3 × failed pings.
* Binary messages are ignored.

### 3.2 Envelope Format

```ts
interface Message<T = unknown> {
  type: string;     // event name
  payload: T;       // event‑specific data
  ts: number;       // unix millis
}
```

### 3.3 Server → Client Events

| `type`         | Payload                                                  | Description           |
| -------------- | -------------------------------------------------------- | --------------------- |
| `lobby_update` | `{ players: […] }`                                       | Player joined/left    |
| `phase_change` | `{ phase: "LIE_SUBMISSION", deadline: 171700… }`         | Timer sync            |
| `prompt`       | `{ id, category, text }`                                 | New trivia prompt     |
| `choices`      | `{ list: [{ id, text }] }`                               | Shuffled truth + lies |
| `reveal`       | `{ truthId, fooled: [{victimId, liarId}], scoresDelta }` | End of voting         |
| `scoreboard`   | `{ scores: [{playerId, total}] }`                        | After reveal          |
| `game_over`    | `{ final: [...] }`                                       | End‑game podium       |
| `error`        | `{ code, message }`                                      | See §4 codes          |

### 3.4 Client → Server Events

| `type`        | Payload        | Notes                    |
| ------------- | -------------- | ------------------------ |
| `submit_lie`  | `{ text }`     | Empty = auto‑generate    |
| `submit_vote` | `{ choiceId }` | Validates not own lie    |
| `heartbeat`   | `{}`           | Sent every 10 s (client) |

---

## 4 · Error Codes

| HTTP / WS Code    | Meaning | Suggested Fix                       |
| ----------------- | ------- | ----------------------------------- |
| `LOBBY_NOT_FOUND` | 404     | Check lobby code                    |
| `NAME_TAKEN`      | 409     | Choose different nickname           |
| `TOO_LATE`        | 400     | Action after timer expiry           |
| `INVALID_STATE`   | 409     | Action not allowed in current phase |
| `RATE_LIMIT`      | 429     | Slow down client                    |
| `SERVER_ERROR`    | 500     | Generic fallback                    |

---

## 5 · Data Models (Pydantic)

```python
class Choice(BaseModel):
    id: int
    text: str
    author_id: str | None  # None = truth

class Player(BaseModel):
    id: str
    nickname: str
    avatar: str
    score: int = 0

class Lobby(BaseModel):
    code: str
    players: list[Player]
    round_count: int
    state: Literal["LOBBY", "IN_GAME", "GAME_OVER"]
```

*Full schema is auto‑generated at `/docs/swagger` by FastAPI.*

---

## 6 · Example Flow (cURL + ws)

```bash
# Create lobby
curl -X POST -H 'Content-Type: application/json' \
     -d '{"roundCount": 7}' \
     http://localhost:8000/api/v1/lobbies
# → {"code":"A1B2C3","hostToken":"<jwt>"}

# Join lobby as player
curl -X POST -H 'Authorization: Bearer <jwt>' \
     -H 'Content-Type: application/json' \
     -d '{"nickname":"Rob","avatar":"🦊"}' \
     http://localhost:8000/api/v1/lobbies/A1B2C3/join
```

Then open a WebSocket client:

```js
const ws = new WebSocket("wss://localhost/ws/lobbies/A1B2C3?token=<jwt>");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## 7 · Environment & Scaling

* **Horizontal Scaling**: Use Redis for pub/sub (`REDIS_URL`) so multiple Uvicorn workers broadcast identical events.
* **CORS**: Configured via `ALLOWED_ORIGINS` env var.
* **Rate Limits**: `RPS_DEFAULT=30` per IP by default (Starlette middleware).
* **Docker Healthcheck**: `CMD curl -f http://localhost:8000/healthz || exit 1`.

---

## 8 · TODO / Future Endpoints

* `GET /stats/global` – fetch global leaderboard.
* `POST /games/{id}/chat` – in‑game chatter.
* `GET /prompts/random?category=…` – external prompt API.

---

Feel free to extend or refine this spec; Codex will generate Rust‑grade code clarity when it has a well‑defined contract! 🚀