from __future__ import annotations
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from server.embeddings import normalize_answer_text

CORRECT_GUESS_BASE = 1000
FOOLED_BASE = 500

ROUND_CONFIG = [
    {"round_number": 1, "score_multiplier": 1, "questions_in_round": 8},
    {"round_number": 2, "score_multiplier": 2, "questions_in_round": 8},
    {"round_number": 3, "score_multiplier": 3, "questions_in_round": 1},
]

MIN_ANSWER_OPTIONS = 3


@dataclass
class Player:
    player_id: str
    name: str
    avatar_emoji: str
    avatar_bg_color: str
    question_history: dict[str, str] = field(default_factory=dict)  # question_id → "correct"|"incorrect"
    score: int = 0
    likes_received: int = 0
    connected: bool = True
    has_submitted_lie: bool = False
    has_voted: bool = False
    has_liked: bool = False


@dataclass
class Answer:
    answer_id: str
    text: str
    author_id: Optional[str]   # None for real answer and bot fill-ins
    is_real: bool = False
    is_bot: bool = False        # True for pre-written fill-in lies
    vote_count: int = 0
    likes: int = 0
    voted_by: list[str] = field(default_factory=list)
    liked_by: list[str] = field(default_factory=list)


@dataclass
class Appeal:
    appeal_id: str
    answer_id: str
    filed_by: str               # player_id
    votes_accept: list[str] = field(default_factory=list)
    votes_reject: list[str] = field(default_factory=list)
    resolved: bool = False
    approved: bool = False


@dataclass
class Turn:
    turn_number: int
    active_player_id: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    question_id: Optional[int] = None
    question_prompt: Optional[str] = None
    real_answer_text: Optional[str] = None
    real_answer_id: Optional[str] = None
    answers: list[Answer] = field(default_factory=list)
    score_changes: dict[str, int] = field(default_factory=dict)
    appeals: list[Appeal] = field(default_factory=list)


@dataclass
class Round:
    round_number: int
    score_multiplier: int
    questions_in_round: int
    turns_completed: int = 0
    current_turn: Optional[Turn] = None


@dataclass
class GameState:
    phase: str = "lobby"
    players: dict[str, Player] = field(default_factory=dict)
    player_order: list[str] = field(default_factory=list)
    current_round: Optional[Round] = None
    active_player_index: int = 0
    used_question_ids: set[int] = field(default_factory=set)
    included_groups: Optional[list[str]] = None
    phase_deadline: Optional[datetime] = None
    phase_token: int = 0


# Module-level singleton
_game: GameState = GameState()


def get_game() -> GameState:
    return _game


def reset_game() -> GameState:
    global _game
    _game = GameState()
    return _game


# ---------------------------------------------------------------------------
# Player helpers
# ---------------------------------------------------------------------------

def active_players(game: GameState) -> list[Player]:
    return [game.players[pid] for pid in game.player_order if pid in game.players and game.players[pid].connected]


def active_player_ids(game: GameState) -> list[str]:
    return [p.player_id for p in active_players(game)]


def current_picker(game: GameState) -> Optional[Player]:
    order = game.player_order
    if not order:
        return None
    idx = game.active_player_index % len(order)
    pid = order[idx]
    return game.players.get(pid)


def advance_picker(game: GameState) -> None:
    game.active_player_index = (game.active_player_index + 1) % max(len(game.player_order), 1)


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------

def all_lies_submitted(game: GameState) -> bool:
    return all(p.has_submitted_lie for p in active_players(game))


def all_votes_cast(game: GameState) -> bool:
    return all(p.has_voted for p in active_players(game))


def all_likes_done(game: GameState) -> bool:
    return all(p.has_liked for p in active_players(game))


def all_appeal_votes_done(game: GameState) -> bool:
    turn = game.current_round and game.current_round.current_turn
    if not turn:
        return True
    eligible = _eligible_appeal_voters(game)
    for appeal in turn.appeals:
        if appeal.resolved:
            continue
        voted = set(appeal.votes_accept) | set(appeal.votes_reject)
        if not eligible or eligible.issubset(voted):
            continue
        return False
    return True


def _eligible_appeal_voters(game: GameState) -> set[str]:
    turn = game.current_round and game.current_round.current_turn
    if not turn or not turn.real_answer_id:
        return set()
    real_answer = next((a for a in turn.answers if a.answer_id == turn.real_answer_id), None)
    if not real_answer:
        return set()
    return set(real_answer.voted_by) & set(active_player_ids(game))


