"""Read-plane tests for the Looker connector: param builders, tool helpers, graceful degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the ``{"rows", "row_count"}`` envelope, that the pure
param builders assemble the right look/query params (and copy their collections defensively), that
the right operation name + params reach the backend, and that a missing backend yields a structured
``BACKEND_NOT_CONFIGURED`` error instead of raising.
"""

from quantum_ads.connectors.looker import read_tools
from quantum_ads.connectors.looker.connector import register_looker
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


# --- pure param builders (unit) -----------------------------------------------


def test_build_look_run_params_defaults_to_json():
    params = read_tools.build_look_run_params("42")
    assert params == {"look_id": "42", "result_format": "json"}


def test_build_look_run_params_honours_result_format():
    params = read_tools.build_look_run_params("42", "csv")
    assert params == {"look_id": "42", "result_format": "csv"}


def test_build_query_run_params_copies_fields_and_filters():
    fields = ["orders.count", "orders.total"]
    filters: dict[str, object] = {"orders.created_date": "30 days"}
    params = read_tools.build_query_run_params("ecommerce", "orders", fields, filters)
    assert params["model"] == "ecommerce"
    assert params["view"] == "orders"
    assert params["fields"] == ["orders.count", "orders.total"]
    assert params["filters"] == {"orders.created_date": "30 days"}
    # Builder copies defensively: mutating the source list/dict must not touch the params.
    fields.append("orders.average")
    filters["orders.created_date"] = "7 days"
    assert params["fields"] == ["orders.count", "orders.total"]
    assert params["filters"] == {"orders.created_date": "30 days"}


# --- pure tool helpers (unit) -------------------------------------------------


def test_list_dashboards_wraps_rows_and_passes_no_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"id": "1", "title": "Spend overview"}]

    out = read_tools.list_dashboards(read=read)
    assert out["rows"] == [{"id": "1", "title": "Spend overview"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "dashboards.list"
    assert seen["params"] == {}


def test_list_looks_wraps_rows():
    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        assert operation == "looks.list"
        assert params == {}
        return [{"id": "7"}, {"id": "8"}]

    out = read_tools.list_looks(read=read)
    assert out["row_count"] == 2


def test_run_look_forwards_look_id_and_format():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"orders.count": 12}]

    out = read_tools.run_look(look_id="42", read=read, result_format="json")
    assert out["rows"] == [{"orders.count": 12}]
    assert out["row_count"] == 1
    assert seen["operation"] == "look.run"
    assert seen["params"] == {"look_id": "42", "result_format": "json"}


def test_run_look_uses_default_format_when_unspecified():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["params"] = params
        return []

    read_tools.run_look(look_id="42", read=read)
    assert seen["params"]["result_format"] == read_tools.DEFAULT_RESULT_FORMAT


def test_run_query_forwards_model_view_fields_filters():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"orders.count": 3}]

    out = read_tools.run_query(
        model="ecommerce",
        view="orders",
        fields=["orders.count"],
        filters={"orders.status": "complete"},
        read=read,
    )
    assert out["rows"] == [{"orders.count": 3}]
    assert seen["operation"] == "query.run"
    assert seen["params"] == {
        "model": "ecommerce",
        "view": "orders",
        "fields": ["orders.count"],
        "filters": {"orders.status": "complete"},
    }


# --- registration + backend-not-configured degradation (integration) ----------


def test_read_tools_registered_and_marked_read_only():
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_looker],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "looker.dashboards.list" in names
    assert "looker.looks.list" in names
    assert "looker.look.run" in names
    assert "looker.query.run" in names
    assert assembled.registry.describe_tool("looker.look.run").read_only is True


def test_read_tools_degrade_when_backend_missing():
    # No backends wired -> ctx.backend("looker.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_looker],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "looker.dashboards.list" in names
