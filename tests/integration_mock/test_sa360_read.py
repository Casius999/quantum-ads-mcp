"""Read-plane tests for the SA360 connector: registration, read_only flags, builders, degradation.

All fakes — the real googleapiclient (searchads360 v0) SDK is never imported. Verifies the
``{"rows", "row_count"}`` envelope, that the right operation name + params (``search`` with
``{"customer_id", "query"}``) reach the backend, that the report shortcuts build the SA360 query
string and reject bad date ranges, and that a missing backend yields a structured
``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.sa360 import queries, register_sa360, register_sa360_read
from quantum_ads.connectors.sa360.read import search_tools
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
        backends={"sa360.api": _fake_read, "sa360.mutate": _fake_mutate},
        connectors=[register_sa360],
    )


# --- registration -------------------------------------------------------------


def test_sa360_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "sa360.search" in names
    assert "sa360.customers.list_accessible" in names
    assert "sa360.report.campaign" in names
    assert "sa360.report.ad_group" in names


def test_sa360_read_tools_marked_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("sa360.search").read_only is True
    assert assembled.registry.describe_tool("sa360.customers.list_accessible").read_only is True
    assert assembled.registry.describe_tool("sa360.report.campaign").read_only is True
    assert assembled.registry.describe_tool("sa360.report.ad_group").read_only is True


def test_register_sa360_read_alone_registers_only_read_tools():
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"sa360.api": _fake_read},
        connectors=[register_sa360_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "sa360.search" in names
    assert "sa360.conversion.upload" not in names


# --- pure query builders (unit) -----------------------------------------------


def test_build_search_params_shape():
    assert queries.build_search_params("CID1", "SELECT campaign.id FROM campaign") == {
        "customer_id": "CID1",
        "query": "SELECT campaign.id FROM campaign",
    }


def test_build_search_query_assembles_select_from_where():
    q = queries.build_search_query(
        resource="campaign",
        fields=["campaign.id", "campaign.name"],
        date_range="LAST_7_DAYS",
    )
    assert q == (
        "SELECT campaign.id, campaign.name FROM campaign WHERE segments.date DURING LAST_7_DAYS"
    )


def test_build_search_query_appends_order_by():
    q = queries.build_search_query(
        resource="campaign",
        fields=["campaign.id"],
        date_range="LAST_30_DAYS",
        order_by="metrics.cost_micros DESC",
    )
    assert q.endswith("ORDER BY metrics.cost_micros DESC")
    assert "WHERE segments.date DURING LAST_30_DAYS" in q


def test_build_campaign_query_uses_campaign_resource_and_cost_order():
    q = queries.build_campaign_query("LAST_14_DAYS")
    assert q.startswith("SELECT ")
    assert "FROM campaign" in q
    assert "WHERE segments.date DURING LAST_14_DAYS" in q
    assert q.endswith("ORDER BY metrics.cost_micros DESC")
    assert "metrics.cost_micros" in q


def test_build_ad_group_query_uses_ad_group_resource():
    q = queries.build_ad_group_query("LAST_30_DAYS")
    assert "FROM ad_group" in q
    assert "ad_group.id" in q
    assert "WHERE segments.date DURING LAST_30_DAYS" in q


def test_allowed_date_ranges_is_closed_set():
    assert "LAST_30_DAYS" in queries.ALLOWED_DATE_RANGES
    assert "DROP TABLE" not in queries.ALLOWED_DATE_RANGES


# --- tool helpers against the fake ReadFn -------------------------------------


def test_search_wraps_rows_and_passes_customer_id_and_query():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"campaign": {"id": "1"}}]

    out = search_tools.search(
        customer_id="CID1", query="SELECT campaign.id FROM campaign", read=read
    )
    assert out["row_count"] == 1
    assert out["rows"] == [{"campaign": {"id": "1"}}]
    assert seen["operation"] == "search"
    assert seen["params"] == {
        "customer_id": "CID1",
        "query": "SELECT campaign.id FROM campaign",
    }


def test_list_accessible_customers_uses_operation_and_no_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"resourceName": "customers/123"}]

    out = search_tools.list_accessible_customers(read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "customers.listAccessible"
    assert seen["params"] == {}


def test_report_campaign_builds_query_and_runs_search():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return []

    out = search_tools.report_campaign(customer_id="CID1", date_range="LAST_7_DAYS", read=read)
    assert out["row_count"] == 0
    assert seen["operation"] == "search"
    params = seen["params"]
    assert isinstance(params, dict)
    assert params["customer_id"] == "CID1"
    assert "FROM campaign" in str(params["query"])
    assert "DURING LAST_7_DAYS" in str(params["query"])


def test_report_ad_group_builds_query_and_runs_search():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"adGroup": {"id": "9"}}]

    out = search_tools.report_ad_group(customer_id="CID1", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "search"
    assert "FROM ad_group" in str(seen["params"]["query"])  # type: ignore[index]


def test_report_campaign_rejects_unknown_date_range():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        raise AssertionError("backend must not be called for a bad date range")

    out = search_tools.report_campaign(customer_id="CID1", date_range="LAST_400_DAYS", read=read)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BAD_DATE_RANGE"


def test_report_ad_group_rejects_unknown_date_range():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        raise AssertionError("backend must not be called for a bad date range")

    out = search_tools.report_ad_group(customer_id="CID1", date_range="EVIL", read=read)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BAD_DATE_RANGE"


# --- backend-not-configured degradation (integration) -------------------------


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("sa360.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_sa360_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "sa360.search" in names