# ---------------------------------------------------------------------------
# Game start
# ---------------------------------------------------------------------------

def start_game(game: GameState) -> None:
    game.used_question_ids = set()
    game.active_player_index = 0
    game.current_round = Round(**{k: v for k, v in ROUND_CONFIG[0].items()})
    game.phase = "category_pick"
    game.phase_token += 1
    _reset_per_turn_player_flags(game)


def _reset_per_turn_player_flags(game: GameState) -> None:
    for p in game.players.values():
        p.has_submitted_lie = False
        p.has_voted = False
        p.has_liked = False


# ---------------------------------------------------------------------------
# Category / question setup
# ---------------------------------------------------------------------------

def setup_turn(game: GameState, category_id: int, category_name: str,
               question_id: int, question_prompt: str, real_answer_text: str,
               bot_lies: list[str]) -> None:
    rnd = game.current_round
    turn_number = rnd.turns_completed + 1
    picker = current_picker(game)

    turn = Turn(
        turn_number=turn_number,
        active_player_id=picker.player_id if picker else "",
        category_id=category_id,
        category_name=category_name,
        question_id=question_id,
        question_prompt=question_prompt,
        real_answer_text=real_answer_text,
    )

    real_answer = Answer(
        answer_id=str(uuid.uuid4()),
        text=real_answer_text,
        author_id=None,
        is_real=True,
    )
    turn.real_answer_id = real_answer.answer_id
    turn.answers = [real_answer]

    # bot fill-ins stored but not shuffled in until lie_submission ends
    turn._bot_lies = bot_lies  # type: ignore[attr-defined]

    rnd.current_turn = turn
    game.used_question_ids.add(question_id)
    game.phase = "lie_submission"
    game.phase_token += 1
    _reset_per_turn_player_flags(game)


# ---------------------------------------------------------------------------
# Lie submission
# ---------------------------------------------------------------------------

def submit_lie(game: GameState, player_id: str, text: str) -> None:
    turn = game.current_round.current_turn
    answer = Answer(
        answer_id=str(uuid.uuid4()),
        text=text,
        author_id=player_id,
    )
    turn.answers.append(answer)
    game.players[player_id].has_submitted_lie = True


def finalize_answers(game: GameState) -> None:
    turn = game.current_round.current_turn
    bot_lies: list[str] = getattr(turn, "_bot_lies", [])  # type: ignore[attr-defined]
    active = active_players(game)

    # Pad with bot lies if needed
    player_submissions = [a for a in turn.answers if not a.is_real and not a.is_bot]
    total = len(player_submissions) + 1  # +1 for real answer
    needed = max(0, MIN_ANSWER_OPTIONS - total)
    for lie_text in bot_lies[:needed]:
        turn.answers.append(Answer(
            answer_id=str(uuid.uuid4()),
            text=lie_text,
            author_id=None,
            is_bot=True,
        ))

    # Shuffle
    random.shuffle(turn.answers)
    game.phase = "voting"
    game.phase_token += 1


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

def cast_vote(game: GameState, player_id: str, answer_id: str) -> None:
    turn = game.current_round.current_turn
    answer = _get_answer(turn, answer_id)
    answer.vote_count += 1
    answer.voted_by.append(player_id)
    game.players[player_id].has_voted = True


def finalize_votes(game: GameState) -> None:
    game.phase = "likes"
    game.phase_token += 1


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

def cast_like(game: GameState, player_id: str, answer_id: str) -> None:
    turn = game.current_round.current_turn
    answer = _get_answer(turn, answer_id)
    answer.likes += 1
    answer.liked_by.append(player_id)
    author = game.players.get(answer.author_id) if answer.author_id else None
    if author:
        author.likes_received += 1


def mark_likes_done(game: GameState, player_id: str) -> None:
    game.players[player_id].has_liked = True


def finalize_likes(game: GameState) -> None:
    compute_scores(game)
    game.phase = "round_results"
    game.phase_token += 1


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_scores(game: GameState) -> None:
    rnd = game.current_round
    turn = rnd.current_turn
    multiplier = rnd.score_multiplier
    score_changes: dict[str, int] = {}

    real_answer = next(a for a in turn.answers if a.is_real)

    for voter_id in real_answer.voted_by:
        delta = CORRECT_GUESS_BASE * multiplier
        game.players[voter_id].score += delta
        score_changes[voter_id] = score_changes.get(voter_id, 0) + delta

    for answer in turn.answers:
        if answer.is_real or answer.is_bot or answer.author_id is None:
            continue
        for _ in answer.voted_by:
            delta = FOOLED_BASE * multiplier
            game.players[answer.author_id].score += delta
            score_changes[answer.author_id] = score_changes.get(answer.author_id, 0) + delta

    turn.score_changes = score_changes


