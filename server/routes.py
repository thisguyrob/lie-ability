from __future__ import annotations
import uuid

from flask import Blueprint, jsonify, request

from server import game_state_lock, socketio
from server.game import (
    GameState,
    active_players,
    advance_turn,
    all_appeal_votes_done,
    all_likes_done,
    all_votes_cast,
    all_lies_submitted,
    cast_appeal_vote,
    cast_like,
    cast_vote,
    compute_scores,
    file_appeal,
    finalize_answers,
    finalize_likes,
    finalize_votes,
    get_game,
    mark_likes_done,
    reset_game,
    resolve_all_pending_appeals,
    sanitize_state,
    setup_turn,
    start_game,
    submit_lie,
    current_picker,
    _eligible_appeal_voters,
)
from server.db import (
    get_categories,
    get_groups,
    get_random_question,
    mark_questions_used,
)
from server.embeddings import is_too_similar
from server.timers import set_phase_deadline, start_phase_timer

bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_state(game: GameState) -> None:
    socketio.emit("game_state", sanitize_state(game))


def _error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _stop_phase_clock(game: GameState) -> None:
    stopped_phase = game.phase
    game.phase_deadline = None
    game.phase_token += 1
    socketio.emit("timer_stop", {"phase": stopped_phase})


def _advance_to_voting(game: GameState) -> None:
    finalize_answers(game)
    set_phase_deadline(game, "voting")
    socketio.emit("phase_change", {"phase": "voting", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
    start_phase_timer(game, lambda: _force_advance_voting(game))
    _emit_state(game)


def _force_advance_voting(game: GameState) -> None:
    with game_state_lock:
        if game.phase != "voting":
            return
        finalize_votes(game)
        set_phase_deadline(game, "likes")
        socketio.emit("phase_change", {"phase": "likes", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
        start_phase_timer(game, lambda: _force_advance_likes(game))
    _emit_state(game)


def _force_advance_likes(game: GameState) -> None:
    with game_state_lock:
        if game.phase != "likes":
            return
        # Mark all still-active players as done
        for p in active_players(game):
            p.has_liked = True
        finalize_likes(game)
        set_phase_deadline(game, "round_results")
        socketio.emit("phase_change", {"phase": "round_results", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
        socketio.emit("round_results", sanitize_state(game)["current_turn"])
        start_phase_timer(game, lambda: _force_advance_results(game))
    _emit_state(game)


def _force_advance_results(game: GameState) -> None:
    with game_state_lock:
        if game.phase != "round_results":
            return
        turn = game.current_round.current_turn if game.current_round else None
        if turn and turn.appeals:
            game.phase = "appeal_vote"
            game.phase_token += 1
            set_phase_deadline(game, "appeal_vote")
            socketio.emit("phase_change", {"phase": "appeal_vote", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
            start_phase_timer(game, lambda: _force_advance_appeal_vote(game))
        else:
            _do_advance_turn(game)
    _emit_state(game)


def _force_advance_appeal_vote(game: GameState) -> None:
    with game_state_lock:
        if game.phase != "appeal_vote":
            return
        resolve_all_pending_appeals(game)
        _do_advance_turn(game)
    _emit_state(game)


def _do_advance_turn(game: GameState) -> None:
    turn = game.current_round.current_turn if game.current_round else None
    if turn:
        mark_questions_used([turn.question_id] if turn.question_id else [])
    next_phase = advance_turn(game)
    if next_phase != "game_over":
        set_phase_deadline(game, "category_pick")
        start_phase_timer(game, lambda: _force_advance_category_pick(game))
    socketio.emit("phase_change", {"phase": next_phase, "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})


def _force_advance_category_pick(game: GameState) -> None:
    with game_state_lock:
        if game.phase != "category_pick":
            return
        cats = get_categories(game.included_groups)
        if not cats:
            return
        import random
        chosen_cat = random.choice(cats)
        _do_setup_turn(game, chosen_cat["id"], chosen_cat["name"])
    _emit_state(game)


def _do_setup_turn(game: GameState, category_id: int, category_name: str) -> None:
    histories = [p.question_history for p in active_players(game)]
    q = get_random_question(category_id, game.used_question_ids, histories, game.included_groups)
    if not q:
        # No questions left in category — pick a random one from any category
        cats = get_categories(game.included_groups)
        import random
        for cat in random.sample(cats, len(cats)):
            q = get_random_question(cat["id"], game.used_question_ids, histories, game.included_groups)
            if q:
                category_id = cat["id"]
                category_name = cat["name"]
                break
    if not q:
        return

    setup_turn(
        game,
        category_id=category_id,
        category_name=category_name,
        question_id=q["id"],
        question_prompt=q["prompt"],
        real_answer_text=q["answer"],
        bot_lies=q.get("lies", []),
    )
    set_phase_deadline(game, "lie_submission")
    socketio.emit("phase_change", {"phase": "lie_submission", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
    start_phase_timer(game, lambda: _force_advance_voting(game))


# ---------------------------------------------------------------------------
# Player endpoints
# ---------------------------------------------------------------------------

@bp.route("/players", methods=["POST"])
def join_game():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _error("name is required")

    game = get_game()
    with game_state_lock:
        if game.phase != "lobby":
            return _error("Game already in progress", 403)

        player_id = str(uuid.uuid4())
        from server.game import Player
        player = Player(
            player_id=player_id,
            name=name,
            avatar_emoji=data.get("avatar_emoji", "😊"),
            avatar_bg_color=data.get("avatar_bg_color", "#4A90D9"),
            question_history=data.get("question_history", {}),
        )
        game.players[player_id] = player
        game.player_order.append(player_id)
        state = sanitize_state(game)

    _emit_state(game)
    return jsonify({"player_id": player_id, "player": {
        "player_id": player_id,
        "name": player.name,
        "avatar_emoji": player.avatar_emoji,
        "avatar_bg_color": player.avatar_bg_color,
    }})


@bp.route("/players/rejoin", methods=["POST"])
def rejoin_game():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    game = get_game()

    with game_state_lock:
        player = game.players.get(player_id)
        if not player:
            return _error("Player not found — join as a new player", 404)
        player.connected = True
        # Update history from cookie if provided
        if "question_history" in data:
            player.question_history = data["question_history"]
        state = sanitize_state(game)

    _emit_state(game)
    return jsonify({"player_id": player_id, "state": state})


@bp.route("/players/<player_id>", methods=["PATCH"])
def update_player(player_id: str):
    data = request.get_json(force=True, silent=True) or {}
    game = get_game()
    with game_state_lock:
        player = game.players.get(player_id)
        if not player:
            return _error("Player not found", 404)
        if "name" in data:
            player.name = data["name"].strip() or player.name
        if "avatar_emoji" in data:
            player.avatar_emoji = data["avatar_emoji"]
        if "avatar_bg_color" in data:
            player.avatar_bg_color = data["avatar_bg_color"]
        state = sanitize_state(game)

    _emit_state(game)
    return jsonify({"player": {
        "player_id": player.player_id,
        "name": player.name,
        "avatar_emoji": player.avatar_emoji,
        "avatar_bg_color": player.avatar_bg_color,
    }})


# ---------------------------------------------------------------------------
# Game control
# ---------------------------------------------------------------------------

@bp.route("/game/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    game = get_game()
    with game_state_lock:
        if game.phase != "lobby":
            return _error("Game already started")
        active = active_players(game)
        if len(active) < 2:
            return _error("Need at least 2 players to start")
        included_groups = data.get("included_groups") or None
        game.included_groups = included_groups
        start_game(game)
        set_phase_deadline(game, "category_pick")
        start_phase_timer(game, lambda: _force_advance_category_pick(game))
        socketio.emit("phase_change", {"phase": "category_pick", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
        state = sanitize_state(game)

    _emit_state(game)
    return jsonify({"status": "started", "state": state})


@bp.route("/game/state", methods=["GET"])
def game_state():
    game = get_game()
    return jsonify(sanitize_state(game))


@bp.route("/game/reset", methods=["POST"])
def game_reset():
    game = reset_game()
    _emit_state(game)
    return jsonify({"status": "reset"})


# ---------------------------------------------------------------------------
# Categories / groups
# ---------------------------------------------------------------------------

@bp.route("/categories", methods=["GET"])
def categories():
    game = get_game()
    cats = get_categories(game.included_groups)
    return jsonify(cats)


@bp.route("/groups", methods=["GET"])
def groups():
    return jsonify(get_groups())


# ---------------------------------------------------------------------------
# Category pick
# ---------------------------------------------------------------------------

@bp.route("/game/category", methods=["POST"])
def pick_category():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    category_id = data.get("category_id")
    game = get_game()

    with game_state_lock:
        if game.phase != "category_pick":
            return _error("Not in category pick phase")
        picker = current_picker(game)
        if not picker or picker.player_id != player_id:
            return _error("It's not your turn to pick", 403)
        if category_id is None:
            return _error("category_id is required")

        cats = {c["id"]: c["name"] for c in get_categories(game.included_groups)}
        if category_id not in cats:
            return _error("Invalid category_id")

        _do_setup_turn(game, int(category_id), cats[int(category_id)])

    _emit_state(game)
    return jsonify({"status": "ok", "phase": "lie_submission"})


# ---------------------------------------------------------------------------
# Lie submission
# ---------------------------------------------------------------------------

@bp.route("/game/lie", methods=["POST"])
def submit_lie_route():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    text = (data.get("text") or "").strip()
    game = get_game()

    with game_state_lock:
        if game.phase != "lie_submission":
            return _error("Not in lie submission phase")
        player = game.players.get(player_id)
        if not player or not player.connected:
            return _error("Player not found", 404)
        if player.has_submitted_lie:
            return _error("Already submitted a lie")
        if not text:
            return _error("Lie text cannot be empty")

        turn = game.current_round.current_turn
        if is_too_similar(text, turn.real_answer_text):
            return _error("That's too close to the real answer — try again!")

        submit_lie(game, player_id, text)
        done = all_lies_submitted(game)
        if done:
            _stop_phase_clock(game)
            _advance_to_voting(game)

    if not done:
        _emit_state(game)
    return jsonify({"status": "submitted"})


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

@bp.route("/game/vote", methods=["POST"])
def vote():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    answer_id = data.get("answer_id", "")
    game = get_game()

    votes_done = False
    likes_done = False

    with game_state_lock:
        if game.phase != "voting":
            return _error("Not in voting phase")
        player = game.players.get(player_id)
        if not player or not player.connected:
            return _error("Player not found", 404)
        if player.has_voted:
            return _error("Already voted")

        turn = game.current_round.current_turn
        answer = next((a for a in turn.answers if a.answer_id == answer_id), None)
        if not answer:
            return _error("Invalid answer_id")
        if answer.author_id == player_id:
            return _error("You cannot vote for your own lie")

        cast_vote(game, player_id, answer_id)
        votes_done = all_votes_cast(game)
        if votes_done:
            finalize_votes(game)
            likes_done = all_likes_done(game)
            if not likes_done:
                set_phase_deadline(game, "likes")
                socketio.emit("phase_change", {"phase": "likes", "deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None})
                start_phase_timer(game, lambda: _force_advance_likes(game))

    if votes_done and likes_done:
        _force_advance_likes(game)
        return jsonify({"status": "voted"})

    _emit_state(game)
    return jsonify({"status": "voted"})


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

@bp.route("/game/like", methods=["POST"])
def like():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    answer_id = data.get("answer_id", "")
    game = get_game()

    with game_state_lock:
        if game.phase not in ("voting", "likes"):
            return _error("Not in a phase that allows likes")
        player = game.players.get(player_id)
        if not player or not player.connected:
            return _error("Player not found", 404)
        if not player.has_voted:
            return _error("You must vote before liking an answer")
        if player.has_liked:
            return _error("Already liked an answer")

        turn = game.current_round.current_turn
        answer = next((a for a in turn.answers if a.answer_id == answer_id), None)
        if not answer:
            return _error("Invalid answer_id")
        if answer.author_id == player_id:
            return _error("You cannot like your own answer")
        if player_id in answer.liked_by:
            return _error("Already liked this answer")

        cast_like(game, player_id, answer_id)
        mark_likes_done(game, player_id)
        done = all_likes_done(game)

    # _force_advance_likes acquires game_state_lock itself, so call after releasing
    if done:
        _force_advance_likes(game)
        return jsonify({"status": "liked"})

    _emit_state(game)
    return jsonify({"status": "liked"})


# ---------------------------------------------------------------------------
# Appeals
# ---------------------------------------------------------------------------

@bp.route("/game/appeal", methods=["POST"])
def appeal():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    answer_id = data.get("answer_id", "")
    game = get_game()

    with game_state_lock:
        if game.phase != "round_results":
            return _error("Appeals can only be filed during round results")
        player = game.players.get(player_id)
        if not player:
            return _error("Player not found", 404)

        turn = game.current_round.current_turn
        answer = next((a for a in turn.answers if a.answer_id == answer_id), None)
        if not answer:
            return _error("Invalid answer_id")
        if answer.is_real:
            return _error("Cannot appeal the real answer")
        if any(a.answer_id == answer_id for a in turn.appeals):
            return _error("This answer has already been appealed")

        appeal_obj = file_appeal(game, player_id, answer_id)

    _emit_state(game)
    return jsonify({"status": "appeal_filed", "appeal_id": appeal_obj.appeal_id})


@bp.route("/game/appeal/vote", methods=["POST"])
def appeal_vote():
    data = request.get_json(force=True, silent=True) or {}
    player_id = data.get("player_id", "")
    appeal_id = data.get("appeal_id", "")
    accept = bool(data.get("accept", False))
    game = get_game()

    with game_state_lock:
        if game.phase != "appeal_vote":
            return _error("Not in appeal vote phase")
        player = game.players.get(player_id)
        if not player or not player.connected:
            return _error("Player not found", 404)

        eligible = _eligible_appeal_voters(game)
        if player_id not in eligible:
            return _error("Only players who guessed correctly may vote on appeals", 403)

        turn = game.current_round.current_turn
        appeal_obj = next((a for a in turn.appeals if a.appeal_id == appeal_id), None)
        if not appeal_obj:
            return _error("Invalid appeal_id")
        if appeal_obj.resolved:
            return _error("This appeal has already been resolved")
        already_voted = player_id in appeal_obj.votes_accept or player_id in appeal_obj.votes_reject
        if already_voted:
            return _error("Already voted on this appeal")

        cast_appeal_vote(game, player_id, appeal_id, accept)

        if all_appeal_votes_done(game):
            resolve_all_pending_appeals(game)
            _do_advance_turn(game)

    _emit_state(game)
    return jsonify({"status": "vote_cast"})


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

@bp.route("/game/scores", methods=["GET"])
def scores():
    game = get_game()
    sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
    return jsonify([
        {
            "player_id": p.player_id,
            "name": p.name,
            "score": p.score,
            "likes_received": p.likes_received,
        }
        for p in sorted_players
    ])
