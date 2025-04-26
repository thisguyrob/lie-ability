#!/usr/bin/env python3
"""
Lie‑Ability — bluffing‑trivia game (prototype with Debug Console)
===========================================================================
Run locally on macOS / Linux / Windows with **Python 3.11+**.

Quick‑start
-----------
1.  pip install flask flask-socketio eventlet
2.  python server.py
3.  Open http://<LAN‑IP>:1337/debug for the debug console
4.  Open http://<LAN‑IP>:1337/host on the host screen (placeholder)
5.  Players hit http://<LAN‑IP>:1337/player on their phones (placeholder)

Files expected in the same folder:
    ├─ server.py               (this file)
    ├─ sample.json             (questions; supplied by you)
    └─ static/ & templates/    (debug.html must be in templates/)
"""

from __future__ import annotations

import eventlet
eventlet.monkey_patch()

import json
import logging
import os
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from flask import Flask, jsonify, render_template, request, redirect
from flask_socketio import SocketIO, emit

BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = BASE_DIR / "sample.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lie-ability")

app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

if not QUESTIONS_PATH.exists():
    log.error("sample.json not found — create it first (see README)")
    raise SystemExit(1)

with QUESTIONS_PATH.open(encoding="utf-8") as fp:
    QUESTION_BANK: Dict[str, List[dict]] = json.load(fp)

@dataclass
class Player:
    sid: str
    name: str
    score: int = 0
    likes: int = 0
    deceptions: int = 0
    is_bot: bool = False

    def to_json(self):
        return asdict(self)

