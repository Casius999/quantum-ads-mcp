"""YouTube read tools: pure param builders + a thin backend-invoking runner.

Each tool names the resource/operation as the ``ReadFn`` first argument and carries the ids in
``params``. Builders are pure (unit-tested directly); ``run_read`` wraps the injected backend
and shapes the shared ``{"rows", "row_count"}`` envelope.

Quota notes (June 2026 Data API v3):
- ``search.list`` is quota-scarce (~100 units/call, ~10k/day default) — AVOID it. Enumerate a
  channel's uploads via the uploads playlist (``playlist_items.list``) instead, which is 1 unit.
- ``videos.list`` accepts a comma-separated id list (up to 50): one call returns statistics for
  many videos at 1 unit — this is the bulk-statistics path (there is no separate batch endpoint).
- Reporting API bulk reports are retained only 30/60 days — call ``reporting.ensure_jobs`` early
  and persist the downloaded reports yourself; they are not re-fetchable after expiry.
"""

from __future__ import annotations

from ..types import ReadFn

# Operation (resource) names passed as the first ReadFn argument.
OP_CHANNEL_GET = "channels.get"
OP_VIDEOS_LIST = "videos.list"
OP_PLAYLIST_ITEMS_LIST = "playlistItems.list"
OP_ANALYTICS_QUERY = "analytics.query"
OP_REPORTING_ENSURE_JOBS = "reporting.ensureJobs"


def build_channel_params(channel_id: str) -> dict[str, object]:
    """Pure: wrap a channel id for ``channels.get``."""
    params: dict[str, object] = {"channel_id": channel_id}
    return params


def build_video_ids_params(video_ids: list[str]) -> dict[str, object]:
    """Pure: wrap a list of video ids for ``videos.list`` (comma-joined into one bulk call)."""
    params: dict[str, object] = {"video_ids": list(video_ids)}
    return params


def build_playlist_items_params(playlist_id: str) -> dict[str, object]:
    """Pure: wrap a playlist id for ``playlistItems.list`` (use the uploads playlist, not search)."""
    params: dict[str, object] = {"playlist_id": playlist_id}
    return params


def build_analytics_params(
    *,
    ids: str,
    start_date: str,
    end_date: str,
    metrics: list[str],
    dimensions: list[str],
) -> dict[str, object]:
    """Pure: build YouTube Analytics query params.

    ``ids`` is the Analytics ``ids`` selector (e.g. ``channel==MINE`` or ``channel==<id>``);
    ``metrics``/``dimensions`` are the Analytics metric/dimension name lists.
    """
    params: dict[str, object] = {
        "ids": ids,
        "start_date": start_date,
        "end_date": end_date,
        "metrics": list(metrics),
        "dimensions": list(dimensions),
    }
    return params


def build_reporting_jobs_params(report_type_ids: list[str]) -> dict[str, object]:
    """Pure: wrap the Reporting API report-type ids to ensure a bulk-report job exists for each."""
    params: dict[str, object] = {"report_type_ids": list(report_type_ids)}
    return params


def run_read(*, operation: str, params: dict[str, object], read: ReadFn) -> dict[str, object]:
    """Invoke the read backend for ``operation`` and wrap rows in the shared envelope."""
    rows = read(operation, params)
    return {"rows": rows, "row_count": len(rows)}


def get_channel(*, channel_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: get a channel's snippet/statistics (and contentDetails for the uploads playlist)."""
    return run_read(operation=OP_CHANNEL_GET, params=build_channel_params(channel_id), read=read)


def list_videos(*, video_ids: list[str], read: ReadFn) -> dict[str, object]:
    """Tool: list full video resources (snippet/status/statistics) for a batch of video ids."""
    return run_read(operation=OP_VIDEOS_LIST, params=build_video_ids_params(video_ids), read=read)


def list_playlist_items(*, playlist_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: enumerate items in a playlist (prefer the uploads playlist over ``search.list``)."""
    return run_read(
        operation=OP_PLAYLIST_ITEMS_LIST,
        params=build_playlist_items_params(playlist_id),
        read=read,
    )


def analytics_query(
    *,
    ids: str,
    start_date: str,
    end_date: str,
    metrics: list[str],
    dimensions: list[str],
    read: ReadFn,
) -> dict[str, object]:
    """Tool: query organic video performance (views, watch time, etc.) from YouTube Analytics."""
    return run_read(
        operation=OP_ANALYTICS_QUERY,
        params=build_analytics_params(
            ids=ids,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            dimensions=dimensions,
        ),
        read=read,
    )


def ensure_reporting_jobs(*, report_type_ids: list[str], read: ReadFn) -> dict[str, object]:
    """Tool: ensure a Reporting API bulk-report job exists per report type.

    Reports are retained only 30/60 days, so create jobs early and persist downloads — expired
    reports cannot be re-fetched.
    """
    return run_read(
        operation=OP_REPORTING_ENSURE_JOBS,
        params=build_reporting_jobs_params(report_type_ids),
        read=read,
    )
