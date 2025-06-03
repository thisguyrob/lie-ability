# WebSocket Protocol

**Channel:** `/ws/lobbies/{code}`  |  **Version:** `v1`  |  **Transport:** native WebSocket (no Socket.IO framing)

The WebSocket provides real‑time, low‑latency updates to both the **Shared Display** and **Player Devices**.  All gameplay after joining the lobby relies exclusively on this duplex channel.

---

## 1 · Connection Handshake

```
GET /ws/lobbies/A1B2C3?token=<jwt> HTTP/1.1
Upgrade: websocket
Sec-WebSocket-Key: Z3Vlc3Mgd2hhdA==
```

* **Query param `token`** – signed JWT (see `/login` in backend API).  The server rejects the connection with `4401` close code if invalid or expired.
* **Compression** – `permessage-deflate` negotiated by default; can be disabled via `?compress=0`.

### 1.1 Heartbeats

* **Ping** – Server sends `ping` opcode every **15 s**.
* **Pong** – Client responds automatically per WebSocket standard.
* After **3 missed pongs** the server closes with code `4000` (`KEEPALIVE_TIMEOUT`).

---

## 2 · Message Envelope

All application messages are UTF‑8 JSON strings matching the TypeScript interface below.

```ts
type EventType =
  | "lobby_update"
  | "phase_change"
  | "prompt"
  | "choices"
  | "reveal"
  | "scoreboard"
  | "game_over"
  | "error"
  | "submit_lie"        // client→server
  | "submit_vote"       // client→server
  | "heartbeat";        // client→server

interface WSMessage<T = unknown> {
  type: EventType;
  payload: T;
  ts: number; // Unix epoch ms
}
```

Server & client must ignore unknown `type` values for forward compatibility.

---

## 3 · Server → Client Events

| `type`         | Payload Schema                                                                   | Notes                                                               |
| -------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `lobby_update` | `{ players: Player[] }`                                                          | Fires when a player joins/leaves or changes name.                   |
| `phase_change` | `{ phase: Phase; deadline: number }`                                             | Syncs timers; `deadline` is epoch ms.                               |
| `prompt`       | `{ id: string; category: string; text: string }`                                 | Trivia prompt for current round.                                    |
| `choices`      | `{ list: Choice[] }`                                                             | Truth + lies shuffled.  `Choice.authorId === null` indicates truth. |
| `reveal`       | `{ truthId: string; fooled: FoolPair[]; scoresDelta: Record<playerId, number> }` |                                                                     |
| `scoreboard`   | `{ scores: Score[] }`                                                            | Cumulative scores after each round.                                 |
| `game_over`    | `{ final: Score[] }`                                                             | Final standings.                                                    |
| `error`        | `{ code: string; message: string }`                                              | Non‑fatal protocol errors.                                          |

### Complex Types

```ts
interface Player { id: string; nickname: string; avatar: string; connected: boolean; }
interface Choice { id: string; text: string; authorId: string | null; }
type Phase = "LOBBY" | "LIE_SUBMISSION" | "VOTING" | "REVEAL" | "SCOREBOARD" | "GAME_OVER";
interface Score { playerId: string; total: number; }
interface FoolPair { victimId: string; liarId: string; }
```

---

## 4 · Client → Server Events

| `type`        | Payload                | Validation                                               |
| ------------- | ---------------------- | -------------------------------------------------------- |
| `submit_lie`  | `{ text: string }`     | Only allowed in `LIE_SUBMISSION` phase.  Empty→auto-lie. |
| `submit_vote` | `{ choiceId: string }` | Must reference existing choice & not own lie.            |
| `heartbeat`   | `{}`                   | Optional; if sent, server echoes nothing.                |

If a client sends an invalid event, the server responds with `error` event and may close the socket with code `4400` (`BAD_REQUEST`).

---

## 5 · Close Codes

| Code   | Meaning            | When Emitted                       |
| ------ | ------------------ | ---------------------------------- |
| `1000` | Normal closure     | Game over or page unload.          |
| `4000` | Keep‑alive timeout | 3 missed pongs.                    |
| `4400` | Bad request        | Malformed JSON or invalid payload. |
| `4401` | Unauthorized       | Missing/invalid JWT.               |
| `4420` | Phase violation    | Action outside allowed phase.      |

---

## 6 · Example Round (JSON)

<details>
<summary>Expand to view</summary>

```jsonc
// 1) Server ➜ Client (prompt)
{"type":"prompt","payload":{"id":"p_42","category":"TRIVIA TIME","text":"Mickey Mouse's middle name is _____."},"ts":1717001000000}

// 2) Client ➜ Server (submit_lie)
{"type":"submit_lie","payload":{"text":"Theodore"},"ts":1717001005123}

// … all lies collected …
// 3) Server ➜ Client (choices)
{"type":"choices","payload":{"list":[{"id":"c0","text":"Theodore","authorId":null}, {"id":"c1","text":"Fauntleroy","authorId":"p42"}]},"ts":1717001030000}

// 4) Client ➜ Server (submit_vote)
{"type":"submit_vote","payload":{"choiceId":"c0"},"ts":1717001032233}

// 5) Server ➜ Client (reveal)
{"type":"reveal","payload":{"truthId":"c0","fooled":[{"victimId":"p99","liarId":"p42"}],"scoresDelta":{"p42":250,"p01":500}},"ts":1717001040000}
```

</details>

---

## 7 · Client Libraries

Use any native WebSocket client.  Examples:

### JavaScript (browser)

```js
const url = `wss://${location.host}/ws/lobbies/${code}?token=${jwt}`;
const ws = new WebSocket(url);
ws.onopen = () => console.log("connected");
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  // handle by msg.type …
};
```

### Python (asyncio)

```python
import websockets, json, asyncio
async def main():
    uri = f"wss://localhost/ws/lobbies/{code}?token={jwt}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "heartbeat", "payload": {}, "ts": int(time.time()*1000)}))
        async for raw in ws:
            msg = json.loads(raw)
            print(msg)
asyncio.run(main())
```

---

## 8 · Testing Tips

* Use `npm run ws-dev` to launch a hot‑reload WebSocket echo client in `/tools/ws-tester`.
* Mock events in Jest with `@lie-ability/test-utils` for deterministic UI tests.
* Fuzz packets with [`websock-fuzz`](https://github.com/link/websock-fuzz) to ensure graceful error handling.

---

## 9 · Change Log

* **`v1.1`** – Added `phase_change` deadline sync, close code `4420`.
* **`v1.0`** – Initial release with basic gameplay events.

---

Happy hacking & may your lies be convincing! 🚀