"""Tolerate enum values added by monthly Google API releases without crashing.

Guards the class of breakage seen when e.g. DV360 added Demand Gen (2026-06-10): a `list`
response may carry enum values the pinned client doesn't know yet.
"""

from __future__ import annotations


def safe_enum_name(value: str, known: set[str]) -> str:
    """Return ``value`` if known, else ``"UNKNOWN"`` (never raise on new enum values)."""
    return value if value in known else "UNKNOWN"
