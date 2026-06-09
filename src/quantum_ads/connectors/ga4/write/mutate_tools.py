"""Pure operation builders for GA4 Admin API mutations (entity-agnostic dict operations).

Each builder returns the ``operations`` list handed to the guarded ``WriteExecutor``; the
concrete Admin API translation lives in ``ga4.sdk`` (live boundary). Unit-test these directly.
"""

from __future__ import annotations


def build_create_key_event_ops(property_id: str, event_name: str) -> list[dict[str, object]]:
    """Build the op to create a key event (conversion) for an event name on a property."""
    op: dict[str, object] = {
        "entity": "key_event",
        "action": "create",
        "property_id": property_id,
        "event_name": event_name,
    }
    return [op]


def build_create_audience_ops(
    property_id: str, display_name: str, filter_clauses: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Build the op to create an audience with the given display name + filter clauses."""
    op: dict[str, object] = {
        "entity": "audience",
        "action": "create",
        "property_id": property_id,
        "display_name": display_name,
        "filter_clauses": list(filter_clauses),
    }
    return [op]