# ---------------------------------------------------------------------------
# Appeals
# ---------------------------------------------------------------------------

def file_appeal(game: GameState, player_id: str, answer_id: str) -> Appeal:
    turn = game.current_round.current_turn
    appeal = Appeal(
        appeal_id=str(uuid.uuid4()),
        answer_id=answer_id,
        filed_by=player_id,
    )
    turn.appeals.append(appeal)
    return appeal


def cast_appeal_vote(game: GameState, player_id: str, appeal_id: str, accept: bool) -> Appeal:
    turn = game.current_round.current_turn
    appeal = next(a for a in turn.appeals if a.appeal_id == appeal_id)
    if accept:
        appeal.votes_accept.append(player_id)
    else:
        appeal.votes_reject.append(player_id)
    _try_resolve_appeal(game, appeal)
    return appeal


def _try_resolve_appeal(game: GameState, appeal: Appeal) -> None:
    eligible = _eligible_appeal_voters(game)
    voted = set(appeal.votes_accept) | set(appeal.votes_reject)

    if eligible and not eligible.issubset(voted):
        return  # not all eligible voters have weighed in

    # Resolve: majority wins; ties go to reject
    if not eligible:
        approved = True  # no correct guessers → auto-approve
    else:
        approved = len(appeal.votes_accept) > len(appeal.votes_reject)

    appeal.approved = approved
    appeal.resolved = True
    _apply_appeal_scores(game, appeal)


def _apply_appeal_scores(game: GameState, appeal: Appeal) -> None:
    rnd = game.current_round
    turn = rnd.current_turn
    multiplier = rnd.score_multiplier

    appealed_answer = _get_answer(turn, appeal.answer_id)

    if appeal.approved:
        # Voters of the appealed answer now get correct-guess points
        for voter_id in appealed_answer.voted_by:
            if voter_id not in game.players:
                continue
            delta = CORRECT_GUESS_BASE * multiplier
            game.players[voter_id].score += delta
            turn.score_changes[voter_id] = turn.score_changes.get(voter_id, 0) + delta
        # Author gets fooled points for each voter
        if appealed_answer.author_id and appealed_answer.author_id in game.players:
            author = game.players[appealed_answer.author_id]
            for _ in appealed_answer.voted_by:
                delta = FOOLED_BASE * multiplier
                author.score += delta
                turn.score_changes[author.player_id] = turn.score_changes.get(author.player_id, 0) + delta
    else:
        # Filer loses points
        if appeal.filed_by in game.players:
            penalty = CORRECT_GUESS_BASE * multiplier
            game.players[appeal.filed_by].score -= penalty
            turn.score_changes[appeal.filed_by] = turn.score_changes.get(appeal.filed_by, 0) - penalty


def resolve_all_pending_appeals(game: GameState) -> None:
    turn = game.current_round.current_turn
    for appeal in turn.appeals:
        if not appeal.resolved:
            # Force resolve with current votes
            eligible = _eligible_appeal_voters(game)
            approved = not eligible or len(appeal.votes_accept) > len(appeal.votes_reject)
            appeal.approved = approved
            appeal.resolved = True
            _apply_appeal_scores(game, appeal)


# ---------------------------------------------------------------------------
# Round / turn advancement
# ---------------------------------------------------------------------------

def advance_turn(game: GameState) -> str:
    rnd = game.current_round
    rnd.turns_completed += 1
    rnd.current_turn = None
    advance_picker(game)

    if rnd.turns_completed < rnd.questions_in_round:
        game.phase = "category_pick"
        game.phase_token += 1
        _reset_per_turn_player_flags(game)
        return "category_pick"

    # Advance to next macro-round
    next_round_idx = rnd.round_number  # 0-based index into ROUND_CONFIG
    if next_round_idx < len(ROUND_CONFIG):
        cfg = ROUND_CONFIG[next_round_idx]
        game.current_round = Round(**{k: v for k, v in cfg.items()})
        game.phase = "category_pick"
        game.phase_token += 1
        _reset_per_turn_player_flags(game)
        return "category_pick"

    game.phase = "game_over"
    game.phase_token += 1
    return "game_over"


