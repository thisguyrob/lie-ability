from __future__ import annotations

import logging
import math
import re
from difflib import SequenceMatcher
from typing import Optional

import requests

LOGGER = logging.getLogger(__name__)

LM_STUDIO_URL = "http://localhost:1234"
EMBEDDING_MODEL = "text-embedding-nomic-embed-text-v2"
SIMILARITY_THRESHOLD = 0.75
_EMBED_TIMEOUT = 2.0

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_SCALE_WORDS = {"hundred": 100, "thousand": 1000}
_NUMBER_TOKEN_RE = re.compile(r"[a-z]+(?:-[a-z]+)*|\d+|[^\w\s]", re.IGNORECASE)


def is_too_similar(lie: str, truth: str) -> bool:
    normalized_lie = _normalize_text(lie)
    normalized_truth = _normalize_text(truth)
    heuristic_reason = _heuristic_too_similar(normalized_lie, normalized_truth)
    try:
        similarity = _embedding_similarity(normalized_lie, normalized_truth)
        result = similarity >= SIMILARITY_THRESHOLD or heuristic_reason is not None
        LOGGER.debug(
            "Embedding similarity check lie=%r truth=%r normalized_lie=%r normalized_truth=%r similarity=%.6f threshold=%.6f heuristic=%s result=%s",
            lie,
            truth,
            normalized_lie,
            normalized_truth,
            similarity,
            SIMILARITY_THRESHOLD,
            heuristic_reason or "none",
            result,
        )
        return result
    except Exception as exc:
        fallback = heuristic_reason is not None or normalized_lie == normalized_truth
        LOGGER.warning(
            "Embedding similarity check failed lie=%r truth=%r normalized_lie=%r normalized_truth=%r heuristic=%s fallback=%s error=%s",
            lie,
            truth,
            normalized_lie,
            normalized_truth,
            heuristic_reason or "none",
            fallback,
            exc,
        )
        return fallback


def normalize_answer_text(text: str) -> str:
    return _normalize_text(text)


def _embedding_similarity(a: str, b: str) -> float:
    url = f"{LM_STUDIO_URL}/v1/embeddings"
    resp = requests.post(
        url,
        json={"input": [a, b], "model": EMBEDDING_MODEL},
        timeout=_EMBED_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    vec_a = data[0]["embedding"]
    vec_b = data[1]["embedding"]
    return _cosine(vec_a, vec_b)


def _normalize_text(text: str) -> str:
    tokens = _NUMBER_TOKEN_RE.findall(text.lower())
    normalized: list[str] = []
    i = 0
    while i < len(tokens):
        replacement, consumed = _consume_number_tokens(tokens, i)
        if consumed:
            normalized.append(replacement)
            i += consumed
            continue
        token = tokens[i]
        if re.fullmatch(r"[^\w\s]", token):
            if normalized:
                normalized[-1] = normalized[-1].rstrip()
            normalized.append(token)
        else:
            normalized.append(token)
        i += 1
    text = " ".join(normalized)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _heuristic_too_similar(a: str, b: str) -> Optional[str]:
    if a == b:
        return "exact-normalized-match"

    tokens_a = _word_tokens(a)
    tokens_b = _word_tokens(b)
    if not tokens_a or not tokens_b:
        return None

    if _token_subset_match(tokens_a, tokens_b):
        return "token-subset-match"
    if _fuzzy_token_subset_match(tokens_a, tokens_b):
        return "fuzzy-token-subset-match"
    return None


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _token_subset_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    shorter, longer = sorted((tokens_a, tokens_b), key=len)
    return len(shorter) < len(longer) and all(token in longer for token in shorter)


def _fuzzy_token_subset_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    shorter, longer = sorted((tokens_a, tokens_b), key=len)
    if len(shorter) >= len(longer):
        return False
    matched = []
    for token in shorter:
        ratios = [SequenceMatcher(None, token, candidate).ratio() for candidate in longer]
        best_ratio = max(ratios, default=0.0)
        if best_ratio < 0.88:
            return False
        matched.append(best_ratio)
    return max(matched, default=0.0) >= 0.9


def _consume_number_tokens(tokens: list[str], start: int) -> tuple[str, int]:
    raw_parts: list[str] = []
    i = start
    while i < len(tokens):
        token = tokens[i]
        if token == "and" and raw_parts:
            raw_parts.append(token)
            i += 1
            continue
        if token in _NUMBER_WORDS or token in _SCALE_WORDS or "-" in token:
            split_parts = token.split("-")
            if all(part in _NUMBER_WORDS for part in split_parts):
                raw_parts.extend(split_parts)
                i += 1
                continue
            if token in _SCALE_WORDS:
                raw_parts.append(token)
                i += 1
                continue
        break
    if not raw_parts:
        return "", 0
    for end in range(len(raw_parts), 0, -1):
        value = _words_to_number(raw_parts[:end])
        if value is not None:
            return str(value), _count_consumed_tokens(tokens, start, end)
    return "", 0


def _count_consumed_tokens(tokens: list[str], start: int, expanded_parts_count: int) -> int:
    consumed_parts = 0
    token_count = 0
    i = start
    while i < len(tokens) and consumed_parts < expanded_parts_count:
        token = tokens[i]
        if token == "and":
            consumed_parts += 1
            token_count += 1
            i += 1
            continue
        if token in _SCALE_WORDS:
            consumed_parts += 1
            token_count += 1
            i += 1
            continue
        split_parts = token.split("-")
        if all(part in _NUMBER_WORDS for part in split_parts):
            consumed_parts += len(split_parts)
            token_count += 1
            i += 1
            continue
        break
    return token_count


def _words_to_number(words: list[str]) -> Optional[int]:
    filtered = [word for word in words if word != "and"]
    if not filtered:
        return None

    pairs: list[int] = []
    current = 0
    saw_number = False
    for word in filtered:
        if word in _NUMBER_WORDS:
            current += _NUMBER_WORDS[word]
            saw_number = True
            continue
        if word == "hundred":
            if current == 0:
                return None
            current *= 100
            continue
        if word == "thousand":
            if current == 0:
                return None
            pairs.append(current * 1000)
            current = 0
            continue
        return None

    if not saw_number:
        return None

    total = sum(pairs) + current

    if (
        len(filtered) == 2
        and filtered[0] in _NUMBER_WORDS
        and filtered[1] in _NUMBER_WORDS
        and 10 <= _NUMBER_WORDS[filtered[0]] <= 19
        and 20 <= _NUMBER_WORDS[filtered[1]] <= 99
    ):
        return (_NUMBER_WORDS[filtered[0]] * 100) + _NUMBER_WORDS[filtered[1]]

    if (
        len(filtered) == 3
        and filtered[0] in _NUMBER_WORDS
        and filtered[1] in _NUMBER_WORDS
        and filtered[2] in _NUMBER_WORDS
        and 10 <= _NUMBER_WORDS[filtered[0]] <= 19
        and 20 <= _NUMBER_WORDS[filtered[1]] <= 90
        and 0 <= _NUMBER_WORDS[filtered[2]] <= 9
    ):
        return (_NUMBER_WORDS[filtered[0]] * 100) + _NUMBER_WORDS[filtered[1]] + _NUMBER_WORDS[filtered[2]]

    return total


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
