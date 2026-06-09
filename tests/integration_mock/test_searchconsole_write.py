"""Search Console guarded write connector: op builders + guarded execution + degradation.

Unit-tests the pure ``sitemap_ops`` builders, then drives a guarded mutation end-to-end with a
fake ``MutateFn`` (no SDK) through the shared ``WriteExecutor`` to confirm the
validate_only-preview -> confirm -> apply flow, the missing-backend degradation, and the
read-only block. The real googleapiclient SDK is never imported.
"""

from quantum_ads.connectors.searchconsole import register_searchconsole
from quantum_ads.connectors.searchconsole.write import sitemap_ops
from quantum_ads.connectors.searchconsole.write.connector import register_searchconsole_write
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
    site_url: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"validate_only": validate_only}


def _backends() -> dict[str, object]:
    return {"searchconsole.api": _fake_read, "searchconsole.mutate": _fake_mutate}


# --- registration -----------------------------------------------------------------------------


def test_searchconsole_write_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_searchconsole],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "searchconsole.sitemaps.submit" in names
    assert "searchconsole.sitemaps.delete" in names


def test_searchconsole_write_tools_marked_not_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        backends=_backends(),
        connectors=[register_searchconsole_write],
    )
    assert assembled.registry.describe_tool("searchconsole.sitemaps.submit").read_only is False
    assert assembled.registry.describe_tool("searchconsole.sitemaps.delete").read_only is False


# --- pure op builders (unit) ------------------------------------------------------------------


def test_build_submit_sitemap_ops():
    ops = sitemap_ops.build_submit_sitemap_ops(
        "https://example.com/", "https://example.com/sitemap.xml"
    )
    assert ops == [
        {
            "entity": "sitemap",
            "action": "submit",
            "site_url": "https://example.com/",
            "feedpath": "https://example.com/sitemap.xml",
        }
    ]


def test_build_delete_sitemap_ops():
    ops = sitemap_ops.build_delete_sitemap_ops(
        "https://example.com/", "https://example.com/sitemap.xml"
    )
    assert ops == [
        {
            "entity": "sitemap",
            "action": "delete",
            "site_url": "https://example.com/",
            "feedpath": "https://example.com/sitemap.xml",
        }
    ]


# --- guarded flow through WriteExecutor (preview -> confirm -> applied) ------------------------


def _executor() -> WriteExecutor:
    return WriteExecutor(_fake_mutate, SafetyMode(read_only=False), AuditLedger.ephemeral())


def test_submit_sitemap_preview_then_confirm():
    ex = _executor()
    ops = sitemap_ops.build_submit_sitemap_ops(
        "https://example.com/", "https://example.com/sitemap.xml"
    )

    preview = ex.execute(
        op="searchconsole.sitemaps.submit", customer_id="https://example.com/", operations=ops
    )
    assert preview["applied"] is False
    assert preview["preview"] == {"validate_only": True}
    token = preview["confirm_token"]

    # token binds to the exact (op, payload) the executor builds.
    expected = confirm_token(
        "searchconsole.sitemaps.submit",
        {"customer_id": "https://example.com/", "operations": ops},
    )
    assert token == expected

    applied = ex.execute(
        op="searchconsole.sitemaps.submit",
        customer_id="https://example.com/",
        operations=ops,
        confirm=str(token),
    )
    assert applied["applied"] is True
    assert applied["result"] == {"validate_only": False}
    assert isinstance(applied["audit_signature"], str)


def test_submit_sitemap_blocked_in_read_only_mode():
    ex = WriteExecutor(_fake_mutate, SafetyMode(read_only=True), AuditLedger.ephemeral())
    ops = sitemap_ops.build_submit_sitemap_ops(
        "https://example.com/", "https://example.com/sitemap.xml"
    )
    out = ex.execute(
        op="searchconsole.sitemaps.submit", customer_id="https://example.com/", operations=ops
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


# --- guarded flow through the registered FastMCP callable (fake MutateFn) ----------------------


def _ctx(backends: dict[str, object], read_only: bool = False) -> ServerContext:
    return ServerContext(
        creds={},
        version="v3",
        stream_factory=lambda c, v: lambda cid, q: [],
        version_manager=VersionManager("v3", client_factory=lambda c, v: None),
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


def test_submit_previews_then_confirms_via_registered_tool():
    calls: list[bool] = []

    def fake_mutate(
        site_url: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        calls.append(validate_only)
        return {"site_url": site_url, "validate_only": validate_only, "ops": len(operations)}

    app = _RecordingApp()
    ctx = _ctx({"searchconsole.mutate": fake_mutate})
    register_searchconsole_write(app, ctx)  # type: ignore[arg-type]
    submit = app.fns["searchconsole.sitemaps.submit"]

    first = submit(  # type: ignore[operator]
        site_url="https://example.com/", feedpath="https://example.com/sitemap.xml"
    )
    assert first["applied"] is False
    assert calls == [True]  # validate_only preview only

    token = first["confirm_token"]
    second = submit(  # type: ignore[operator]
        site_url="https://example.com/",
        feedpath="https://example.com/sitemap.xml",
        confirm=token,
    )
    assert second["applied"] is True
    assert calls == [True, True, False]  # preview re-run, then real apply


def test_write_tool_degrades_when_mutate_backend_missing():
    app = _RecordingApp()
    ctx = _ctx({})  # no searchconsole.mutate backend
    register_searchconsole_write(app, ctx)  # type: ignore[arg-type]
    delete = app.fns["searchconsole.sitemaps.delete"]

    out = delete(  # type: ignore[operator]
        site_url="https://example.com/", feedpath="https://example.com/sitemap.xml"
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "MUTATE_NOT_CONFIGURED"
