"""Integration (mock) tests for the Data Manager API connector.

Exercises tool registration, read_only flags, and the read/write planes against fakes — no real
Data Manager SDK is imported. ``build_server`` wires the fakes via the ``backends`` mapping.
"""

from quantum_ads.connectors.datamanager import register_datamanager
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
    return [{"operation": operation, "params": params}]


def _fake_mutate(
    account_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "account_id": account_id, "validate_only": validate_only}


def _build():
    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"datamanager.api": _fake_mutate, "datamanager.read": _fake_read},
        connectors=[register_datamanager],
    )


def test_datamanager_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "datamanager.status" in names
    assert "datamanager.destinations.list" in names


def test_datamanager_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "datamanager.audience.upload_members" in names
    assert "datamanager.audience.remove_members" in names
    assert "datamanager.conversions.upload" in names


def test_datamanager_read_tools_marked_read_only():
    assembled = _build()
    registry = assembled.registry
    assert registry.describe_tool("datamanager.status").read_only is True
    assert registry.describe_tool("datamanager.destinations.list").read_only is True


def test_datamanager_write_tools_marked_not_read_only():
    assembled = _build()
    registry = assembled.registry
    assert registry.describe_tool("datamanager.audience.upload_members").read_only is False
    assert registry.describe_tool("datamanager.audience.remove_members").read_only is False
    assert registry.describe_tool("datamanager.conversions.upload").read_only is False


def test_datamanager_capability_declared():
    assembled = _build()
    domains = {(c.connector, c.domain) for c in assembled.registry.list_capabilities()}
    assert ("datamanager", "read") in domains
    assert ("datamanager", "write") in domains