@dataclass
class GameState:
    _timer_gen: int = 0  # 🔐 internal generation counter to cancel old timers
    players: Dict[str, Player] = field(default_factory=dict)
    current_chooser: Optional[str] = None
    round: int = 1
    question_index: int = 0
    questions_per_round: Dict[int, int] = field(default_factory=lambda: {1: 8, 2: 8, 3: 1})
    phase: str = "lobby"
    current_question: Optional[dict] = None
    options: List[str] = field(default_factory=list)
    used_questions: Set[str] = field(default_factory=set)
    current_categories: List[str] = field(default_factory=list)
    submitted_lies: Set[str] = field(default_factory=set)
    lie_authors: Dict[str, Set[str]] = field(default_factory=dict)
    picks_submitted: Set[str] = field(default_factory=set)
    timer: Optional[int] = None

    def _question_pool(self) -> List[dict]:
        if self.round == 1:
            return QUESTION_BANK["round_one"]
        if self.round == 2:
            return QUESTION_BANK["round_two"]
        return QUESTION_BANK["final_round"]

    def get_category_choices(self) -> List[str]:
        pool = self._question_pool()
        available = [q for q in pool if q["question"] not in self.used_questions]
        random.shuffle(available)
        selected = available[:4]
        self.current_categories = [q["category"] for q in selected]
        return self.current_categories

    def next_question_by_category(self, chosen_category: str):
        pool = self._question_pool()
        for q in pool:
            if q["category"] == chosen_category and q["question"] not in self.used_questions:
                self.current_question = q
                self.used_questions.add(q["question"])
                self.question_index += 1
                self.phase = "submit_lie"
                self.cancel_timer()
                self.submitted_lies.clear()
                self.options.clear()
                self.picks_submitted.clear() 
                self.timer = None
                self.start_timer(45, force_move_to_pick_truth)  # ⏱️ Start lie timer!
                trigger_bots()

                log.info("[Game] Category chosen: %s → Question: %s", chosen_category, q["question"])
                return True
        
        self.current_chooser = None

        log.warning("[Game] No valid question found for category: %s", chosen_category)
        return False

    def next_question(self):
        """Skip directly to next unused question (for debug use)."""
        pool = self._question_pool()
        available = [q for q in pool if q["question"] not in self.used_questions]
        
        if not available:
            log.warning("[Game] next_question() called but no unused questions remain")
            return False

        q = random.choice(available)
        self.current_question = q
        self.used_questions.add(q["question"])
        self.question_index += 1
        self.phase = "submit_lie"
        self.cancel_timer()
        self.options.clear()
        self.submitted_lies.clear()
        self.picks_submitted.clear() 
        self.timer = None
        self.start_timer(45, force_move_to_pick_truth)  # ⏱️ Start lie timer!


        self.current_chooser = None

        log.info("[Game] next_question() → %s", q["question"])
        return True

    def advance_phase(self):
        order = [
            "lobby",
            "round_intro",
            "choose_category",
            "submit_lie",
            "pick_truth",
            "likes",
            "scoreboard",
        ]
        try:
            next_phase = order[order.index(self.phase) + 1]
        except (ValueError, IndexError):
            next_phase = None

        if self.phase == "scoreboard":
            total_so_far = sum(self.questions_per_round[r] for r in range(1, self.round))
            if self.question_index >= total_so_far + self.questions_per_round[self.round]:
                # All questions for this round finished
                if self.round < 3:
                    self.round += 1
                    self.phase = "round_intro"
                else:
                    self.phase = "game_over"
            else:
                self.phase = "choose_category"
        elif next_phase:
            self.phase = next_phase

        log.info("[Game] Phase → %s", self.phase)

        if self.phase == "round_intro":
            self.start_timer(3, self.advance_phase)

        elif self.phase == "choose_category":
            if self.players:
                self.current_chooser = random.choice(list(self.players))
            else:
                self.current_chooser = None

            chooser = self.players.get(self.current_chooser)
            log.info("[Choose] It’s %s’s turn to choose a category.", chooser.name if chooser else "nobody")

            self.get_category_choices()
            self.start_timer(15, auto_choose_category)

        elif self.phase == "submit_lie":
            self.start_timer(45, force_move_to_pick_truth)  # ⏱️ 45s to submit lies

        elif self.phase == "scoreboard":
            self.start_timer(5, self.advance_phase)

        else:
            self.timer = None

        trigger_bots()

    def start_timer(self, seconds: int, callback):
        self.cancel_timer()          # kill any previous timer
        self.timer = seconds         # expose the full value immediately
        socketio.emit("state", self.to_json())   # one immediate push

        my_gen = self._timer_gen

        def countdown():
            remaining = seconds
            while remaining > 0 and my_gen == self._timer_gen:
                socketio.sleep(1)
                remaining -= 1
                self.timer = remaining
                socketio.emit("state", self.to_json())
            if my_gen == self._timer_gen:
                callback()
                socketio.emit("state", self.to_json())
        socketio.start_background_task(countdown)


    def cancel_timer(self):
        """Immediately cancel any currently running timer."""
        self._timer_gen += 1
        self.timer = None
        socketio.emit("state", self.to_json())  # optional: update UI immediately

    def reset(self):
        self.__init__()

    def start_game(self):
        if self.phase == "lobby":
            log.info("[Game] Starting game → advancing from lobby to round_intro")
            self.advance_phase()

    def to_json(self):
        d = asdict(self)

        d["current_chooser"] = self.current_chooser

        # convert all sets -> lists
        d["used_questions"] = list(self.used_questions)
        d["submitted_lies"] = list(self.submitted_lies)
        d["lie_authors"] = {lie: list(sids) for lie, sids in self.lie_authors.items()}
        d["picks_submitted"] = list(self.picks_submitted)  # <— ADD THIS LINE

        # players need their own to_json()
        d["players"] = {sid: p.to_json() for sid, p in self.players.items()}

        return d


game = GameState()

def process_pick_truth(player: Player, choice: str):
    if player.sid in game.picks_submitted or game.phase != "pick_truth":
        return

    correct_answer = game.current_question["answer"]
    if choice == correct_answer:
        player.score += 1000 * game.round
    else:
        if choice in game.current_question.get("lies", []):
            player.score -= 500
        for sid in game.lie_authors.get(choice, set()):
            if sid != player.sid and sid in game.players:
                author = game.players[sid]
                author.score += 500 * game.round
                author.deceptions += 1
    game.picks_submitted.add(player.sid)

    # 🔑 NEW: if everybody’s picked, roll straight into likes
    if len(game.picks_submitted) >= len(game.players):
        move_to_likes()

