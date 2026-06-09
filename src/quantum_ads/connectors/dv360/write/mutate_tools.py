"""Pure operation builders for DV360 line-item mutations (entity-agnostic dict operations).

Each op dict names the DV360 ``action`` (``update_line_item`` / ``set_line_item_status``) plus
the advertiser + line-item ids and the body fields. The ``MutateFn`` backend dispatches on
``action``; the concrete Display Video API translation lives in ``dv360.sdk`` (live boundary).
Builders are pure and unit-tested directly.

``set_line_item_status`` is modelled as a constrained update over the single ``entityStatus``
field — DV360 has no dedicated status endpoint, so the SDK threads it through patch like any
other field, but the distinct op name keeps the audit log and tool surface explicit.
"""

from __future__ import annotations


def build_update_line_item_ops(
    advertiser_id: str, line_item_id: str, fields: dict[str, object]
) -> list[dict[str, object]]:
    """Build an update-line-item op (partial patch) under an advertiser."""
    op: dict[str, object] = {
        "action": "update_line_item",
        "advertiser_id": advertiser_id,
        "line_item_id": line_item_id,
        "fields": dict(fields),
    }
    return [op]


def build_set_line_item_status_ops(
    advertiser_id: str, line_item_id: str, entity_status: str
) -> list[dict[str, object]]:
    """Build a set-status op (constrained update over ``entityStatus``) under an advertiser."""
    op: dict[str, object] = {
        "action": "set_line_item_status",
        "advertiser_id": advertiser_id,
        "line_item_id": line_item_id,
        "entity_status": entity_status,
    }
    return [op]
