# Lie-Ability

**Lie-Ability** is an open source party trivia bluffing game inspired by *Fibbage*. Players compete to uncover the truth hidden among each other’s lies.

Each round, players are presented with obscure trivia prompts like:

> **CELEBRITY TWEET!**  
> @realDonaldTrump: Who wouldn't take _____'s picture and make lots of money if she does the nude sunbathing thing?

or

> **TRIVIA TIME!**  
> Mickey Mouse's middle name is _____.

Players then submit fake answers (bluffs) to fool their friends — and try to pick the real one. Score points for choosing the truth or tricking others into choosing your lie. Up to 8 players can join a single game using their smartphones.

---

## 🎮 Screenshots

*Coming soon!*

Expect to see:
- A **shared display** view (for TVs or projectors)
- **Personal screens** (for phones/tablets used by each player)

---

## 🚀 Quickstart (Mac/Linux)

All you need is:

```bash
./start.sh
````

This will:

* Launch the server
* Open the shared display in a new browser window

> 🧪 Not tested on Windows yet — PRs welcome!

---

## ✨ Features

* 🧠 Bluff-based trivia gameplay
* 📱 Join from your phone via QR code
* 🖥️ One shared display, multiple personal screens
* 🎉 Up to 8 players
* 🔄 Rounds of prompts, lies, voting, and reveals

---

## 📦 Installation

1. Clone this repo:

   ```bash
   git clone https://github.com/thisguyrob/lie-ability.git
   cd lie-ability
   ```

2. Run the game:

   ```bash
   ./start.sh
   ```

---

## 🕹️ Usage

1. Run the bash script:

   ```bash
   ./start.sh
   ```
2. Wait for the server to load
3. Cast the **shared display** to a TV or projector
4. Have players scan the QR code on-screen to join the lobby
5. Start the game when everyone has joined

---

## 🛠️ Contributing

This game is being built using OpenAI Codex as a collaborative coding agent. Codex interprets game specifications and produces pull requests, which are then reviewed and merged.

To contribute:

* Submit a GitHub issue with your idea or feature request
* Codex may propose an implementation
* Human reviewers will verify functionality and approve changes

See [`docs/`](./docs) for gameplay architecture and current dev goals.

---

## 📜 License

This project is released under a **Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)**.
See [`LICENSE`](./LICENSE) for full terms.

---

## 🙏 Credits

* Built with ❤️ by [Codex](https://platform.openai.com/docs/guides/codex) and the open source community
* Inspired by *Fibbage* by Jackbox Games