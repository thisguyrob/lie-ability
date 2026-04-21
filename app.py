from __future__ import annotations

import logging
import os
import threading
import time
import webbrowser
import tkinter as tk
from typing import Optional

import requests

from server import create_app, socketio

LAUNCH_MODE = os.environ.get("LAUNCH_MODE", "main")
BASE_URL = "http://localhost:6767"
MAIN_URL = f"{BASE_URL}/main/"
PLAYER_URL = f"{BASE_URL}/players/"
GAME_STATE_URL = f"{BASE_URL}/api/game/state"
GAME_START_URL = f"{BASE_URL}/api/game/start"
POLL_INTERVAL_MS = 1000
REQUEST_TIMEOUT_S = 1.5

werkzeug_log = logging.getLogger("werkzeug")
if LAUNCH_MODE == "debug":
    logging.basicConfig(level=logging.DEBUG)
elif LAUNCH_MODE == "dev":
    werkzeug_log.setLevel(logging.INFO)
else:
    werkzeug_log.setLevel(logging.ERROR)


def count_joined_players(state: Optional[dict]) -> int:
    players = (state or {}).get("players") or []
    return sum(1 for player in players if player.get("connected", True))


def can_start_game(state: Optional[dict]) -> bool:
    if not state:
        return False
    return state.get("phase") == "lobby" and count_joined_players(state) >= 2


def format_countdown_text(state: Optional[dict], now_ts: Optional[float] = None) -> str:
    if not state:
        return "Current timer: --"

    phase = (state.get("phase") or "").replace("_", " ").strip()
    deadline_ts = state.get("phase_deadline_ts")
    if not phase or deadline_ts is None:
        return "Current timer: --"

    remaining_seconds = max(0, int(deadline_ts - (now_ts if now_ts is not None else time.time())))
    minutes, seconds = divmod(remaining_seconds, 60)
    timer_name = phase.capitalize()
    return f"{timer_name} timer: {minutes:02d}:{seconds:02d}"


def fetch_game_state(session: requests.Session) -> Optional[dict]:
    response = session.get(GAME_STATE_URL, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    return response.json()


def start_game(session: requests.Session) -> tuple[bool, str]:
    response = session.post(GAME_START_URL, json={}, timeout=REQUEST_TIMEOUT_S)
    if response.ok:
        return True, "Game started. Category pick is live."

    message = "Unable to start the game."
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if payload.get("error"):
        message = payload["error"]
    return False, message


def open_game_views() -> None:
    webbrowser.open(MAIN_URL)
    webbrowser.open(PLAYER_URL)


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.session = requests.Session()
        self.latest_state: Optional[dict] = None

        root.title("Lie-Ability")
        root.geometry("360x270")
        root.resizable(False, False)

        self.server_label = tk.Label(root, text=f"Server running at {BASE_URL}", fg="gray")
        self.server_label.pack(pady=(18, 6))

        self.player_count_label = tk.Label(root, text="Players joined: --", font=("TkDefaultFont", 11, "bold"))
        self.player_count_label.pack(pady=(4, 4))

        self.phase_label = tk.Label(root, text="Phase: starting up...", fg="gray")
        self.phase_label.pack(pady=(0, 12))

        self.countdown_label = tk.Label(root, text="Current timer: --", font=("TkDefaultFont", 11))
        self.countdown_label.pack(pady=(0, 12))

        self.open_button = tk.Button(root, text="Open Game Screens", command=open_game_views, width=22, height=2)
        self.open_button.pack(pady=(0, 10))

        self.start_button = tk.Button(root, text="Start Game", command=self.on_start_game, width=22, height=2, state=tk.DISABLED)
        self.start_button.pack()

        self.status_label = tk.Label(
            root,
            text="Waiting for at least 2 players to join.",
            fg="gray",
            wraplength=300,
            justify="center",
        )
        self.status_label.pack(pady=(12, 0))

        self.root.after(250, self.poll_state)

    def poll_state(self) -> None:
        try:
            state = fetch_game_state(self.session)
        except requests.RequestException:
            self.latest_state = None
            self.player_count_label.config(text="Players joined: --")
            self.phase_label.config(text="Phase: server unavailable")
            self.countdown_label.config(text="Current timer: --")
            self.start_button.config(state=tk.DISABLED)
            self.status_label.config(text="Connecting to the local game server...", fg="gray")
        else:
            self.latest_state = state
            self.render_state(state)
        finally:
            self.root.after(POLL_INTERVAL_MS, self.poll_state)

    def render_state(self, state: dict) -> None:
        joined_players = count_joined_players(state)
        phase = state.get("phase", "unknown").replace("_", " ")

        self.player_count_label.config(text=f"Players joined: {joined_players}")
        self.phase_label.config(text=f"Phase: {phase}")
        self.countdown_label.config(text=format_countdown_text(state))

        if can_start_game(state):
            self.start_button.config(state=tk.NORMAL)
            self.status_label.config(text="Ready to start.", fg="green")
            return

        self.start_button.config(state=tk.DISABLED)
        if state.get("phase") != "lobby":
            self.status_label.config(text="A game is already in progress.", fg="gray")
        else:
            needed = max(0, 2 - joined_players)
            noun = "player" if needed == 1 else "players"
            self.status_label.config(text=f"Waiting for {needed} more {noun} to join.", fg="gray")

    def on_start_game(self) -> None:
        try:
            ok, message = start_game(self.session)
        except requests.RequestException:
            self.status_label.config(text="Could not reach the local game server.", fg="red")
            self.start_button.config(state=tk.DISABLED)
            return

        self.status_label.config(text=message, fg="green" if ok else "red")
        if ok:
            self.start_button.config(state=tk.DISABLED)
            try:
                self.latest_state = fetch_game_state(self.session)
            except requests.RequestException:
                return
            self.render_state(self.latest_state)


def start_server() -> threading.Thread:
    flask_app = create_app()
    server_thread = threading.Thread(
        target=lambda: socketio.run(
            flask_app,
            host="0.0.0.0",
            port=6767,
            use_reloader=False,
            debug=LAUNCH_MODE == "debug",
            allow_unsafe_werkzeug=True,
        ),
        daemon=True,
    )
    server_thread.start()
    return server_thread


def main() -> None:
    start_server()
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
