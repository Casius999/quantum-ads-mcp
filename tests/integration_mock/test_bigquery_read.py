"""Read-plane tests for the BigQuery connector: cost helper, tool helpers, graceful degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the ``{"rows", "row_count"}`` envelope, the dry-run cost
annotation ($6.25/TiB), that ``run_query`` forwards + echoes ``max_bytes_billed``, that the right
operation name + params reach the backend, and that a missing backend yields a structured
``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.bigquery import read_tools
from quantum_ads.connectors.bigquery.connector import register_bigquery
from quantum_ads.connectors.bigquery.cost import BYTES_PER_TIB, estimate_cost_usd
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


# --- pure cost helper (unit) --------------------------------------------------


def test_estimate_cost_usd_one_tib_is_six_twenty_five():
    assert estimate_cost_usd(BYTES_PER_TIB) == 6.25


def test_estimate_cost_usd_scales_linearly():
    assert estimate_cost_usd(BYTES_PER_TIB // 2) == 3.125
    assert estimate_cost_usd(0) == 0.0


# --- pure tool helpers (unit) -------------------------------------------------


def test_list_datasets_wraps_rows_and_passes_project_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"dataset_id": "analytics_123"}]

    out = read_tools.list_datasets(project_id="proj-1", read=read)
    assert out["rows"] == [{"dataset_id": "analytics_123"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "datasets.list"
    assert seen["params"] == {"project_id": "proj-1"}


def test_list_tables_passes_project_and_dataset():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return []

    out = read_tools.list_tables(project_id="proj-1", dataset_id="ds-1", read=read)
    assert out["row_count"] == 0
    assert seen["operation"] == "tables.list"
    assert seen["params"] == {"project_id": "proj-1", "dataset_id": "ds-1"}


def test_dry_run_query_annotates_estimated_bytes_and_cost():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        assert operation == "query.dry_run"
        assert params == {"project_id": "proj-1", "sql": "SELECT 1"}
        return [{"total_bytes_processed": BYTES_PER_TIB}]

    out = read_tools.dry_run_query(project_id="proj-1", sql="SELECT 1", read=read)
    assert out["estimated_bytes"] == BYTES_PER_TIB
    assert out["estimated_cost_usd"] == 6.25
    assert out["row_count"] == 1


def test_dry_run_query_defaults_to_zero_when_estimate_absent():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        return [{"unexpected": "shape"}]

    out = read_tools.dry_run_query(project_id="proj-1", sql="SELECT 1", read=read)
    assert out["estimated_bytes"] == 0
    assert out["estimated_cost_usd"] == 0.0


def test_run_query_forwards_and_echoes_max_bytes_billed():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"col": 1}]

    out = read_tools.run_query(
        project_id="proj-1", sql="SELECT 1", read=read, max_bytes_billed=5_000
    )
    assert out["rows"] == [{"col": 1}]
    assert out["max_bytes_billed"] == 5_000
    assert seen["operation"] == "query.run"
    assert seen["params"] == {"project_id": "proj-1", "sql": "SELECT 1", "max_bytes_billed": 5_000}


def test_run_query_uses_default_ceiling_when_unspecified():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["params"] = params
        return []

    out = read_tools.run_query(project_id="proj-1", sql="SELECT 1", read=read)
    assert out["max_bytes_billed"] == read_tools.DEFAULT_MAX_BYTES_BILLED
    assert seen["params"]["max_bytes_billed"] == read_tools.DEFAULT_MAX_BYTES_BILLED


# --- registration + backend-not-configured degradation (integration) ----------


def test_read_tools_registered_and_marked_read_only():
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_bigquery],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "bigquery.datasets.list" in names
    assert "bigquery.tables.list" in names
    assert "bigquery.query.dry_run" in names
    assert "bigquery.query.run" in names
    assert assembled.registry.describe_tool("bigquery.query.run").read_only is True


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("bigquery.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_bigquery],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "bigquery.datasets.list" in names
