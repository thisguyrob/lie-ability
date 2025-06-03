# API Overview

*Last updated: 2025‑06‑02*

This document describes the public-facing HTTP and WebSocket APIs for the **Lie‑Ability** game server. The server encodes all traffic as JSON (UTF‑8). Production uses HTTPS or `ws[s]://`, while local development permits plain HTTP and WebSocket.

> **Scope**
> ‑ High‑level resource map for REST endpoints
> ‑ Event catalogue for the WebSocket real‑time channel
> Detailed request/response schemas live beside implementation files (e.g. `backend/schemas/`).

---

## 1  Base URLs

| Environment                        | REST base                                 | WS base                                    |
| ---------------------------------- | ----------------------------------------- | ------------------------------------------ |
| **Local dev** (`./start.sh --dev`) | `http://localhost:8000/api/v1`            | `ws://localhost:8000/socket.io`            |
| **Docker** (`docker compose up`)   | `http://localhost:8000/api/v1`            | `ws://localhost:8000/socket.io`            |
| **Production**                     | `https://lie‑ability.yourhost.com/api/v1` | `wss://lie‑ability.yourhost.com/socket.io` |

---

## 2  Authentication

* **Anonymous JWT** – on first lobby join, the server issues a short‑lived token (signed with `SECRET_KEY`).  The token is:

  * echoed in the HTTP `Set‑Cookie: la_token=<jwt>; HttpOnly` header, **and**
  * returned in JSON (`{"token": "…"}`) for non‑browser clients.
* Clients then include the token in subsequent REST calls (`Authorization: Bearer …`) and the Socket.IO connection query (`token=<jwt>`).
* A `/auth/refresh` endpoint renews tokens every 30 minutes.

*No registration / password flow is required for gameplay.*

---

## 3  REST Endpoints

### 3.1  Health & Meta

| Method | Path       | Description                                | Auth |
| ------ | ---------- | ------------------------------------------ | ---- |
| `GET`  | `/healthz` | Liveness probe (returns `{"status":"ok"}`) | None |
| `GET`  | `/version` | Git SHA & semantic version                 | None |

### 3.2  Lobby Lifecycle

| Method   | Path                    | Body                                 | Description                                    |
| -------- | ----------------------- | ------------------------------------ | ---------------------------------------------- |
| `POST`   | `/lobbies`              | `{ "rounds": 3, "pack": "classic" }` | Create a new lobby. Returns lobby code.        |
| `GET`    | `/lobbies/{code}`       | —                                    | Fetch current lobby state (players, settings). |
| `POST`   | `/lobbies/{code}/start` | —                                    | Host starts the game.                          |
| `DELETE` | `/lobbies/{code}`       | —                                    | Close lobby and kick clients.                  |

### 3.3  Prompts (Admin)

| Method | Path              | Description                                             |
| ------ | ----------------- | ------------------------------------------------------- |
| `POST` | `/prompts/upload` | CSV file upload (multipart/form‑data); returns pack ID. |
| `GET`  | `/prompts/packs`  | List available prompt packs + counts.                   |

*All admin endpoints require a token with the `role=host` claim (granted automatically to lobby creator).*

---

## 4  WebSocket (Socket.IO) Events

```text
namespace: /
transport: WebSocket preferred, falls back to polling
```

| Direction | Event             | Payload                      | Purpose                                             |
| --------- | ----------------- | ---------------------------- | --------------------------------------------------- |
| C → S     | `lobby.join`      | `{ code, nickname, avatar }` | Join lobby; server responds with `lobby.state`.     |
| S → C     | `lobby.state`     | `LobbyState`                 | Current lobby snapshot (players, settings, status). |
| C → S     | `lobby.leave`     | `—`                          | Client voluntarily leaves.                          |
| S → C     | `game.prompt`     | `Prompt`                     | New prompt broadcast to all players.                |
| C → S     | `game.submit_lie` | `{ text }`                   | Player sends bluff.                                 |
| S → C     | `game.choices`    | `{ id, text }[]`             | Shuffled truth + lies.                              |
| C → S     | `game.vote`       | `{ choice_id }`              | Player casts vote.                                  |
| C → S     | `game.like`       | `{ choice_id }`              | Optional like.                                      |
| S → C     | `game.reveal`     | `RevealState`                | Ordered reveal of lies & truth.                     |
| S → C     | `game.scoreboard` | `Scoreboard`                 | Round results & cumulative points.                  |
| S → C     | `game.end`        | `FinalResults`               | Final standings; triggers Game Over screen.         |
| \* ↔ \*   | `error`           | `{ code, message }`          | Non‑fatal error (e.g. invalid payload).             |

### 4.1  Core Payload Schemas (TypeScript)

```ts
interface Prompt {
  id: string;    // UUID
  category: string;
  text: string;  // e.g. "Mickey Mouse's middle name is _____"
  round: number; // 1‑based
}

interface Choice {
  id: string;   // random ULID
  text: string; // lie or truth
}

interface LobbyState {
  code: string;
  players: PlayerMeta[];
  rounds: number;
  pack: string;
  started: boolean;
}

interface Scoreboard {
  round: number;
  rows: Array<{ playerId: string; roundPoints: number; total: number; likes: number }>;
}
```

The auto-generated **ReDoc** docs bundle the full JSON Schema files from `backend/schemas/` (`make redoc`).

---

## 5  Rate Limits & Timeouts

* **REST** – 60 req/min per IP (429 on exceed).
* **WebSocket** – heartbeat ping every 15 s, disconnect after 40 s of silence.
* The server enforces lie submission and voting windows; it NACKs late packets with `error { code:"timeout" }`.

---

## 6  Versioning

This is API v1.  Breaking changes increment the path prefix (`/api/v2`). Minor additive changes (fields, events) require no version bump.

---

## 7  Changelog

| Date       | Change                |
| ---------- | --------------------- |
| 2025‑06‑02 | Initial public draft. |

---

Questions? Open an issue with the **api** label or ping `@maintainers` in Discord.
