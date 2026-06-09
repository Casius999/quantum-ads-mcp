"""Google Workspace guarded write connector: op builders + guarded execution + degradation.

Unit-tests the pure ``sheets_ops`` builders, then drives a guarded mutation end-to-end with a
fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the missing-backend degradation, and the
read-only block. The real googleapiclient SDK is never imported.
"""

from quantum_ads.connectors.workspace import register_workspace
from quantum_ads.connectors.workspace.write import sheets_ops
from quantum_ads.connectors.workspace.write.connector import register_workspace_write
from quantum_ads.core.context import ServerContext
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.confirm import confirm_token
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.safety.write_executor import WriteExecutor
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
    return [{"operation": operation}]


def _fake_mutate(
    account_id: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"workspace.api": _fake_read, "workspace.mutate": _fake_mutate}


# --- registration -----------------------------------------------------------------------------


def test_workspace_write_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_workspace],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "workspace.sheets.write_range" in names
    assert "workspace.sheets.create" in names
    assert "workspace.slides.create_deck" in names


def test_workspace_write_tools_marked_not_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_workspace_write],
    )
    assert assembled.registry.describe_tool("workspace.sheets.write_range").read_only is False
    assert assembled.registry.describe_tool("workspace.sheets.create").read_only is False
    assert assembled.registry.describe_tool("workspace.slides.create_deck").read_only is False


# --- pure op builders (unit) ------------------------------------------------------------------


def test_build_write_range_ops():
    ops = sheets_ops.build_write_range_ops("sheet-1", "Sheet1!A1:B1", [["a", "b"]])
    assert ops == [
        {
            "entity": "sheet_range",
            "action": "write_range",
            "spreadsheet_id": "sheet-1",
            "range_a1": "Sheet1!A1:B1",
            "values": [["a", "b"]],
        }
    ]


def test_build_create_spreadsheet_ops():
    ops = sheets_ops.build_create_spreadsheet_ops("Q2 Reporting")
    assert ops == [{"entity": "spreadsheet", "action": "create", "title": "Q2 Reporting"}]


def test_build_create_deck_ops():
    ops = sheets_ops.build_create_deck_ops("Client Review Deck")
    assert ops == [{"entity": "presentation", "action": "create", "title": "Client Review Deck"}]


# --- guarded flow through WriteExecutor (preview -> confirm -> applied) ------------------------


def _executor() -> WriteExecutor:
    return WriteExecutor(_fake_mutate, SafetyMode(read_only=False), AuditLedger.ephemeral())


def test_write_range_preview_then_confirm():
    ex = _executor()
    ops = sheets_ops.build_write_range_ops("sheet-1", "Sheet1!A1:B1", [["a", "b"]])

    preview = ex.execute(op="workspace.sheets.write_range", customer_id="sheet-1", operations=ops)
    assert preview["applied"] is False
    assert preview["preview"] == {"validate_only": True}
    token = preview["confirm_token"]

    # token binds to the exact (op, payload) the executor builds.
    expected = confirm_token(
        "workspace.sheets.write_range",
        {"customer_id": "sheet-1", "operations": ops},
    )
    assert token == expected

    applied = ex.execute(
        op="workspace.sheets.write_range",
        customer_id="sheet-1",
        operations=ops,
        confirm=str(token),
    )
    assert applied["applied"] is True
    assert applied["result"] == {"validate_only": False}
    assert isinstance(applied["audit_signature"], str)


def test_write_range_blocked_in_read_only_mode():
    ex = WriteExecutor(_fake_mutate, SafetyMode(read_only=True), AuditLedger.ephemeral())
    ops = sheets_ops.build_write_range_ops("sheet-1", "Sheet1!A1:B1", [["a", "b"]])
    out = ex.execute(op="workspace.sheets.write_range", customer_id="sheet-1", operations=ops)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


# --- guarded flow through the registered FastMCP callable (fake MutateFn) ----------------------


def _ctx(backends: dict[str, object], read_only: bool = False) -> ServerContext:
    return ServerContext(
        creds={},
        version="v4",
        stream_factory=lambda c, v: lambda cid, q: [],
        version_manager=VersionManager("v4", client_factory=lambda c, v: None),
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


def test_write_range_previews_then_confirms_via_registered_tool():
    calls: list[bool] = []

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {"account_id": account_id, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"workspace.mutate": fake_mutate})
    register_workspace_write(app, ctx)  # type: ignore[arg-type]
    write_range = app.fns["workspace.sheets.write_range"]

    first = write_range(  # type: ignore[operator]
        spreadsheet_id="sheet-1", range_a1="Sheet1!A1:B1", values=[["a", "b"]]
    )
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only

    token = first["confirm_token"]
    second = write_range(  # type: ignore[operator]
        spreadsheet_id="sheet-1",
        range_a1="Sheet1!A1:B1",
        values=[["a", "b"]],
        confirm=token,
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_create_spreadsheet_uses_drive_account_scope():
    seen: dict[str, object] = {}

    def fake_mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        seen["account_id"] = account_id
        return {"validate_only": validate_only}

    app = _RecordingApp()
    ctx = _ctx({"workspace.mutate": fake_mutate})
    register_workspace_write(app, ctx)  # type: ignore[arg-type]
    create = app.fns["workspace.sheets.create"]

    create(title="New Report")  # type: ignore[operator]
    assert seen["account_id"] == "drive"


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no workspace.mutate backend
    register_workspace_write(app, ctx)  # type: ignore[arg-type]
    create_deck = app.fns["workspace.slides.create_deck"]

    out = create_deck(title="Deck")  # type: ignore[operator]
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"
