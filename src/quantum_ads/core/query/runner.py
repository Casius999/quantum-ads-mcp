"""run_report: validate a GAQL query, stream it, and flatten proto rows to dotted dicts."""

from __future__ import annotations

from collections.abc import Callable

from .gaql_validator import validate_gaql

StreamFn = Callable[[str, str], list[dict[str, object]]]


def _flatten(row: dict[str, object], prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in row.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, f"{dotted}."))
        else:
            out[dotted] = value
    return out


def run_report(customer_id: str, query: str, *, stream: StreamFn) -> list[dict[str, object]]:
    """Validate first (short-circuits before any network call), then stream and flatten."""
    validate_gaql(query)
    return [_flatten(row) for row in stream(customer_id, query)]
