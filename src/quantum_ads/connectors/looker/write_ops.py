"""Pure operation builders for Looker write mutations.

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys let
the SDK mutate boundary dispatch to the right Looker call; the remaining keys carry the resource
ids and payload. These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_create_dashboard_ops(title: str, model: str) -> list[dict[str, object]]:
    """Build the op for creating a dashboard with a title under a model."""
    op: dict[str, object] = {
        "entity": "dashboard",
        "action": "create",
        "title": title,
        "model": model,
    }
    return [op]
