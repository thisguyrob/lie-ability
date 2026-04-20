# Lie-Ability

Lie-Ability is a prototype of a local party game built with Flask and Tkinter. The long-term idea is a web-based bluffing and trivia game inspired by games like Fibbage and Balderdash, where players invent plausible lies and try to guess the truth.

Right now, this repository contains a very early local prototype with:
- a small Tkinter launcher window
- a Flask server running on `http://localhost:6767`
- placeholder `/main/` and `/players/` browser views

## Current Status

The current app is not a full game yet. It currently serves two simple prototype pages from a single Python app:
- `/main/` for the shared main display
- `/players/` for the player-facing view

This is a good foundation for iterating on the main view, player view, and backend logic independently.

## Planned Game Direction

The intended game direction is still:
- a local party game for roughly 2–8 players
- a shared display for the main screen
- individual player devices for player interaction
- rounds centered on bluffing, trivia, and guessing the real answer

Planned round flow:
1. Lobby: Players join and enter names.
2. Choose Category: A rotating player picks a question category.
3. Submit Lies: Everyone invents and submits a fake answer.
4. Pick Truth: Players review the options and guess the real answer.
5. Likes: Players can react to favorite lies.
6. Scoring: Points and likes are tallied.
7. Repeat: More rounds continue with scorekeeping.
8. End: A winner is declared.

These steps describe the target game design, not the current implemented feature set.

## Running The Prototype

Requirements:
- Python 3
- `tkinter` available for your Python install

Quick start on macOS:

```bash
./start.command
```

That script will:
- create `.venv` if needed
- install dependencies from `requirements.txt`
- prompt for a launch mode
- start the app

You can also run it manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

When the launcher opens, press `START` to open:
- `http://localhost:6767/main/`
- `http://localhost:6767/players/`

## Development Workspaces

This repo is set up to support isolated development with `git worktree`.

Base workspace:
- `/Users/robfalk/Dev/lie-ability` on `main`

Isolated worktrees:
- `/Users/robfalk/Dev/lie-ability-main-view` on `codex/main-view`
- `/Users/robfalk/Dev/lie-ability-players-view` on `codex/players-view`
- `/Users/robfalk/Dev/lie-ability-backend` on `codex/backend`

Recommended usage:
- use the main-view worktree for `/main/` UI changes
- use the players-view worktree for `/players/` UI changes
- use the backend worktree for server and app-structure changes

This keeps work separated by branch and folder so changes can be developed in parallel and merged back cleanly later.
