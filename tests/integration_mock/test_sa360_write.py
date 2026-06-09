"""Write-plane tests for the SA360 connector: op builder + guarded execution.

Unit-tests the pure ``conversion_ops`` builder, then drives a guarded upload end-to-end with a
fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the read-only block, and the missing-backend
degradation. ``customer_id`` is bound to the SA360 account id (``account_id``).
"""

from quantum_ads.connectors.sa360 import conversion_ops, register_sa360
from quantum_ads.connectors.sa360.write.connector import register_sa360_write
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
        backends={"sa360.api": _fake_read, "sa360.mutate": _fake_mutate},
        connectors=[register_sa360],
    )


# --- registration -------------------------------------------------------------


def test_sa360_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "sa360.conversion.upload" in names


def test_sa360_write_tools_marked_not_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("sa360.conversion.upload").read_only is False


# --- pure op builder (unit) ---------------------------------------------------


def test_build_upload_conversions_ops_shape():
    conversions: list[dict[str, object]] = [{"conversionId": "x1", "conversionQuantity": 1}]
    ops = conversion_ops.build_upload_conversions_ops(conversions)
    assert ops == [
        {
            "action": "upload_conversions",
            "conversions": [{"conversionId": "x1", "conversionQuantity": 1}],
        }
    ]


def test_build_upload_conversions_ops_copies_inputs_no_mutation_leak():
    conversions: list[dict[str, object]] = [{"conversionId": "x1"}]
    ops = conversion_ops.build_upload_conversions_ops(conversions)
    conversions.append({"conversionId": "extra"})
    # The op must hold a snapshot, not the caller's list.
    assert ops[0]["conversions"] == [{"conversionId": "x1"}]


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
        version="v0",
        stream_factory=_stream,
        version_manager=VersionManager("v0", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=read_only),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends=backends,
    )


def test_conversion_upload_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []
    seen_account: list[str] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        seen_account.append(account_id)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"sa360.mutate": fake_mutate})
    register_sa360_write(app, ctx)  # type: ignore[arg-type]
    upload = app.fns["sa360.conversion.upload"]

    first = upload(  # type: ignore[operator]
        customer_id="CID1", conversions=[{"conversionId": "x1"}]
    )
    assert first["applied"] is False
    assert "confirm_token" in first
    assert isinstance(first["preview"], dict)
    assert calls == [True]  # validate_only preview only
    # customer_id is bound to the SA360 account id.
    assert seen_account == ["CID1"]

    token = first["confirm_token"]
    second = upload(  # type: ignore[operator]
        customer_id="CID1", conversions=[{"conversionId": "x1"}], confirm=str(token)
    )
    assert second["applied"] is True
    assert "audit_signature" in second
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_conversion_upload_blocked_in_read_only_mode():
    app = _RecordingApp()
    ctx = _ctx({"sa360.mutate": _fake_mutate}, read_only=True)
    register_sa360_write(app, ctx)  # type: ignore[arg-type]
    upload = app.fns["sa360.conversion.upload"]

    out = upload(customer_id="CID1", conversions=[{"conversionId": "x1"}])  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


def test_conversion_upload_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({"sa360.api": _fake_read})  # sa360.mutate intentionally absent
    register_sa360_write(app, ctx)  # type: ignore[arg-type]
    upload = app.fns["sa360.conversion.upload"]

    out = upload(customer_id="CID1", conversions=[{"conversionId": "x1"}])  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
