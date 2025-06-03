# Lie‑Ability Docs

Welcome to the **Lie‑Ability** documentation hub — your one‑stop guide to bluff‑based glory. Whether you’re a player, developer, or curious spectator, you’ll find everything you need to run, hack, and extend the game here.

> **Status:** Early alpha • PRs welcome • ⚠️ Expect breaking changes until `v1.0`

---

## 🚀 Quick Links

| Topic                 | Doc                                               |
| --------------------- | ------------------------------------------------- |
| 📐 **Architecture**   | [docs/architecture.md](./architecture.md)         |
| 🎲 **Gameplay Rules** | [docs/gameplay.md](./gameplay.md)                 |
| 🔌 **REST API**       | [docs/api/backend.md](./api/backend.md)           |
| 🔄 **WebSocket API**  | [docs/api/websocket.md](./api/websocket.md)       |
| 🛠️ **Dev Setup**     | [docs/dev/setup.md](./dev/setup.md)               |
| 🐳 **Docker Guide**   | [docs/dev/docker.md](./dev/docker.md)             |
| 🤝 **Contributing**   | [docs/dev/contributing.md](./dev/contributing.md) |

---

## 🎮 What Is Lie‑Ability?

Lie‑Ability is an open‑source party trivia game inspired by *Fibbage*. Up to eight players use their phones to invent convincing lies, guess the truth, and outwit friends in the living‑room or over video chat. The project combines a **FastAPI** backend, **React/Vite** frontends, and real‑time WebSockets for sub‑second play.

---

## 🏁 Getting Started

1. **Clone & Run (native):**

   ```bash
   git clone https://github.com/thisguyrob/lie-ability && cd lie-ability
   ./start.sh -n  # native mode
   ```
2. **Or Docker Compose:**

   ```bash
   docker compose up --build
   ```
3. Open [http://localhost](http://localhost) (player view) and [http://localhost/shared](http://localhost/shared) (shared display).
4. Scan the QR code, choose a nickname, and start lying!

For full environment details see **[Dev Setup](./dev/setup.md)**.

---

## 🗺️ Docs Roadmap

We aim for concise, example‑driven docs. Upcoming sections:

* **Prompt CSV guidelines**
* **Theming / CSS tokens**
* **Deploying to Fly.io / Render**
* **Analytics & Telemetry opt‑in**

Feel free to open an issue if you spot a gap.

---

## 👥 Community & Support

* GitHub [Discussions](https://github.com/thisguyrob/lie-ability/discussions)

Raise bugs under **Issues**; chat or brainstorm in **Discussions**.

---

Happy bluffing — and may the wiliest liar win! 🎉
