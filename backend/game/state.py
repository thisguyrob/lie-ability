from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import Choice, Lobby, Phase


@dataclass
class GameState:
    """Mutable game state for one lobby."""

    lobby: Lobby
    round_count: int
    round_number: int = 0
    phase: Phase = "LOBBY"
    prompt_id: Optional[str] = None
    prompt_category: Optional[str] = None
    prompt_text: Optional[str] = None
    choices: List[Choice] = field(default_factory=list)
    lies: Dict[str, str] = field(default_factory=dict)
    votes: Dict[str, str] = field(default_factory=dict)
    scores: Dict[str, int] = field(default_factory=dict)
    deadline: float = 0.0

    def __post_init__(self) -> None:
        for p in self.lobby.players:
            self.scores[p.id] = 0


# ------------------ Prompt source ------------------
PROMPTS = [
    {
        "id": "p1",
        "category": "TRIVIA TIME",
        "text": "Mickey Mouse's middle name is _____.",
        "answer": "Theodore",
    },
    {
        "id": "p2",
        "category": "CELEBRITY TWEET",
        "text": "@realDonaldTrump: Who wouldn't take _____'s picture and make lots of money if she does the nude sunbathing thing?",
        "answer": "Kate Middleton",
    },
]


def get_prompt() -> dict:
    """Return a random prompt from the built-in list."""
    return random.choice(PROMPTS)


# ------------------ Scoring ------------------
TRUTH_POINTS = 500
FOOL_POINTS = 250
AUTO_LIE_PENALTY = 500


def compute_multiplier(round_number: int) -> int:
    return max(1, round_number)


# ------------------ Utility ------------------


def make_choice(text: str, author: Optional[str]) -> Choice:
    return Choice(id=str(uuid.uuid4()), text=text, author_id=author)
