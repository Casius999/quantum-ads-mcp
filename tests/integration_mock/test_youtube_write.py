from quantum_ads.connectors.youtube.connector import register_youtube
from quantum_ads.connectors.youtube.write.mutate_tools import (
    build_playlist_add_item_ops,
    build_update_video_ops,
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
    return {"ok": True, "validate_only": validate_only, "channel_id": account_path}


def _build():
    from quantum_ads.server import build_server

    return build_server(
        env=_env(),
        stream_factory=_stream,
        backends={
            "youtube.data": _fake_read,
            "youtube.analytics": _fake_read,
            "youtube.mutate": _fake_mutate,
        },
        connectors=[register_youtube],
    )


def test_youtube_write_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "youtube.video.update" in names
    assert "youtube.playlist.add_item" in names


def test_youtube_write_tools_marked_not_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("youtube.video.update").read_only is False
    assert assembled.registry.describe_tool("youtube.playlist.add_item").read_only is False


# --- pure builder unit tests ---


def test_build_update_video_ops():
    ops = build_update_video_ops("vid123", {"title": "New title", "tags": ["a", "b"]})
    assert ops == [
        {
            "action": "update_video",
            "video_id": "vid123",
            "fields": {"title": "New title", "tags": ["a", "b"]},
        }
    ]


def test_build_update_video_ops_copies_fields():
    fields: dict[str, object] = {"title": "x"}
    ops = build_update_video_ops("vid123", fields)
    fields["title"] = "mutated"
    assert ops[0]["fields"] == {"title": "x"}  # builder took a copy


def test_build_playlist_add_item_ops():
    ops = build_playlist_add_item_ops("PL123", "vid123")
    assert ops == [{"action": "playlist_add_item", "playlist_id": "PL123", "video_id": "vid123"}]


# --- guarded-flow integration via the connector's registered callable ---


def _ctx_with(backends: dict[str, object], *, read_only: bool):
    from quantum_ads.core.context import ServerContext
    from quantum_ads.core.registry.registry import ConnectorRegistry
    from quantum_ads.core.safety.audit import AuditLedger
    from quantum_ads.core.safety.mode import SafetyMode
    from quantum_ads.core.versioning.version_manager import VersionManager

    return ServerContext(
        creds={},
        version="v3",
        stream_factory=_stream,
        version_manager=VersionManager("v3", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=read_only),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends=backends,
    )


def _capture_tools(ctx) -> dict[str, object]:
    captured: dict[str, object] = {}

    class _App:
        def tool(self, name: str, description: str):
            def deco(fn):
                captured[name] = fn
                return fn

            return deco

    register_youtube(_App(), ctx)  # type: ignore[arg-type]
    return captured


def test_video_update_two_step_confirm_flow():
    ctx = _ctx_with({"youtube.data": _fake_read, "youtube.mutate": _fake_mutate}, read_only=False)
    captured = _capture_tools(ctx)
    video_update = captured["youtube.video.update"]

    preview = video_update(video_id="vid123", fields={"title": "New"})
    assert preview["applied"] is False
    assert "confirm_token" in preview
    assert isinstance(preview["preview"], dict)

    token = preview["confirm_token"]
    applied = video_update(video_id="vid123", fields={"title": "New"}, confirm=str(token))
    assert applied["applied"] is True
    assert "audit_signature" in applied


def test_playlist_add_item_blocked_in_read_only_mode():
    ctx = _ctx_with({"youtube.data": _fake_read, "youtube.mutate": _fake_mutate}, read_only=True)
    captured = _capture_tools(ctx)
    add_item = captured["youtube.playlist.add_item"]

    out = add_item(playlist_id="PL123", video_id="vid123")
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "READ_ONLY"


def test_video_update_reports_backend_not_configured_when_mutate_unwired():
    ctx = _ctx_with({"youtube.data": _fake_read}, read_only=False)  # youtube.mutate absent
    captured = _capture_tools(ctx)
    video_update = captured["youtube.video.update"]

    out = video_update(video_id="vid123", fields={"title": "x"})
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
