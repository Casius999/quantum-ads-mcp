"""Integration (mock) tests for the Merchant API connector.

Exercises tool registration, read_only flags, and the read/write planes against fakes — no real
Merchant API SDK is imported. ``build_server`` wires the fakes via the ``backends`` mapping.
"""

from quantum_ads.connectors.merchant import register_merchant
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
        backends={"merchant.api": _fake_read, "merchant.mutate": _fake_mutate},
        connectors=[register_merchant],
    )


def test_merchant_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "merchant.products.list" in names
    assert "merchant.product.get" in names
    assert "merchant.product_statuses.list" in names
    assert "merchant.accounts.get" in names


def test_merchant_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "merchant.product.insert" in names
    assert "merchant.product.update" in names
    assert "merchant.product.delete" in names


def test_merchant_read_tools_marked_read_only():
    assembled = _build()
    registry = assembled.registry
    assert registry.describe_tool("merchant.products.list").read_only is True
    assert registry.describe_tool("merchant.product.get").read_only is True
    assert registry.describe_tool("merchant.product_statuses.list").read_only is True
    assert registry.describe_tool("merchant.accounts.get").read_only is True


def test_merchant_write_tools_marked_not_read_only():
    assembled = _build()
    registry = assembled.registry
    assert registry.describe_tool("merchant.product.insert").read_only is False
    assert registry.describe_tool("merchant.product.update").read_only is False
    assert registry.describe_tool("merchant.product.delete").read_only is False


def test_merchant_capability_declared():
    assembled = _build()
    domains = {(c.connector, c.domain) for c in assembled.registry.list_capabilities()}
    assert ("merchant", "read") in domains
    assert ("merchant", "write") in domains
