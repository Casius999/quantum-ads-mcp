"""Pure operation builders for BigQuery write (DDL) mutations.

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys
let the SDK mutate boundary dispatch to the right BigQuery call; the remaining keys carry the
resource ids and payload. These are pure and unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_create_dataset_ops(project_id: str, dataset_id: str) -> list[dict[str, object]]:
    """Build the op for creating a dataset under a project."""
    op: dict[str, object] = {
        "entity": "dataset",
        "action": "create",
        "project_id": project_id,
        "dataset_id": dataset_id,
    }
    return [op]


def build_create_table_ops(
    project_id: str, dataset_id: str, table_id: str, schema: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Build the op for creating a table with a schema under a dataset.

    ``schema`` is a list of field dicts (e.g. ``{"name": "clicks", "type": "INT64"}``); it is
    copied defensively so the caller's list is never mutated.
    """
    op: dict[str, object] = {
        "entity": "table",
        "action": "create",
        "project_id": project_id,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "schema": [dict(field) for field in schema],
    }
    return [op]
