"""Mount the YouTube (Data API v3 + Analytics/Reporting) read + guarded-write tools.

Read tools degrade gracefully when their backend is unwired (structured
``BACKEND_NOT_CONFIGURED``); write tools are guarded by the shared ``WriteExecutor``
(validate_only preview + two-step confirm + signed audit) and degrade when ``youtube.mutate``
is unwired. Two read backends are read lazily per call:
  - ``youtube.data``      -> Data API v3 ReadFn (channels / videos / batch stats / playlistItems)
  - ``youtube.analytics`` -> Analytics+Reporting ReadFn (analytics query + report-job ensure)

This is the organic counterpart to the Google Ads video-campaign surface: organic video metrics
here pair with paid video performance there. ``search.list`` is intentionally NOT exposed — it
is quota-scarce; enumerate uploads via the uploads playlist instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from ...core.safety.write_executor import MutateFn, WriteExecutor
from .read import list_tools
from .types import ReadFn
from .write.mutate_tools import build_playlist_add_item_ops, build_update_video_ops

_DATA_BACKEND = "youtube.data"
_ANALYTICS_BACKEND = "youtube.analytics"
_MUTATE_BACKEND = "youtube.mutate"

_DATA_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "youtube.data not wired"}
}
_ANALYTICS_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "youtube.analytics not wired"}
}
_MUTATE_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "youtube.mutate not wired"}
}


def register_youtube(app: FastMCP, ctx: ServerContext) -> None:
    # --- read tools (backends: youtube.data + youtube.analytics) ---
    def _data() -> ReadFn | None:
        backend = ctx.backend(_DATA_BACKEND)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def _analytics() -> ReadFn | None:
        backend = ctx.backend(_ANALYTICS_BACKEND)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def youtube_channel_get(channel_id: str) -> dict[str, object]:
        read = _data()
        if read is None:
            return dict(_DATA_NOT_CONFIGURED)
        return list_tools.get_channel(channel_id=channel_id, read=read)

    def youtube_videos_list(video_ids: list[str]) -> dict[str, object]:
        read = _data()
        if read is None:
            return dict(_DATA_NOT_CONFIGURED)
        return list_tools.list_videos(video_ids=video_ids, read=read)

    def youtube_video_batch_stats(video_ids: list[str]) -> dict[str, object]:
        read = _data()
        if read is None:
            return dict(_DATA_NOT_CONFIGURED)
        return list_tools.video_batch_stats(video_ids=video_ids, read=read)

    def youtube_playlist_items_list(playlist_id: str) -> dict[str, object]:
        read = _data()
        if read is None:
            return dict(_DATA_NOT_CONFIGURED)
        return list_tools.list_playlist_items(playlist_id=playlist_id, read=read)

    def youtube_analytics_query(
        ids: str,
        start_date: str,
        end_date: str,
        metrics: list[str],
        dimensions: list[str],
    ) -> dict[str, object]:
        read = _analytics()
        if read is None:
            return dict(_ANALYTICS_NOT_CONFIGURED)
        return list_tools.analytics_query(
            ids=ids,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            dimensions=dimensions,
            read=read,
        )

    def youtube_reporting_ensure_jobs(report_type_ids: list[str]) -> dict[str, object]:
        read = _analytics()
        if read is None:
            return dict(_ANALYTICS_NOT_CONFIGURED)
        return list_tools.ensure_reporting_jobs(report_type_ids=report_type_ids, read=read)

    read_tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "youtube.channel.get",
            "Get a channel's snippet/statistics + uploads-playlist id (Data API v3).",
            youtube_channel_get,
        ),
        (
            "youtube.videos.list",
            "List full video resources for a batch of video ids (Data API v3).",
            youtube_videos_list,
        ),
        (
            "youtube.video.batch_stats",
            "Cheap bulk statistics for many video ids via 2026 videos.batchGetStats.",
            youtube_video_batch_stats,
        ),
        (
            "youtube.playlist_items.list",
            "Enumerate playlist items (use the uploads playlist; avoid quota-scarce search.list).",
            youtube_playlist_items_list,
        ),
        (
            "youtube.analytics.query",
            "Query organic video performance (views/watch time/etc.) from YouTube Analytics.",
            youtube_analytics_query,
        ),
        (
            "youtube.reporting.ensure_jobs",
            "Ensure Reporting API bulk-report jobs exist (reports retained 30/60d — persist early).",
            youtube_reporting_ensure_jobs,
        ),
    ]

    # --- write tools (backend: youtube.mutate, guarded; account_id=channel_id) ---
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(_MUTATE_BACKEND)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def youtube_video_update(
        video_id: str, fields: dict[str, object], confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_MUTATE_NOT_CONFIGURED)
        return ex.execute(
            op="youtube.video.update",
            customer_id=video_id,
            operations=build_update_video_ops(video_id, fields),
            confirm=confirm,
        )

    def youtube_playlist_add_item(
        playlist_id: str, video_id: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_MUTATE_NOT_CONFIGURED)
        return ex.execute(
            op="youtube.playlist.add_item",
            customer_id=playlist_id,
            operations=build_playlist_add_item_ops(playlist_id, video_id),
            confirm=confirm,
        )

    write_tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "youtube.video.update",
            "Update video metadata (title/description/tags) — guarded; no media upload.",
            youtube_video_update,
        ),
        (
            "youtube.playlist.add_item",
            "Add a video to a playlist (playlistItems.insert) — guarded.",
            youtube_playlist_add_item,
        ),
    ]

    for name, description, fn in read_tools + write_tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="youtube",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in read_tools],
        )
    )
    ctx.registry.register(
        Capability(
            connector="youtube",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in write_tools
            ],
        )
    )
