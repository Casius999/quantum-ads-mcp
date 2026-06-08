import datetime as dt

from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.registry.registry import Capability, ConnectorRegistry, ToolSpec
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager
from quantum_ads.server import (
    build_server,
    capabilities_payload,
    describe_tool_payload,
    health_payload,
)


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
    }


def _factory(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def test_server_registers_core_tools():
    assembled = build_server(env=_env(), stream_factory=_factory)
    names = {t.name for t in assembled.registry.all_tools()}
    assert {"health", "list_capabilities", "describe_tool"} <= names


def test_health_payload_reports_version_and_readonly():
    vm = VersionManager("v24", client_factory=lambda c, v: None)
    out = health_payload(vm, SafetyMode(read_only=True), today=dt.date(2026, 6, 9))
    assert out["api_version"] == "v24"
    assert out["read_only"] is True
    assert isinstance(out["days_until_sunset"], int)


def test_describe_tool_payload_unknown_returns_error():
    out = describe_tool_payload(ConnectorRegistry(), "nope")
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "UNKNOWN_TOOL"


def test_capabilities_payload_lists_registered():
    registry = ConnectorRegistry()
    registry.register(
        Capability(
            connector="google_ads",
            domain="read",
            tools=[ToolSpec(name="ads.gaql.query", summary="Run GAQL")],
        )
    )
    caps = capabilities_payload(registry)
    assert caps[0]["connector"] == "google_ads"
    assert caps[0]["tools"][0]["name"] == "ads.gaql.query"
