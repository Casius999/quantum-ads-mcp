"""Structured -> GAQL string builder. Output is designed to pass ``validate_gaql``."""

from __future__ import annotations


def build_gaql(
    *,
    resource: str,
    fields: list[str],
    where: list[str] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> str:
    parts = [f"SELECT {', '.join(fields)}", f"FROM {resource}"]
    if where:
        parts.append("WHERE " + " AND ".join(where))
    if order_by:
        parts.append(f"ORDER BY {order_by}")
    if limit:
        parts.append(f"LIMIT {int(limit)}")
    return "\n".join(parts)
