"""GAQL pre-flight validator encoding the verified June-2026 rules.

Rules:
- Single FROM resource (no JOINs in GAQL).
- No ``OR`` (use ``IN(...)``).
- A non-date segment used in WHERE must also appear in SELECT; the core date segments
  (date/week/month/quarter/year) are exempt.
- Date literals may not exceed the 37-month lookback cap (effective 2026-06-01).
"""

from __future__ import annotations

import datetime as dt
import re

MAX_LOOKBACK_MONTHS = 37

_DATE_SEGMENTS = {
    "segments.date",
    "segments.week",
    "segments.month",
    "segments.quarter",
    "segments.year",
}
_SELECT_RE = re.compile(r"\bSELECT\b(.*?)\bFROM\b", re.IGNORECASE | re.DOTALL)
_FROM_RE = re.compile(r"\bFROM\b\s+([^\s]+(?:\s*,\s*[^\s]+)*)", re.IGNORECASE)
_WHERE_RE = re.compile(
    r"\bWHERE\b(.*?)(?:\bORDER\s+BY\b|\bLIMIT\b|\bPARAMETERS\b|$)",
    re.IGNORECASE | re.DOTALL,
)
_OR_RE = re.compile(r"\bOR\b", re.IGNORECASE)
_SEGMENT_RE = re.compile(r"\b(segments\.[a-z_]+)\b")
_DATE_LITERAL_RE = re.compile(r"'(\d{4}-\d{2}-\d{2})'")


class GaqlError(ValueError):
    """Raised when a GAQL query violates a structural rule."""


def _select_fields(query: str) -> set[str]:
    match = _SELECT_RE.search(query)
    if not match:
        raise GaqlError("query must have SELECT ... FROM")
    return {field.strip() for field in match.group(1).split(",") if field.strip()}


def _months_between(later: dt.date, earlier: dt.date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def validate_gaql(query: str, today: dt.date | None = None) -> None:
    today = today or dt.date.today()

    if _OR_RE.search(query):
        raise GaqlError("GAQL does not support OR; use IN(...) instead")

    from_match = _FROM_RE.search(query)
    if not from_match or "," in from_match.group(1):
        raise GaqlError("GAQL requires a single FROM resource")

    select = _select_fields(query)
    where_match = _WHERE_RE.search(query)
    where = where_match.group(1) if where_match else ""

    for segment in _SEGMENT_RE.findall(where):
        if segment not in _DATE_SEGMENTS and segment not in select:
            raise GaqlError(f"segment {segment} used in WHERE must also be in SELECT")

    for date_str in _DATE_LITERAL_RE.findall(where):
        parsed = dt.date.fromisoformat(date_str)
        if _months_between(today, parsed) > MAX_LOOKBACK_MONTHS:
            raise GaqlError(
                f"date {date_str} exceeds the 37-month lookback cap (effective 2026-06-01)"
            )
