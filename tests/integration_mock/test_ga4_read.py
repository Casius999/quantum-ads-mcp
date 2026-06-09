"""GA4 read connector: registration, read_only flags, Data API builders, graceful degradation.

All fakes — the real google-analytics-data / google-analytics-admin SDKs are never imported.
"""

from quantum_ads.connectors.ga4 import register_ga4
from quantum_ads.connectors.ga4.read import data_tools
from quantum_ads.connectors.ga4.read.connector import register_ga4_read
from quantum_ads.core.query.runner import StreamFn


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


_CANNED_ROW: dict[str, object] = {"dimensionValues": [{"value": "Paris"}]}


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params, **_CANNED_ROW}]


def _fake_mutate(
    property_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"ga4.data": _fake_read, "ga4.admin": _fake_read, "ga4.admin.mutate": _fake_mutate}


# --- registration via register_ga4 (full connector) -----------------------------------------


def test_ga4_read_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_ga4],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ga4.report" in names
    assert "ga4.realtime" in names
    assert "ga4.admin.list_properties" in names
    assert "ga4.admin.list_data_streams" in names
    assert "ga4.admin.list_key_events" in names


def test_ga4_read_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_ga4],
    )
    for name in (
        "ga4.report",
        "ga4.realtime",
        "ga4.admin.list_properties",
        "ga4.admin.list_data_streams",
        "ga4.admin.list_key_events",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


def test_register_ga4_read_alone_registers_only_read_tools():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_ga4_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ga4.report" in names
    assert "ga4.admin.create_key_event" not in names


# --- pure Data API builders -----------------------------------------------------------------


def test_build_report_params_shape():
    params = data_tools.build_report_params(
        property_id="123456",
        dimensions=["city", "country"],
        metrics=["activeUsers"],
        start_date="2026-05-01",
        end_date="2026-05-31",
    )
    assert params == {
        "property_id": "123456",
        "dimensions": ["city", "country"],
        "metrics": ["activeUsers"],
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }


def test_build_realtime_params_has_no_date_range():
    params = data_tools.build_realtime_params(
        property_id="123456", dimensions=["country"], metrics=["activeUsers"]
    )
    assert params == {
        "property_id": "123456",
        "dimensions": ["country"],
        "metrics": ["activeUsers"],
    }
    assert "start_date" not in params


# --- run wrappers against the fake ReadFn ---------------------------------------------------


def test_run_report_calls_backend_with_runreport_operation():
    out = data_tools.run_report(
        property_id="123456",
        dimensions=["city"],
        metrics=["activeUsers"],
        start_date="2026-05-01",
        end_date="2026-05-31",
        backend=_fake_read,
    )
    assert out["row_count"] == 1
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "runReport"


def test_run_realtime_calls_backend_with_realtime_operation():
    out = data_tools.run_realtime(
        property_id="123456",
        dimensions=["country"],
        metrics=["activeUsers"],
        backend=_fake_read,
    )
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "runRealtimeReport"


def test_run_report_backend_not_configured():
    out = data_tools.run_report(
        property_id="123456",
        dimensions=["city"],
        metrics=["activeUsers"],
        start_date="2026-05-01",
        end_date="2026-05-31",
        backend=None,
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