def move_to_likes():
    if game.phase != "pick_truth":
        return
    log.info("[Game] Moving to likes ↦ scoreboard")
    game.phase = "likes"
    game.timer = None
    trigger_bots()

    def finish_likes():
        game.advance_phase()          # goes to scoreboard / next round
        socketio.emit("state", game.to_json())

    game.start_timer(5, finish_likes)  # 5‑second like window
    socketio.emit("state", game.to_json())

def auto_choose_category():
    if game.phase != "choose_category":
        return

    chooser = game.players.get(game.current_chooser)
    if not chooser:
        return   # no players?

    # If bot, choose right away (or after a tiny half‑second for UI polish)
    if chooser.is_bot:
        socketio.sleep(0.5)
        chosen = random.choice(game.current_categories)
        log.info("[Bot‑Chooser] %s auto‑picked %s", chooser.name, chosen)
        game.next_question_by_category(chosen)
        socketio.emit("state", game.to_json())
        return

    # Human didn’t pick in time → auto‑pick
    chosen = random.choice(game.current_categories)
    log.info("[Timer] %s didn't pick – auto‑choosing %s", chooser.name, chosen)
    game.next_question_by_category(chosen)
    socketio.emit("state", game.to_json())

def human_lie_quota_met() -> bool:
    """Return True when every human player has submitted a lie."""
    human_sids = {sid for sid, p in game.players.items() if not p.is_bot}
    # if there are no humans, quota is satisfied immediately
    if not human_sids:
        return True
    human_lies = human_sids.intersection(game.submitted_lies)
    return len(human_lies) >= len(human_sids)

def force_move_to_pick_truth():
    if game.phase != "submit_lie":
        return
    log.info("[Game] submit_lie timer expired → forcing pick_truth phase")
    game.options.append(game.current_question["answer"])
    random.shuffle(game.options)
    game.phase = "pick_truth"
    game.timer = None
    game.start_timer(30, move_to_likes)
    trigger_bots()
    socketio.emit("state", game.to_json())

def trigger_bots():
    bots = [p for p in game.players.values() if p.is_bot]
    phase = game.phase
    question = game.current_question
    if not bots:
        return

    def delayed_bot_task(delay_seconds, task_fn):
        socketio.sleep(delay_seconds)
        task_fn()

    def bot_task():
        if phase == "choose_category":
            # If the current chooser is a bot, let them pick right away
            chooser_sid = game.current_chooser
            if chooser_sid and chooser_sid in game.players:
                chooser = game.players[chooser_sid]
                if chooser.is_bot and game.current_categories:
                    chosen = random.choice(game.current_categories)
                    log.info("[Bot‑Chooser] %s picked category: %s", chooser.name, chosen)
                    game.next_question_by_category(chosen)
                    socketio.emit("state", game.to_json())
        elif phase == "submit_lie" and question:
                # --- make each bot invent (or steal) a lie -------------------------
                for bot in bots:
                    if bot.sid in game.submitted_lies:
                        continue  # ✅ Already lied

                    pool = [l for l in question.get("lies", [])
                            if l.lower() != question["answer"].lower()
                            and l not in game.options]

                    if not pool:
                        log.warning("[Bot] No available JSON lies for question: %s", question["question"])
                        return  # don’t submit a fallback lie

                    lie = random.choice(pool)


                    game.options.append(lie)
                    game.submitted_lies.add(bot.sid)
                    game.lie_authors.setdefault(lie, set()).add(bot.sid)
                    log.info("[Bot] %s submitted lie: %s", bot.name, lie)
        
                # ---- move on once *human* quota is satisfied ----------------------
                total_humans = [p for p in game.players.values() if not p.is_bot]
                if human_lie_quota_met():
                    game.options.append(question["answer"])
                    random.shuffle(game.options)
                    game.phase = "pick_truth"
                    game.timer = None
                    game.start_timer(30, move_to_likes)
                    trigger_bots()
                socketio.emit("state", game.to_json())
        elif phase == "pick_truth" and question:
            game.options = list(set(game.options or [])) or question["lies"] + [question["answer"]]
            for bot in bots:
                choice = random.choice(game.options)
                log.info("[Bot] %s picked: %s", bot.name, choice)
                process_pick_truth(bot, choice)          # <— direct, no emit!
            socketio.emit("state", game.to_json())
        elif phase == "likes" and question:
            answer = question["answer"]
            all_options = list(set(game.options or []).union({answer}))

            for bot in bots:
                # pick one thing to like (anything except your own lie)
                pool = [
                    val for val in all_options
                    if val not in game.lie_authors or bot.sid not in game.lie_authors[val]
                ]
                if not pool:
                    continue  # nothing safe to like
                val = random.choice(pool)

                # give credit to any player(s) who authored this lie
                if val == answer:
                    log.info("[Like] %s (bot) liked the truth: %s", bot.name, val)
                elif val in game.lie_authors:
                    for sid in game.lie_authors[val]:
                        game.players[sid].likes += 1
                        log.info("[Like] %s (bot) liked %s's lie: %s", bot.name, game.players[sid].name, val)
            socketio.emit("state", game.to_json())



    socketio.start_background_task(lambda: delayed_bot_task(0.5, bot_task))

