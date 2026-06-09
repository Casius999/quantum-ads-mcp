"""Write-plane tests for the ADH connector: op builder + guarded execution.

Unit-tests the pure ``query_ops`` builder, then drives a guarded stored-query creation end-to-end
with a fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the read-only block, and the missing-backend
degradation. ``customer_id`` is bound to the ADH account id (``account_id``).
"""

from quantum_ads.connectors.adh import query_ops, register_adh
from quantum_ads.connectors.adh.write.connector import register_adh_write
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


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return []


def _fake_mutate(
    account_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only, "account_id": account_id}


def _build():
    from quantum_ads.server import build_server

    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"adh.api": _fake_read, "adh.mutate": _fake_mutate},
        connectors=[register_adh],
    )


# --- registration -------------------------------------------------------------


def test_adh_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "adh.query.create" in names


def test_adh_write_tools_marked_not_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("adh.query.create").read_only is False


# --- pure op builder (unit) ---------------------------------------------------


def test_build_create_query_ops_shape():
    ops = query_ops.build_create_query_ops("Reach by campaign", "SELECT 1")
    assert ops == [
        {
            "entity": "analysis_query",
            "action": "create",
            "title": "Reach by campaign",
            "query_text": "SELECT 1",
        }
    ]


def test_build_create_query_ops_entity_constant():
    ops = query_ops.build_create_query_ops("t", "SELECT 1")
    assert ops[0]["entity"] == query_ops.ENTITY_ANALYSIS_QUERY


# --- guarded write flow (integration, fake MutateFn) --------------------------


class _RecordingApp:
    """Captures the functions registered via FastMCP's ``add_tool`` so we can call them."""

    def __init__(self) -> None:
        self.fns: dict[str, object] = {}

    def tool(self, name: str, description: str):
        def decorator(fn):
            self.fns[name] = fn
            return fn

        return decorator


def _ctx(backends: dict[str, object], read_only: bool = False) -> ServerContext:
    return ServerContext(
        creds={},
        version="v1",
        stream_factory=_stream,
        version_manager=VersionManager("v1", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=read_only),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends=backends,
    )


def test_query_create_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []
    seen_account: list[str] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        seen_account.append(account_id)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"adh.mutate": fake_mutate})
    register_adh_write(app, ctx)  # type: ignore[arg-type]
    create = app.fns["adh.query.create"]

    first = create(  # type: ignore[operator]
        customer_id="CID1", title="Reach", query_text="SELECT 1"
    )
    assert first["applied"] is False
    assert "confirm_token" in first
    assert isinstance(first["preview"], dict)
    assert calls == [True]  # validate_only preview only
    # customer_id is bound to the ADH account id.
    assert seen_account == ["CID1"]

    token = first["confirm_token"]
    second = create(  # type: ignore[operator]
        customer_id="CID1", title="Reach", query_text="SELECT 1", confirm=str(token)
    )
    assert second["applied"] is True
    assert "audit_signature" in second
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_query_create_blocked_in_read_only_mode():
    app = _RecordingApp()
    ctx = _ctx({"adh.mutate": _fake_mutate}, read_only=True)
    register_adh_write(app, ctx)  # type: ignore[arg-type]
    create = app.fns["adh.query.create"]

    out = create(customer_id="CID1", title="Reach", query_text="SELECT 1")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


def test_query_create_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({"adh.api": _fake_read})  # adh.mutate intentionally absent
    register_adh_write(app, ctx)  # type: ignore[arg-type]
    create = app.fns["adh.query.create"]

    out = create(customer_id="CID1", title="Reach", query_text="SELECT 1")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
