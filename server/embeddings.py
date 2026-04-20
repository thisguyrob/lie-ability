import math
import os
import requests

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")
SIMILARITY_THRESHOLD = float(os.environ.get("LIE_SIMILARITY_THRESHOLD", "0.90"))
_EMBED_TIMEOUT = 2.0


def is_too_similar(lie: str, truth: str) -> bool:
    try:
        return _embedding_similarity(lie, truth) >= SIMILARITY_THRESHOLD
    except Exception:
        return lie.strip().lower() == truth.strip().lower()


def _embedding_similarity(a: str, b: str) -> float:
    url = f"{LM_STUDIO_URL}/v1/embeddings"
    resp = requests.post(
        url,
        json={"input": [a, b], "model": "text-embedding-ada-002"},
        timeout=_EMBED_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    vec_a = data[0]["embedding"]
    vec_b = data[1]["embedding"]
    return _cosine(vec_a, vec_b)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
