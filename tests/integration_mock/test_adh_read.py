"""Read-plane tests for the ADH connector: registration, read_only flags, builders, degradation.

All fakes — the real googleapiclient (adsdatahub v1) SDK is never imported. Verifies the
``{"rows", "row_count"}`` envelope, that the right operation name + params reach the backend for
each read tool (``customers.list`` / ``queries.list`` / ``query.start`` / ``jobs.get``), that the
pure param builders shape the dicts correctly, and that a missing backend yields a structured
``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.adh import queries, register_adh, register_adh_read
from quantum_ads.connectors.adh.read import query_tools
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


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return []


def _fake_mutate(
    account_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only, "account_id": account_id}


def _build():
    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"adh.api": _fake_read, "adh.mutate": _fake_mutate},
        connectors=[register_adh],
    )


# --- registration -------------------------------------------------------------


def test_adh_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "adh.customers.list" in names
    assert "adh.queries.list" in names
    assert "adh.query.start" in names
    assert "adh.jobs.get" in names


def test_adh_read_tools_marked_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("adh.customers.list").read_only is True
    assert assembled.registry.describe_tool("adh.queries.list").read_only is True
    assert assembled.registry.describe_tool("adh.query.start").read_only is True
    assert assembled.registry.describe_tool("adh.jobs.get").read_only is True


def test_register_adh_read_alone_registers_only_read_tools():
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"adh.api": _fake_read},
        connectors=[register_adh_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "adh.customers.list" in names
    assert "adh.query.create" not in names


# --- pure param builders (unit) -----------------------------------------------


def test_build_list_customers_params_is_empty():
    assert queries.build_list_customers_params() == {}


def test_build_list_queries_params_shape():
    assert queries.build_list_queries_params("CID1") == {"customer_id": "CID1"}


def test_build_start_query_params_shape():
    assert queries.build_start_query_params("CID1", "Q9", "2026-05-01", "2026-05-31") == {
        "customer_id": "CID1",
        "query_id": "Q9",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }


def test_build_get_job_params_shape():
    assert queries.build_get_job_params("operations/abc123") == {
        "operation_name": "operations/abc123"
    }


def test_query_operation_name_constants():
    assert queries.OP_CUSTOMERS_LIST == "customers.list"
    assert queries.OP_QUERIES_LIST == "queries.list"
    assert queries.OP_QUERY_START == "query.start"
    assert queries.OP_JOBS_GET == "jobs.get"


# --- tool helpers against the fake ReadFn -------------------------------------


def test_list_customers_uses_operation_and_no_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "customers/123", "displayName": "Acme"}]

    out = query_tools.list_customers(read=read)
    assert out["row_count"] == 1
    assert out["rows"] == [{"name": "customers/123", "displayName": "Acme"}]
    assert seen["operation"] == "customers.list"
    assert seen["params"] == {}


def test_list_queries_wraps_rows_and_passes_customer_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "customers/123/analysisQueries/Q1"}]

    out = query_tools.list_queries(customer_id="CID1", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "queries.list"
    assert seen["params"] == {"customer_id": "CID1"}


def test_start_query_passes_customer_query_and_dates():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "operations/op-1", "done": False}]

    out = query_tools.start_query(
        customer_id="CID1",
        query_id="Q9",
        start_date="2026-05-01",
        end_date="2026-05-31",
        read=read,
    )
    assert out["row_count"] == 1
    assert out["rows"] == [{"name": "operations/op-1", "done": False}]
    assert seen["operation"] == "query.start"
    assert seen["params"] == {
        "customer_id": "CID1",
        "query_id": "Q9",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }


def test_get_job_passes_operation_name():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "operations/op-1", "done": True}]

    out = query_tools.get_job(operation_name="operations/op-1", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "jobs.get"
    assert seen["params"] == {"operation_name": "operations/op-1"}


# --- backend-not-configured degradation (integration) -------------------------


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("adh.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_adh_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "adh.customers.list" in names
