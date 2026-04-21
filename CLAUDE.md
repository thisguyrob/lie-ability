# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lie-Ability** is a local multiplayer party game (inspired by Fibbage/Balderdash) where players submit fake answers to trivia questions and vote to identify the real one. It runs as a local Flask server — one device displays the main screen, others join on their phones via QR code.

## Running the App

```bash
# Quick start (macOS — sets up venv, installs deps, launches)
./start.command

# Manual
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
LAUNCH_MODE=dev python app.py   # opens Tkinter launcher; click START
```

The server runs at `http://localhost:6767`. Two views:
- `/main/` — shared display (TV/laptop screen)
- `/players/` — player device UI (phones via QR code)

**Environment variables** (all optional):
- `LAUNCH_MODE` — `debug` | `dev` | `main` (controls log verbosity; default: `main`)
- `LM_STUDIO_URL` — embedding service for lie similarity (default: `http://localhost:1234`)
- `LIE_SIMILARITY_THRESHOLD` — cosine similarity cutoff (default: `0.75`)

No test, lint, or build tooling exists yet.

## Architecture

### Request flow
Browser ↔ Flask REST (`/api/*`) + Socket.IO WebSocket ↔ singleton `GameState` (in-memory, mutex-protected) ↔ SQLite (`data/questions.db`)

### Key files
| File | Role |
|------|------|
| `app.py` | Entry point; creates Flask app, starts Tkinter launcher |
| `server/__init__.py` | Flask app factory, SocketIO init |
| `server/game.py` | `GameState` dataclasses + all game logic, scoring, appeals |
| `server/routes.py` | All REST API endpoints |
| `server/events.py` | Socket.IO connect/disconnect/identify handlers |
| `server/timers.py` | Phase timeout auto-advance + per-second countdown ticks |
| `server/db.py` | SQLite schema, seeding from `data/seed.json`, question weighting |
| `server/embeddings.py` | Optional LM Studio similarity check for duplicate lies |
| `server/views.py` | Route handlers returning rendered HTML templates |

### Game phase machine
`lobby → category_pick → lie_submission → voting → likes → round_results → (appeal_vote →) round_results → ... → game_over`

Phase transitions are driven by REST calls (players acting) or timer expiry (`server/timers.py`). Each transition emits a `phase_change` Socket.IO event with a deadline, and `timer_tick` every second.

### State management
- **Single `GameState` instance** (module-level in `server/game.py`) shared across all threads
- All mutations are wrapped with `game_state_lock` (threading.Lock)
- After every mutation, the route/event handler broadcasts the full state via `emit('game_state', ...)`

### Templates & static
- Jinja2 templates under `templates/main/` and `templates/player/`
- Player UI logic lives in inline `<script>` in `templates/player/index.html`; it handles all Socket.IO events client-side and swaps scene fragments
- `static/socket.io.min.js` is a local CDN fallback

### Database
SQLite at `data/questions.db` (gitignored; regenerated from `data/seed.json` on first run).
```
categories(id, name)
questions(id, category_id, prompt, answer, group_name, used_count, last_used_at)
question_lies(id, question_id, text)   -- pre-written plausible lies
```
Questions are weighted toward least-recently-used and those that fooled more players historically.

### Scoring
- Correct guess: 1000 pts × round multiplier (1×/2×/3× for rounds 1–3)
- Fooling a voter: 500 pts × round multiplier per voter fooled
- Appeals: players who voted correctly vote; majority accept grants points to those fooled by the lie

## Worktrees

The repo uses git worktrees for parallel feature development:
- `codex/main-view` → main display UI work
- `codex/players-view` → player device UI work
- `codex/backend` → server & game logic

Work on the matching branch when making changes scoped to one area.
