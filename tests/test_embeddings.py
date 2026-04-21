from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest

from server.embeddings import (
    EMBEDDING_MODEL,
    LM_STUDIO_URL,
    SIMILARITY_THRESHOLD,
    _heuristic_too_similar,
    _normalize_text,
    is_too_similar,
)


@pytest.mark.parametrize(
    ("lie", "truth", "expected_request_input", "embeddings", "expected"),
    [
        (
            "nineteen forty-five",
            "1945",
            ["1945", "1945"],
            ([1.0, 0.0, 0.0], [0.96, 0.04, 0.0]),
            True,
        ),
        (
            "George Washington",
            "Washington",
            ["george washington", "washington"],
            ([1.0, 0.0, 0.0], [0.97, 0.03, 0.0]),
            True,
        ),
        (
            "The Lighthouse of Alexandria",
            "Lighthouse of Alexandria",
            ["the lighthouse of alexandria", "lighthouse of alexandria"],
            ([1.0, 0.0, 0.0], [0.98, 0.02, 0.0]),
            True,
        ),
        (
            "Library of Alexandria",
            "Lighthouse of Alexandria",
            ["library of alexandria", "lighthouse of alexandria"],
            ([1.0, 0.0, 0.0], [0.2, 0.98, 0.0]),
            False,
        ),
        (
            "hello world",
            "1945",
            ["hello world", "1945"],
            ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]),
            False,
        ),
        (
            "George Bush",
            "George Washington",
            ["george bush", "george washington"],
            ([1.0, 0.0, 0.0], [0.4, 0.8, 0.0]),
            False,
        ),
    ],
)
def test_is_too_similar_uses_embedding_comparison(lie, truth, expected_request_input, embeddings, expected):
    response = Mock()
    response.json.return_value = {
        "data": [
            {"embedding": embeddings[0]},
            {"embedding": embeddings[1]},
        ]
    }

    with patch("server.embeddings.requests.post", return_value=response) as mock_post:
        assert is_too_similar(lie, truth) is expected

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["timeout"] == 2.0
    assert kwargs["json"] == {"input": expected_request_input, "model": EMBEDDING_MODEL}
    assert mock_post.call_args.args[0] == f"{LM_STUDIO_URL}/v1/embeddings"


def test_is_too_similar_falls_back_to_normalized_text_on_embedding_error():
    with patch("server.embeddings.requests.post", side_effect=RuntimeError("LM Studio unavailable")):
        assert is_too_similar("nineteen forty-five", "1945") is True
        assert is_too_similar("  Eiffel Tower ", "eiffel tower") is True
        assert is_too_similar("Arc de Triomphe", "Eiffel Tower") is False


def test_is_too_similar_rejects_partial_name_match_below_threshold():
    response = Mock()
    response.json.return_value = {
        "data": [
            {"embedding": [1.0, 0.0, 0.0]},
            {"embedding": [0.74, 0.6726069274, 0.0]},
        ]
    }

    with patch("server.embeddings.requests.post", return_value=response):
        assert is_too_similar("Washington", "George Washington") is True


def test_is_too_similar_rejects_partial_name_match_with_minor_typo_below_threshold():
    response = Mock()
    response.json.return_value = {
        "data": [
            {"embedding": [1.0, 0.0, 0.0]},
            {"embedding": [0.70, 0.7141428429, 0.0]},
        ]
    }

    with patch("server.embeddings.requests.post", return_value=response):
        assert is_too_similar("Washington", "George Washinton") is True


def test_is_too_similar_logs_similarity_details(caplog):
    response = Mock()
    response.json.return_value = {
        "data": [
            {"embedding": [1.0, 0.0, 0.0]},
            {"embedding": [0.8, 0.6, 0.0]},
        ]
    }

    with patch("server.embeddings.requests.post", return_value=response), caplog.at_level(logging.DEBUG):
        assert is_too_similar("Washington", "George Washington") is True

    assert "similarity=0.800000" in caplog.text
    assert "normalized_lie='washington'" in caplog.text
    assert "normalized_truth='george washington'" in caplog.text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("nineteen forty-five", "1945"),
        ("twenty-one pilots", "21 pilots"),
        ("one hundred and one", "101"),
        ("The Lighthouse of Alexandria", "the lighthouse of alexandria"),
    ],
)
def test_normalize_text(text, expected):
    assert _normalize_text(text) == expected


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("washington", "george washington", "token-subset-match"),
        ("washington", "george washinton", "fuzzy-token-subset-match"),
        ("library of alexandria", "lighthouse of alexandria", None),
    ],
)
def test_heuristic_too_similar(left, right, expected):
    assert _heuristic_too_similar(left, right) == expected


def test_similarity_threshold_matches_tuned_value():
    assert SIMILARITY_THRESHOLD == 0.75
