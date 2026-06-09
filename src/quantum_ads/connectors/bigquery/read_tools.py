"""Raw BigQuery read execution + result wrapping for the read connector.

Each tool calls the injected ``ReadFn`` with an operation name and a params dict, then wraps the
rows in the shared ``{"rows", "row_count"}`` envelope, matching the other read connectors.

Cost safety lives here too:

* ``dry_run_query`` always asks the backend for an estimate (no bytes are billed) and annotates
  the response with ``estimated_bytes`` + ``estimated_cost_usd`` derived from
  :func:`quantum_ads.connectors.bigquery.cost.estimate_cost_usd`.
* ``run_query`` forwards an explicit ``max_bytes_billed`` ceiling to the backend; the live SDK
  refuses to run (and is billed nothing) if the scan would exceed it.

The backend is expected to return the dry-run estimate as a single row carrying a
``total_bytes_processed`` key (the field name BigQuery's dry-run uses).
"""

from __future__ import annotations

from .cost import estimate_cost_usd
from .types import ReadFn

# Operation names passed as the first ReadFn argument.
OP_DATASETS_LIST = "datasets.list"
OP_TABLES_LIST = "tables.list"
OP_QUERY_DRY_RUN = "query.dry_run"
OP_QUERY_RUN = "query.run"

# Default ceiling for run_query: 1 GiB-ish (1e9 bytes) ~= $0.0057 at $6.25/TiB.
DEFAULT_MAX_BYTES_BILLED = 1_000_000_000


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_datasets(*, project_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list datasets in a project."""
    params: dict[str, object] = {"project_id": project_id}
    return _wrap(read(OP_DATASETS_LIST, params))


def list_tables(*, project_id: str, dataset_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list tables in a dataset."""
    params: dict[str, object] = {"project_id": project_id, "dataset_id": dataset_id}
    return _wrap(read(OP_TABLES_LIST, params))


def dry_run_query(*, project_id: str, sql: str, read: ReadFn) -> dict[str, object]:
    """Tool: dry-run a query — estimate scanned bytes + USD cost without billing anything.

    Always available (a dry-run scans nothing). Annotates the backend's estimate with the
    derived ``estimated_cost_usd`` at $6.25/TiB so the caller can decide before running.
    """
    params: dict[str, object] = {"project_id": project_id, "sql": sql}
    rows = read(OP_QUERY_DRY_RUN, params)
    estimated_bytes = _estimated_bytes(rows)
    return {
        "rows": rows,
        "row_count": len(rows),
        "estimated_bytes": estimated_bytes,
        "estimated_cost_usd": estimate_cost_usd(estimated_bytes),
    }


def run_query(
    *, project_id: str, sql: str, read: ReadFn, max_bytes_billed: int = DEFAULT_MAX_BYTES_BILLED
) -> dict[str, object]:
    """Tool: run a query, but only if it scans under ``max_bytes_billed`` bytes.

    The ceiling is forwarded to the backend; the live SDK aborts (billing nothing) when the scan
    would exceed it. The applied ceiling is echoed back for transparency.
    """
    params: dict[str, object] = {
        "project_id": project_id,
        "sql": sql,
        "max_bytes_billed": max_bytes_billed,
    }
    out = _wrap(read(OP_QUERY_RUN, params))
    out["max_bytes_billed"] = max_bytes_billed
    return out


def _estimated_bytes(rows: list[dict[str, object]]) -> int:
    """Pull ``total_bytes_processed`` from the first dry-run row; 0 if absent/malformed."""
    if not rows:
        return 0
    raw = rows[0].get("total_bytes_processed", 0)
    try:
        return int(raw)  # type: ignore[call-overload, no-any-return]
    except (TypeError, ValueError):
        return 0
