"""Write-plane tests for the DV360 connector: op builders + guarded execution.

Unit-tests the pure ``mutate_tools`` builders, then drives a guarded mutation end-to-end with a
fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the read-only block, and the missing-backend
degradation. ``customer_id`` is bound to the DV360 advertiser id.
"""

from quantum_ads.connectors.dv360 import register_dv360
from quantum_ads.connectors.dv360.write import mutate_tools
from quantum_ads.connectors.dv360.write.connector import register_dv360_write
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
    advertiser_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only, "advertiser_id": advertiser_id}


def _build():
    from quantum_ads.server import build_server

    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"dv360.api": _fake_read, "dv360.mutate": _fake_mutate},
        connectors=[register_dv360],
    )


# --- registration -------------------------------------------------------------


def test_dv360_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "dv360.line_item.update" in names
    assert "dv360.line_item.set_status" in names


def test_dv360_write_tools_marked_not_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("dv360.line_item.update").read_only is False
    assert assembled.registry.describe_tool("dv360.line_item.set_status").read_only is False


# --- pure op builders (unit) --------------------------------------------------


def test_build_update_line_item_ops():
    ops = mutate_tools.build_update_line_item_ops("ADV1", "LI9", {"displayName": "Renamed"})
    assert ops == [
        {
            "action": "update_line_item",
            "advertiser_id": "ADV1",
            "line_item_id": "LI9",
            "fields": {"displayName": "Renamed"},
        }
    ]


def test_build_set_line_item_status_ops():
    ops = mutate_tools.build_set_line_item_status_ops("ADV1", "LI9", "ENTITY_STATUS_PAUSED")
    assert ops == [
        {
            "action": "set_line_item_status",
            "advertiser_id": "ADV1",
            "line_item_id": "LI9",
            "entity_status": "ENTITY_STATUS_PAUSED",
        }
    ]


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
        version="v4",
        stream_factory=_stream,
        version_manager=VersionManager("v4", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=read_only),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends=backends,
    )


def test_update_line_item_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []

    def fake_mutate(
        advertiser_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {
            "advertiser_id": advertiser_id,
            "validate_only": validate_only,
            "ops": len(operations),
        }

    app = _RecordingApp()
    ctx = _ctx({"dv360.mutate": fake_mutate})
    register_dv360_write(app, ctx)  # type: ignore[arg-type]
    update = app.fns["dv360.line_item.update"]

    first = update(  # type: ignore[operator]
        advertiser_id="ADV1", line_item_id="LI9", fields={"displayName": "X"}
    )
    assert first["applied"] is False
    assert "confirm_token" in first
    assert isinstance(first["preview"], dict)
    assert calls == [True]  # validate_only preview only

    token = first["confirm_token"]
    second = update(  # type: ignore[operator]
        advertiser_id="ADV1", line_item_id="LI9", fields={"displayName": "X"}, confirm=str(token)
    )
    assert second["applied"] is True
    assert "audit_signature" in second
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_set_status_blocked_in_read_only_mode():
    app = _RecordingApp()
    ctx = _ctx({"dv360.mutate": _fake_mutate}, read_only=True)
    register_dv360_write(app, ctx)  # type: ignore[arg-type]
    set_status = app.fns["dv360.line_item.set_status"]

    out = set_status(  # type: ignore[operator]
        advertiser_id="ADV1", line_item_id="LI9", entity_status="ENTITY_STATUS_PAUSED"
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({"dv360.api": _fake_read})  # dv360.mutate intentionally absent
    register_dv360_write(app, ctx)  # type: ignore[arg-type]
    update = app.fns["dv360.line_item.update"]

    out = update(advertiser_id="ADV1", line_item_id="LI9", fields={})  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
