"""GA4 guarded write connector: registration, read_only flags, op builders, full guarded flow.

The mutate backend is a fake MutateFn returning ``{"validate_only": validate_only}``; the real
google-analytics-admin SDK is never imported. The guarded flow (preview -> confirm token ->
applied) is exercised end-to-end through the FastMCP-registered Python callables.
"""

from quantum_ads.connectors.ga4 import register_ga4
from quantum_ads.connectors.ga4.write import mutate_tools
from quantum_ads.connectors.ga4.write.connector import register_ga4_write
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.confirm import confirm_token
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.safety.write_executor import WriteExecutor


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
    return [{"operation": operation}]


def _fake_mutate(
    property_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"ga4.data": _fake_read, "ga4.admin": _fake_read, "ga4.admin.mutate": _fake_mutate}


# --- registration ---------------------------------------------------------------------------


def test_ga4_write_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_ga4],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ga4.admin.create_key_event" in names
    assert "ga4.admin.create_audience" in names


def test_ga4_write_tools_marked_not_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_ga4_write],
    )
    assert assembled.registry.describe_tool("ga4.admin.create_key_event").read_only is False
    assert assembled.registry.describe_tool("ga4.admin.create_audience").read_only is False


# --- pure op builders -----------------------------------------------------------------------


def test_build_create_key_event_ops():
    ops = mutate_tools.build_create_key_event_ops("123456", "purchase")
    assert ops == [
        {
            "entity": "key_event",
            "action": "create",
            "property_id": "123456",
            "event_name": "purchase",
        }
    ]


def test_build_create_audience_ops():
    clauses: list[dict[str, object]] = [{"clauseType": "INCLUDE"}]
    ops = mutate_tools.build_create_audience_ops("123456", "Buyers", clauses)
    assert ops == [
        {
            "entity": "audience",
            "action": "create",
            "property_id": "123456",
            "display_name": "Buyers",
            "filter_clauses": [{"clauseType": "INCLUDE"}],
        }
    ]


# --- guarded flow through WriteExecutor (preview -> confirm -> applied) ----------------------


def _executor() -> WriteExecutor:
    return WriteExecutor(_fake_mutate, SafetyMode(read_only=False), AuditLedger.ephemeral())


def test_create_key_event_preview_then_confirm():
    ex = _executor()
    ops = mutate_tools.build_create_key_event_ops("123456", "purchase")

    preview = ex.execute(op="ga4.admin.create_key_event", customer_id="123456", operations=ops)
    assert preview["applied"] is False
    assert preview["preview"] == {"validate_only": True}
    token = preview["confirm_token"]

    # token binds to the exact (op, payload) the executor builds.
    expected = confirm_token(
        "ga4.admin.create_key_event", {"customer_id": "123456", "operations": ops}
    )
    assert token == expected

    applied = ex.execute(
        op="ga4.admin.create_key_event",
        customer_id="123456",
        operations=ops,
        confirm=str(token),
    )
    assert applied["applied"] is True
    assert applied["result"] == {"validate_only": False}
    assert isinstance(applied["audit_signature"], str)


def test_create_key_event_blocked_in_read_only_mode():
    ex = WriteExecutor(_fake_mutate, SafetyMode(read_only=True), AuditLedger.ephemeral())
    ops = mutate_tools.build_create_key_event_ops("123456", "purchase")
    out = ex.execute(op="ga4.admin.create_key_event", customer_id="123456", operations=ops)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


# --- graceful degradation when the mutate backend is absent ---------------------------------


def test_write_tools_degrade_without_mutate_backend():
    from quantum_ads.server import build_server

    # Only the read backends wired; ga4.admin.mutate is intentionally absent.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"ga4.data": _fake_read, "ga4.admin": _fake_read},
        connectors=[register_ga4_write],
    )
    # Registration still succeeds even though the mutate backend is missing.
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ga4.admin.create_key_event" in names