# ---------------------------------------------------------------------------
# Sanitized state for broadcast
# ---------------------------------------------------------------------------

def sanitize_state(game: GameState) -> dict:
    rnd = game.current_round
    turn = rnd.current_turn if rnd else None

    base = {
        "phase": game.phase,
        "players": [_player_public(p) for p in (game.players[pid] for pid in game.player_order if pid in game.players)],
        "player_order": game.player_order,
        "active_player_id": current_picker(game).player_id if current_picker(game) else None,
        "phase_deadline_ts": game.phase_deadline.timestamp() if game.phase_deadline else None,
    }

    if rnd:
        base["round_number"] = rnd.round_number
        base["score_multiplier"] = rnd.score_multiplier
        base["questions_in_round"] = rnd.questions_in_round
        base["turns_completed"] = rnd.turns_completed

    if turn:
        base["current_turn"] = _sanitize_turn(game, turn)

    if game.phase == "game_over":
        sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
        most_liked = max(game.players.values(), key=lambda p: p.likes_received, default=None)
        base["final_scores"] = [_player_public(p) for p in sorted_players]
        base["most_liked_player"] = _player_public(most_liked) if most_liked else None

    return base


def _sanitize_turn(game: GameState, turn: Turn) -> dict:
    phase = game.phase
    d: dict = {
        "turn_number": turn.turn_number,
        "active_player_id": turn.active_player_id,
        "category_name": turn.category_name,
    }

    if phase in ("lie_submission", "voting", "likes", "round_results", "appeal_vote"):
        d["question_prompt"] = turn.question_prompt

    if phase == "lie_submission":
        active = active_players(game)
        d["submissions_received"] = sum(1 for p in active if p.has_submitted_lie)
        d["submissions_needed"] = len(active)

    elif phase == "voting":
        active = active_players(game)
        d["answers"] = [
            {
                "answer_id": a.answer_id,
                "text": a.text,
                "normalized_text": normalize_answer_text(a.text),
                "author_id": a.author_id,
            }
            for a in turn.answers
        ]
        d["votes_received"] = sum(1 for p in active if p.has_voted)
        d["votes_needed"] = len(active)

    elif phase == "likes":
        d["answers"] = [_answer_revealed(game, a) for a in turn.answers]

    elif phase in ("round_results", "appeal_vote", "game_over"):
        d["real_answer_text"] = turn.real_answer_text
        d["answers"] = [_answer_revealed(game, a) for a in turn.answers]
        d["score_changes"] = turn.score_changes
        if phase == "appeal_vote":
            eligible = _eligible_appeal_voters(game)
            d["appeals"] = [_appeal_public(a, eligible) for a in turn.appeals]

    return d


def _answer_revealed(game: GameState, answer: Answer) -> dict:
    author = game.players.get(answer.author_id) if answer.author_id else None
    return {
        "answer_id": answer.answer_id,
        "text": answer.text,
        "normalized_text": normalize_answer_text(answer.text),
        "author_id": answer.author_id,
        "author_name": author.name if author else None,
        "is_real": answer.is_real,
        "is_bot": answer.is_bot,
        "vote_count": answer.vote_count,
        "likes": answer.likes,
        "voted_by_names": [game.players[pid].name for pid in answer.voted_by if pid in game.players],
    }


def _appeal_public(appeal: Appeal, eligible: set[str]) -> dict:
    return {
        "appeal_id": appeal.appeal_id,
        "answer_id": appeal.answer_id,
        "filed_by": appeal.filed_by,
        "eligible_voters": list(eligible),
        "votes_accept": appeal.votes_accept,
        "votes_reject": appeal.votes_reject,
        "resolved": appeal.resolved,
        "approved": appeal.approved,
    }


def _player_public(p: Player) -> dict:
    return {
        "player_id": p.player_id,
        "name": p.name,
        "avatar_emoji": p.avatar_emoji,
        "avatar_bg_color": p.avatar_bg_color,
        "score": p.score,
        "likes_received": p.likes_received,
        "connected": p.connected,
    }


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _get_answer(turn: Turn, answer_id: str) -> Answer:
    answer = next((a for a in turn.answers if a.answer_id == answer_id), None)
    if answer is None:
        raise ValueError(f"answer_id {answer_id!r} not found")
    return answer
