from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict

SECRET_KEY = os.getenv("SECRET_KEY", "change_me")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encode(payload: Dict[str, Any], expires_in: int = 3600) -> str:
    """Encode payload as JWT using HS256."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = payload.copy()
    payload["exp"] = int(time.time()) + expires_in
    segments = [
        _b64encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64encode(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode()
    signature = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64encode(signature))
    return ".".join(segments)


def decode(token: str) -> Dict[str, Any]:
    """Decode JWT and verify signature/expiry."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64decode(sig_b64), expected):
        raise ValueError("Invalid signature")
    payload = json.loads(_b64decode(payload_b64).decode())
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return payload
