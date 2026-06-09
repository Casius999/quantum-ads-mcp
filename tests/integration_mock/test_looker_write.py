"""Write-plane tests for the Looker connector: op builder + guarded execution.

Unit-tests the pure ``write_ops`` builder, then drives a guarded mutation end-to-end with a fake
``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the validate_only-preview ->
confirm -> apply flow, the read_only flags, and the missing-backend / read-only degradations.
``account_id`` (the MutateFn's first arg) is the constant ``"looker"``.
"""

from quantum_ads.connectors.looker import write_ops
from quantum_ads.connectors.looker.connector import register_looker
from quantum_ads.core.context import ServerContext
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager
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


# --- pure op builder (unit) ---------------------------------------------------


def test_build_create_dashboard_ops():
    ops = write_ops.build_create_dashboard_ops("Spend overview", "ecommerce")
    assert ops == [
        {
            "entity": "dashboard",
            "action": "create",
            "title": "Spend overview",
            "model": "ecommerce",
        }
    ]


# --- guarded write flow (integration, fake MutateFn) --------------------------


def _ctx(backends: dict[str, object], read_only: bool = False) -> ServerContext:
    return ServerContext(
        creds={},
        version="v1",
        stream_factory=lambda c, v: lambda cid, q: [],
        version_manager=VersionManager("v1", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=read_only),
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


def test_dashboard_create_previews_then_confirms_with_fake_mutate():
    calls: list[bool] = []
    seen_account: list[str] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        seen_account.append(account_id)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"looker.mutate": fake_mutate})
    register_looker(app, ctx)  # type: ignore[arg-type]
    create = app.fns["looker.dashboard.create"]

    first = create(title="Spend overview", model="ecommerce")  # type: ignore[operator]
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only
    assert seen_account == ["looker"]  # account_id is the constant "looker"

    token = first["confirm_token"]
    second = create(  # type: ignore[operator]
        title="Spend overview", model="ecommerce", confirm=token
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_write_tools_registered_and_marked_not_read_only():
    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"validate_only": validate_only}

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"looker.mutate": fake_mutate},
        connectors=[register_looker],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "looker.dashboard.create" in names
    assert assembled.registry.describe_tool("looker.dashboard.create").read_only is False


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no looker.mutate backend
    register_looker(app, ctx)  # type: ignore[arg-type]
    create = app.fns["looker.dashboard.create"]

    out = create(title="Spend overview", model="ecommerce")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"


def test_write_blocked_in_read_only_mode():
    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"should": "not be reached for the real apply"}

    app = _RecordingApp()
    ctx = _ctx({"looker.mutate": fake_mutate}, read_only=True)
    register_looker(app, ctx)  # type: ignore[arg-type]
    create = app.fns["looker.dashboard.create"]

    out = create(title="Spend overview", model="ecommerce")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"
