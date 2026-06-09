from quantum_ads.connectors.gtm.connector import register_gtm
from quantum_ads.connectors.gtm.write.mutate_tools import (
    build_create_tag_ops,
    build_create_version_ops,
    build_publish_version_ops,
    build_update_tag_ops,
)
from quantum_ads.core.query.runner import StreamFn


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
    account_path: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only, "parent": account_path}


def _build():
    from quantum_ads.server import build_server

    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={"gtm.api": _fake_read, "gtm.mutate": _fake_mutate},
        connectors=[register_gtm],
    )


def test_gtm_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "gtm.create_tag" in names
    assert "gtm.update_tag" in names
    assert "gtm.create_version" in names
    assert "gtm.publish_version" in names


def test_gtm_write_tools_marked_not_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("gtm.create_tag").read_only is False
    assert assembled.registry.describe_tool("gtm.publish_version").read_only is False


# --- pure builder unit tests ---


def test_build_create_tag_ops():
    ops = build_create_tag_ops(
        "accounts/1/containers/2/workspaces/3",
        "GA4 Config",
        "googtag",
        [{"key": "tagId", "type": "template", "value": "G-XXX"}],
    )
    assert ops == [
        {
            "action": "create_tag",
            "workspace_path": "accounts/1/containers/2/workspaces/3",
            "tag_name": "GA4 Config",
            "tag_type": "googtag",
            "parameter": [{"key": "tagId", "type": "template", "value": "G-XXX"}],
        }
    ]


def test_build_create_tag_ops_defaults_empty_parameters():
    ops = build_create_tag_ops("ws", "name", "html")
    assert ops[0]["parameter"] == []


def test_build_update_tag_ops():
    ops = build_update_tag_ops("accounts/1/containers/2/workspaces/3/tags/9", {"name": "Renamed"})
    assert ops == [
        {
            "action": "update_tag",
            "path": "accounts/1/containers/2/workspaces/3/tags/9",
            "fields": {"name": "Renamed"},
        }
    ]


def test_build_create_version_ops():
    ops = build_create_version_ops("accounts/1/containers/2/workspaces/3", "Release 1")
    assert ops == [
        {
            "action": "create_version",
            "workspace_path": "accounts/1/containers/2/workspaces/3",
            "name": "Release 1",
        }
    ]


def test_build_publish_version_ops():
    ops = build_publish_version_ops("accounts/1/containers/2/versions/5")
    assert ops == [{"action": "publish_version", "path": "accounts/1/containers/2/versions/5"}]


# --- guarded-flow integration via the connector's registered callable ---


def test_create_tag_two_step_confirm_flow():
    # Build a context with the fake mutate backend, capture the tool callables, and exercise
    # the guarded flow (preview without confirm, then apply with the returned confirm_token).
    from quantum_ads.core.context import ServerContext
    from quantum_ads.core.registry.registry import ConnectorRegistry
    from quantum_ads.core.safety.audit import AuditLedger
    from quantum_ads.core.safety.mode import SafetyMode
    from quantum_ads.core.versioning.version_manager import VersionManager

    captured: dict[str, object] = {}

    class _App:
        def tool(self, name: str, description: str):
            def deco(fn):
                captured[name] = fn
                return fn

            return deco

    ctx = ServerContext(
        creds={},
        version="v2",
        stream_factory=_stream,
        version_manager=VersionManager("v2", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=False),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends={"gtm.api": _fake_read, "gtm.mutate": _fake_mutate},
    )
    register_gtm(_App(), ctx)  # type: ignore[arg-type]
    create_tag = captured["gtm.create_tag"]

    preview = create_tag(
        workspace_path="accounts/1/containers/2/workspaces/3",
        tag_name="GA4",
        tag_type="googtag",
    )
    assert preview["applied"] is False
    assert "confirm_token" in preview
    assert isinstance(preview["preview"], dict)

    token = preview["confirm_token"]
    applied = create_tag(
        workspace_path="accounts/1/containers/2/workspaces/3",
        tag_name="GA4",
        tag_type="googtag",
        confirm=str(token),
    )
    assert applied["applied"] is True
    assert "audit_signature" in applied


def test_publish_version_blocked_in_read_only_mode():
    from quantum_ads.core.context import ServerContext
    from quantum_ads.core.registry.registry import ConnectorRegistry
    from quantum_ads.core.safety.audit import AuditLedger
    from quantum_ads.core.safety.mode import SafetyMode
    from quantum_ads.core.versioning.version_manager import VersionManager

    captured: dict[str, object] = {}

    class _App:
        def tool(self, name: str, description: str):
            def deco(fn):
                captured[name] = fn
                return fn

            return deco

    ctx = ServerContext(
        creds={},
        version="v2",
        stream_factory=_stream,
        version_manager=VersionManager("v2", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=True),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends={"gtm.api": _fake_read, "gtm.mutate": _fake_mutate},
    )
    register_gtm(_App(), ctx)  # type: ignore[arg-type]
    publish = captured["gtm.publish_version"]

    out = publish(version_path="accounts/1/containers/2/versions/5")
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


def test_create_tag_reports_backend_not_configured_when_mutate_unwired():
    from quantum_ads.core.context import ServerContext
    from quantum_ads.core.registry.registry import ConnectorRegistry
    from quantum_ads.core.safety.audit import AuditLedger
    from quantum_ads.core.safety.mode import SafetyMode
    from quantum_ads.core.versioning.version_manager import VersionManager

    captured: dict[str, object] = {}

    class _App:
        def tool(self, name: str, description: str):
            def deco(fn):
                captured[name] = fn
                return fn

            return deco

    ctx = ServerContext(
        creds={},
        version="v2",
        stream_factory=_stream,
        version_manager=VersionManager("v2", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=False),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends={"gtm.api": _fake_read},  # gtm.mutate intentionally absent
    )
    register_gtm(_App(), ctx)  # type: ignore[arg-type]
    create_tag = captured["gtm.create_tag"]

    out = create_tag(workspace_path="ws", tag_name="x", tag_type="html")
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
