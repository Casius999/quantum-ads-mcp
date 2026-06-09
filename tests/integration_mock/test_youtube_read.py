from quantum_ads.connectors.youtube.connector import register_youtube
from quantum_ads.connectors.youtube.read import list_tools
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
    return [{"operation": operation, "params": params}]


def _fake_mutate(
    account_path: str, operations: list[dict[str, object]], validate_only: bool
) -> dict[str, object]:
    return {"ok": True, "validate_only": validate_only}


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


def test_youtube_read_tools_registered():
    assembled = _build()
    names = {t.name for t in assembled.registry.all_tools()}
    assert "youtube.channel.get" in names
    assert "youtube.videos.list" in names
    assert "youtube.video.batch_stats" in names
    assert "youtube.playlist_items.list" in names
    assert "youtube.analytics.query" in names
    assert "youtube.reporting.ensure_jobs" in names


def test_youtube_read_tools_marked_read_only():
    assembled = _build()
    assert assembled.registry.describe_tool("youtube.channel.get").read_only is True
    assert assembled.registry.describe_tool("youtube.analytics.query").read_only is True
    assert assembled.registry.describe_tool("youtube.video.batch_stats").read_only is True


# --- pure builder unit tests ---


def test_build_channel_params():
    assert list_tools.build_channel_params("UC_abc") == {"channel_id": "UC_abc"}


def test_build_video_ids_params_copies_list():
    src = ["a", "b"]
    out = list_tools.build_video_ids_params(src)
    assert out == {"video_ids": ["a", "b"]}
    src.append("c")
    assert out["video_ids"] == ["a", "b"]  # builder took a copy


def test_build_playlist_items_params():
    assert list_tools.build_playlist_items_params("PL123") == {"playlist_id": "PL123"}


def test_build_analytics_params():
    out = list_tools.build_analytics_params(
        ids="channel==MINE",
        start_date="2026-05-01",
        end_date="2026-05-31",
        metrics=["views", "estimatedMinutesWatched"],
        dimensions=["day"],
    )
    assert out == {
        "ids": "channel==MINE",
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "metrics": ["views", "estimatedMinutesWatched"],
        "dimensions": ["day"],
    }


def test_build_reporting_jobs_params():
    assert list_tools.build_reporting_jobs_params(["channel_basic_a1"]) == {
        "report_type_ids": ["channel_basic_a1"]
    }


# --- runner / tool wiring unit tests ---


def test_get_channel_invokes_backend():
    out = list_tools.get_channel(channel_id="UC_x", read=_fake_read)
    assert out["row_count"] == 1
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "channels.get"
    assert rows[0]["params"] == {"channel_id": "UC_x"}


def test_video_batch_stats_uses_batch_endpoint():
    out = list_tools.video_batch_stats(video_ids=["v1", "v2"], read=_fake_read)
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "videos.batchGetStats"
    assert rows[0]["params"] == {"video_ids": ["v1", "v2"]}


def test_list_playlist_items_passes_playlist_id():
    out = list_tools.list_playlist_items(playlist_id="UU_uploads", read=_fake_read)
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "playlistItems.list"
    assert rows[0]["params"] == {"playlist_id": "UU_uploads"}


def test_analytics_query_passes_all_params():
    out = list_tools.analytics_query(
        ids="channel==MINE",
        start_date="2026-05-01",
        end_date="2026-05-31",
        metrics=["views"],
        dimensions=["day"],
        read=_fake_read,
    )
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "analytics.query"
    params = rows[0]["params"]
    assert isinstance(params, dict)
    assert params["ids"] == "channel==MINE"
    assert params["metrics"] == ["views"]


def test_ensure_reporting_jobs_passes_report_type_ids():
    out = list_tools.ensure_reporting_jobs(report_type_ids=["channel_basic_a1"], read=_fake_read)
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "reporting.ensureJobs"
    assert rows[0]["params"] == {"report_type_ids": ["channel_basic_a1"]}


def test_read_tool_reports_backend_not_configured_when_data_unwired():
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
        version="v3",
        stream_factory=_stream,
        version_manager=VersionManager("v3", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=False),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends={"youtube.analytics": _fake_read, "youtube.mutate": _fake_mutate},
    )
    register_youtube(_App(), ctx)  # type: ignore[arg-type]
    channel_get = captured["youtube.channel.get"]

    out = channel_get(channel_id="UC_x")
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_analytics_tool_reports_backend_not_configured_when_analytics_unwired():
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
        version="v3",
        stream_factory=_stream,
        version_manager=VersionManager("v3", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=False),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        backends={"youtube.data": _fake_read, "youtube.mutate": _fake_mutate},
    )
    register_youtube(_App(), ctx)  # type: ignore[arg-type]
    analytics_query = captured["youtube.analytics.query"]

    out = analytics_query(
        ids="channel==MINE",
        start_date="2026-05-01",
        end_date="2026-05-31",
        metrics=["views"],
        dimensions=["day"],
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