@socketio.on("connect")
def on_connect(auth=None):          # auth may be None depending on client
    emit("state", game.to_json())

@socketio.on("join")
def on_join(data):
    name = data.get("name") or f"Player {len(game.players)+1}"
    p = Player(sid=request.sid, name=name)
    game.players[p.sid] = p
    log.info("[Join] %s", name)
    emit("joined", p.to_json())
    socketio.emit("state", game.to_json())

@socketio.on("choose_category")
def on_choose_category(data):
    # 🔒 Only the chosen player can select a category
    if request.sid != game.current_chooser:
        log.warning("[Choose] %s tried to pick but is not the chooser", request.sid)
        return

    category = data.get("category")
    if game.phase != "choose_category":
        log.warning("[Choose] Ignored — not in choose_category phase")
        return
    if not category or category not in game.current_categories:
        log.warning("[Choose] Invalid category: %s", category)
        return
    success = game.next_question_by_category(category)
    if success:
        game.current_chooser = None  # ✅ Reset chooser after successful pick
        socketio.emit("state", game.to_json())
        trigger_bots()
        log.info("[Choose] %s selected", category)

@socketio.on("submit_lie")
def on_submit_lie(data):
    player = game.players.get(request.sid)
    if not player or game.phase != "submit_lie":
        return

    if player.sid in game.submitted_lies:
        log.info("[Lie Reject] %s tried to submit more than one lie", player.name)
        return

    lie = data.get("lie", "").strip()
    correct = game.current_question["answer"].strip().lower()

    # Handle "Lie for Me"
    if not lie:
        pool = [l for l in game.current_question.get("lies", [])
                if l.lower() != correct
                and l not in game.options]
        if not pool:
            log.warning("[Lie-for-Me] No fallback lies available in JSON.")
            return  # Fail silently (or emit error if you prefer)
        lie = random.choice(pool)
        log.info("[Lie-for-Me] %s assigned: %s", player.name, lie)

    if lie.lower() == correct:
        log.info("[Lie Reject] %s tried to submit the truth!", player.name)
        emit("error", {"message": "You can't submit the truth!"})
        return

    # Accept the lie
    game.options.append(lie)
    game.submitted_lies.add(player.sid)
    game.lie_authors.setdefault(lie, set()).add(player.sid)
    log.info("[Lie] %s submitted: %s", player.name, lie)

    # 🚀 Move on if all human lies are in
    if human_lie_quota_met():
        if game.current_question:
            game.options.append(game.current_question["answer"])
        random.shuffle(game.options)
        game.phase = "pick_truth"
        game.start_timer(30, move_to_likes)
        trigger_bots()
        log.info("[Game] All human lies in → moving to pick_truth")

    socketio.emit("state", game.to_json())


