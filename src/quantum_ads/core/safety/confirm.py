"""Two-step confirmation tokens for mutations (draft -> preview -> confirm)."""

from __future__ import annotations

import hashlib
import json


def _canonical(op: str, payload: dict[str, object]) -> bytes:
    return json.dumps(
        {"op": op, "payload": payload}, sort_keys=True, separators=(",", ":")
    ).encode()


def confirm_token(op: str, payload: dict[str, object]) -> str:
    """Deterministic token binding a confirmation to an exact (op, payload)."""
    return hashlib.sha256(_canonical(op, payload)).hexdigest()[:16]


def matches(op: str, payload: dict[str, object], candidate: str | None) -> bool:
    return candidate is not None and candidate == confirm_token(op, payload)
