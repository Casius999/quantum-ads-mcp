"""Pure operation builders for CM360 mutations (entity-agnostic dict operations).

Each op dict names the CM360 ``action`` (``update_placement`` / ``insert_report``) plus the
profile id and the body/ids it needs. The ``MutateFn`` backend dispatches on ``action``; the
concrete dfareporting API translation lives in ``cm360.sdk`` (live boundary). Builders are pure
and unit-tested directly.

``update_placement`` is a partial patch over a single placement (id + ``fields``), matching the
DV360 line-item update shape. ``insert_report`` creates a report definition from a full ``report``
body dict (matching the Merchant insert shape), so the agency can stand up new measurement reports
programmatically before running them via the read-plane ``cm360.report.run`` tool.
"""

from __future__ import annotations


def build_update_placement_ops(
    profile_id: str, placement_id: str, fields: dict[str, object]
) -> list[dict[str, object]]:
    """Build an update-placement op (partial patch) under a user profile."""
    op: dict[str, object] = {
        "action": "update_placement",
        "profile_id": profile_id,
        "placement_id": placement_id,
        "fields": dict(fields),
    }
    return [op]


def build_insert_report_ops(profile_id: str, report: dict[str, object]) -> list[dict[str, object]]:
    """Build an insert-report op (create a report definition) under a user profile."""
    op: dict[str, object] = {
        "action": "insert_report",
        "profile_id": profile_id,
        "report": dict(report),
    }
    return [op]