@socketio.on("pick_truth")
def on_pick_truth(data):
    player = game.players.get(request.sid)
    choice = (data or {}).get("choice")
    if not player or not choice or choice not in game.options:
        return
    process_pick_truth(player, choice)
    socketio.emit("state", game.to_json())

@socketio.on("like")
def on_like(data):
    # 🔑 allow likes during pick_truth *or* likes
    if game.phase not in ("pick_truth", "likes"):
        return

    player = game.players.get(request.sid)
    if not player or player.sid not in game.picks_submitted:
        # Must have already guessed before liking
        return

    liked_vals = set(data.get("liked", []))
    for val in liked_vals:
        # no self‑likes & must be a valid lie/answer
        if val not in game.options or player.sid in game.lie_authors.get(val, set()):
            continue

        for sid in game.lie_authors.get(val, []):
            game.players[sid].likes += 1
            log.info("[Like] %s liked %s's lie: %s",
                     player.name, game.players[sid].name, val)

    socketio.emit("state", game.to_json())

@socketio.on("disconnect")
def on_disconnect():
    if request.sid in game.players:
        name = game.players[request.sid].name
        del game.players[request.sid]
        log.info("[Leave] %s", name)
        socketio.emit("state", game.to_json())

@app.get("/api/state")
def api_state():
    return jsonify(game.to_json())

@app.post("/api/next_question")
def api_next_question():
    game.next_question()
    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/advance_phase")
def api_advance_phase():
    game.advance_phase()
    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/reset")
def api_reset():
    game.reset()
    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/update_player_stats")
def api_update_player_stats():
    data = request.json or {}
    updates = data.get("players", {})
    for sid, fields in updates.items():
        if sid in game.players:
            player = game.players[sid]
            player.score = fields.get("score", player.score)
            player.likes = fields.get("likes", player.likes)
            player.deceptions = fields.get("deceptions", player.deceptions)
    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/add_bot")
def api_add_bot():
    name = request.json.get("name") if request.is_json else None
    name = name or f"Bot {len(game.players)+1}"
    sid = f"bot_{len(game.players)+1}"
    if sid in game.players:
        return (f"Bot with sid {sid} already exists", 400)
    game.players[sid] = Player(sid=sid, name=name, is_bot=True)
    log.info("[Debug] Added bot: %s", name)
    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/start_game")
def api_start_game():
    log.info("[API] /api/start_game called — phase=%s, players=%d",
             game.phase, len(game.players))
    if len(game.players) < 2:
        log.info("[API] aborting start — not enough players")
        return jsonify({"error": "At least 2 players required"}), 400

    # Delegate to the new helper
    game.start_game()
    log.info("[API] after start_game() → phase=%s", game.phase)

    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/reset_player/<sid>")
def api_reset_player(sid):
    player = game.players.get(sid)
    if not player:
        return jsonify({"error": "Player not found"}), 404
    player.score = 0
    player.likes = 0
    player.deceptions = 0
    log.info("[Debug] Reset stats for %s", player.name)
    socketio.emit("state", game.to_json())
    return ("", 204)

@app.post("/api/remove_player/<sid>")
def api_remove_player(sid):
    if sid in game.players:
        log.info("[Debug] Removed player: %s", game.players[sid].name)
        del game.players[sid]
        socketio.emit("state", game.to_json())
        return ("", 204)
    return jsonify({"error": "Player not found"}), 404

@app.get("/debug")
def debug_console():
    return render_template("debug.html")

from flask import redirect

@app.get("/")
def root():
    return redirect("/host")

@app.get("/host")
def host_page():
    return render_template("host.html")

@app.get("/player")
def player_page():
    return render_template("player.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 1337))
    log.info("Server live on http://0.0.0.0:%s (room code at /host)", port)
    socketio.run(app, host="0.0.0.0", port=port)
