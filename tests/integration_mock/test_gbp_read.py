"""Google Business Profile read connector: registration, read_only flags, builders, degradation.

All fakes — the real googleapiclient SDK (mybusinessaccountmanagement / mybusinessbusinessinformation
/ businessprofileperformance v1 + legacy mybusiness v4) is never imported. Verifies the
``{"rows", "row_count"}`` envelope, the right operation name + params reach the backend, and missing
backends yield a structured ``BACKEND_NOT_CONFIGURED`` error — including the reviews split, where
``gbp.reviews.list`` degrades independently of the v1 ``gbp.api`` backend.
"""

from quantum_ads.connectors.gbp import register_gbp
from quantum_ads.connectors.gbp.read import list_tools as tools_mod
from quantum_ads.connectors.gbp.read.connector import register_gbp_read
from quantum_ads.core.context import ServerContext
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager


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


_CANNED_ROW: dict[str, object] = {"name": "locations/123", "title": "Cafe Souverain"}


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params, **_CANNED_ROW}]


def _fake_mutate(
    resource: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {
        "gbp.api": _fake_read,
        "gbp.reviews": _fake_read,
        "gbp.mutate": _fake_mutate,
    }


# --- registration via register_gbp (full connector) -----------------------------------------


def test_gbp_read_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_gbp],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "gbp.accounts.list" in names
    assert "gbp.locations.list" in names
    assert "gbp.location.get" in names
    assert "gbp.performance.fetch" in names
    assert "gbp.reviews.list" in names


def test_gbp_read_tools_are_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_gbp],
    )
    for name in (
        "gbp.accounts.list",
        "gbp.locations.list",
        "gbp.location.get",
        "gbp.performance.fetch",
        "gbp.reviews.list",
    ):
        assert assembled.registry.describe_tool(name).read_only is True


def test_register_gbp_read_alone_registers_only_read_tools():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_gbp_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "gbp.accounts.list" in names
    assert "gbp.review.reply" not in names
    assert "gbp.location.update" not in names


# --- pure request builders (unit) -----------------------------------------------------------


def test_build_locations_request_shape():
    request = tools_mod.build_locations_request(account_id="accounts/42")
    assert request == {"account_id": "accounts/42"}


def test_build_location_get_request_shape():
    request = tools_mod.build_location_get_request(location_name="locations/123")
    assert request == {"location_name": "locations/123"}


def test_build_performance_request_shape():
    request = tools_mod.build_performance_request(
        location_name="locations/123",
        start_date="2026-05-01",
        end_date="2026-05-31",
    )
    assert request == {
        "location_name": "locations/123",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }


def test_build_reviews_request_shape():
    request = tools_mod.build_reviews_request(location_name="accounts/1/locations/123")
    assert request == {"location_name": "accounts/1/locations/123"}


# --- tool helpers against the fake ReadFn ---------------------------------------------------


def test_list_accounts_uses_accounts_operation_and_no_params():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "accounts/42", "accountName": "Souverain"}]

    out = tools_mod.list_accounts(read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "accounts.list"
    assert seen["params"] == {}


def test_list_locations_passes_account_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "locations/123"}]

    out = tools_mod.list_locations(account_id="accounts/42", read=read)
    assert out["rows"] == [{"name": "locations/123"}]
    assert seen["operation"] == "locations.list"
    assert seen["params"] == {"account_id": "accounts/42"}


def test_get_location_passes_location_name():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "locations/123", "title": "Cafe"}]

    out = tools_mod.get_location(location_name="locations/123", read=read)
    assert out["row_count"] == 1
    assert seen["operation"] == "location.get"
    assert seen["params"] == {"location_name": "locations/123"}


def test_fetch_performance_passes_range_and_operation():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"dailyMetric": "CALL_CLICKS", "timeSeries": {}}]

    out = tools_mod.fetch_performance(
        location_name="locations/123",
        start_date="2026-05-01",
        end_date="2026-05-31",
        read=read,
    )
    assert out["row_count"] == 1
    assert seen["operation"] == "performance.fetchMultiDailyMetricsTimeSeries"
    assert seen["params"] == {
        "location_name": "locations/123",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
    }


def test_list_reviews_passes_location_name():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"reviewId": "abc", "starRating": "FIVE"}]

    out = tools_mod.list_reviews(location_name="accounts/1/locations/123", read=read)
    assert out["rows"] == [{"reviewId": "abc", "starRating": "FIVE"}]
    assert seen["operation"] == "reviews.list"
    assert seen["params"] == {"location_name": "accounts/1/locations/123"}


# --- backend-not-configured degradation (integration) ---------------------------------------


def _ctx(backends: dict[str, object]) -> ServerContext:
    return ServerContext(
        creds={},
        version="v1",
        stream_factory=lambda c, v: lambda cid, q: [],
        version_manager=VersionManager("v1", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=False),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends=backends,
    )


class _RecordingApp:
    """Captures the functions registered via FastMCP's ``add_tool`` so we can call them."""

    def __init__(self) -> None:
        self.fns: dict[str, object] = {}

    def tool(self, name: str, description: str):
        def decorator(fn):
            self.fns[name] = fn
            return fn

        return decorator


def test_read_tools_degrade_when_backend_missing():
    from quantum_ads.server import build_server

    # No backends wired -> ctx.backend("gbp.api") is None.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_gbp_read],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "gbp.accounts.list" in names


def test_accounts_list_returns_backend_not_configured_without_gbp_api():
    app = _RecordingApp()
    ctx = _ctx({})  # no gbp.api backend
    register_gbp_read(app, ctx)  # type: ignore[arg-type]
    accounts = app.fns["gbp.accounts.list"]

    out = accounts()  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
    assert out["error"]["message"] == "gbp.api not wired"


def test_reviews_list_degrades_independently_when_reviews_backend_missing():
    # gbp.api present, gbp.reviews absent: v1 tools work, reviews degrades on its own key.
    app = _RecordingApp()
    ctx = _ctx({"gbp.api": _fake_read})
    register_gbp_read(app, ctx)  # type: ignore[arg-type]

    accounts = app.fns["gbp.accounts.list"]
    reviews = app.fns["gbp.reviews.list"]

    accounts_out = accounts()  # type: ignore[operator]
    assert accounts_out["row_count"] == 1  # v1 backend is wired

    reviews_out = reviews(location_name="accounts/1/locations/123")  # type: ignore[operator]
    assert isinstance(reviews_out["error"], dict)
    assert reviews_out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
    assert reviews_out["error"]["message"] == "gbp.reviews not wired"


def test_reviews_list_works_when_reviews_backend_wired():
    app = _RecordingApp()
    ctx = _ctx({"gbp.reviews": _fake_read})
    register_gbp_read(app, ctx)  # type: ignore[arg-type]
    reviews = app.fns["gbp.reviews.list"]

    out = reviews(location_name="accounts/1/locations/123")  # type: ignore[operator]
    assert out["row_count"] == 1
    assert out["rows"][0]["operation"] == "reviews.list"
