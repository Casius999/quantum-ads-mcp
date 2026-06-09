"""Real YouTube SDK glue: Data API v3 + Analytics v2 + Reporting v1 factories.

Live boundary — smoke-gated, not unit-tested.

Isolated at the untyped third-party boundary (``googleapiclient.*`` / ``google.oauth2.*`` are in
the mypy ``ignore_missing_imports`` list, so ``build(...)`` yields ``Any`` and the dynamic
resource objects are threaded as ``Any`` here). Imports are local so importing this module stays
cheap and credential-free; OAuth credentials are derived from the shared Google creds dict.

Backends produced here match the connector contracts:
- ``data_read_factory``      -> ReadFn over Data API v3 (channels / videos / playlistItems).
  ``videos.list`` takes a comma-separated id list (1 unit for many ids — the bulk-statistics
  path; there is no separate batch endpoint). ``search.list`` is deliberately NOT wired
  (quota-scarce ~100u/call).
- ``analytics_read_factory`` -> ReadFn over the Analytics API (reports.query) and the Reporting
  API (jobs.list / jobs.create). Reporting bulk reports are retained 30/60d — persist early.
- ``mutate_factory``         -> MutateFn over Data API v3 (videos.update / playlistItems.insert).
  Metadata only — no media upload (videos.insert forces private until the API audit passes).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scopes per surface: read-only Data + Analytics + Reporting; youtube.force-ssl for writes.
_DATA_READ_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
_ANALYTICS_READ_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]
_WRITE_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# Default Data API v3 video/channel parts (broad enough for metrics that pair with paid video).
_VIDEO_PARTS = "snippet,status,statistics,contentDetails"
_CHANNEL_PARTS = "snippet,statistics,contentDetails"
_PLAYLIST_ITEM_PARTS = "snippet,contentDetails,status"


def _oauth_credentials(creds: dict[str, object], scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials

    quota = creds.get("quota_project_id")
    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes,
        quota_project_id=str(quota) if quota else None,
    )


def _build_service(creds: dict[str, object], name: str, version: str, scopes: list[str]) -> Any:
    from googleapiclient.discovery import build

    return build(
        name, version, credentials=_oauth_credentials(creds, scopes), cache_discovery=False
    )


def _items(response: dict[str, object]) -> list[dict[str, object]]:
    items = response.get("items", [])
    return [dict(item) for item in items]  # type: ignore[arg-type]


def data_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Data API v3 ReadFn (channels / videos / playlistItems)."""
    service: Any = _build_service(creds, "youtube", "v3", _DATA_READ_SCOPES)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "channels.get":
            request = service.channels().list(part=_CHANNEL_PARTS, id=str(params["channel_id"]))
            return _items(request.execute())
        if operation == "videos.list":
            # Comma-separated ids in one call = the bulk-statistics path (1 unit for up to 50 ids).
            ids = ",".join(str(v) for v in cast(Sequence[object], params["video_ids"]))
            return _items(service.videos().list(part=_VIDEO_PARTS, id=ids).execute())
        if operation == "playlistItems.list":
            request = service.playlistItems().list(
                part=_PLAYLIST_ITEM_PARTS, playlistId=str(params["playlist_id"]), maxResults=50
            )
            return _items(request.execute())
        raise ValueError(f"unsupported youtube.data operation: {operation!r}")

    return read


def analytics_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the ReadFn over the Analytics API (reports.query) + Reporting API (report jobs)."""
    analytics: Any = _build_service(creds, "youtubeAnalytics", "v2", _ANALYTICS_READ_SCOPES)
    reporting: Any = _build_service(creds, "youtubereporting", "v1", _ANALYTICS_READ_SCOPES)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "analytics.query":
            metrics = ",".join(str(m) for m in cast(Sequence[object], params["metrics"]))
            dimensions = ",".join(str(d) for d in cast(Sequence[object], params["dimensions"]))
            response = (
                analytics.reports()
                .query(
                    ids=str(params["ids"]),
                    startDate=str(params["start_date"]),
                    endDate=str(params["end_date"]),
                    metrics=metrics,
                    dimensions=dimensions,
                )
                .execute()
            )
            return _analytics_rows(response)
        if operation == "reporting.ensureJobs":
            return _ensure_report_jobs(reporting, cast(Sequence[object], params["report_type_ids"]))
        raise ValueError(f"unsupported youtube.analytics operation: {operation!r}")

    return read


def _analytics_rows(response: dict[str, object]) -> list[dict[str, object]]:
    """Zip the Analytics columnHeaders with each row into name->value dicts."""
    headers = [
        str(h.get("name", ""))
        for h in cast(Sequence[dict[str, object]], response.get("columnHeaders", []))
    ]
    rows = cast(Sequence[Sequence[object]], response.get("rows", []))
    return [dict(zip(headers, row, strict=False)) for row in rows]


def _ensure_report_jobs(
    reporting: Any, report_type_ids: Sequence[object]
) -> list[dict[str, object]]:
    """Create a Reporting API job per report type that lacks one; return the full job set."""
    existing = reporting.jobs().list().execute().get("jobs", [])
    existing_types = {str(job.get("reportTypeId")) for job in existing}
    results: list[dict[str, object]] = [dict(job) for job in existing]
    for raw in report_type_ids:
        report_type_id = str(raw)
        if report_type_id in existing_types:
            continue
        body: dict[str, object] = {"reportTypeId": report_type_id, "name": report_type_id}
        created = reporting.jobs().create(body=body).execute()
        results.append(dict(created))
    return results


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the Data API v3 MutateFn (videos.update / playlistItems.insert). Metadata only."""
    service: Any = _build_service(creds, "youtube", "v3", _WRITE_SCOPES)

    def _update_video(op: dict[str, object]) -> dict[str, object]:
        fields = dict(cast(dict[str, object], op.get("fields", {})))
        body: dict[str, object] = {"id": str(op["video_id"])}
        # Route each field group to its part; snippet carries title/description/tags/categoryId.
        snippet = {
            k: fields[k] for k in ("title", "description", "tags", "categoryId") if k in fields
        }
        status = {k: fields[k] for k in ("privacyStatus",) if k in fields}
        parts: list[str] = []
        if snippet:
            body["snippet"] = snippet
            parts.append("snippet")
        if status:
            body["status"] = status
            parts.append("status")
        request = service.videos().update(part=",".join(parts), body=body)
        return dict(request.execute())

    def _playlist_add_item(op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {
            "snippet": {
                "playlistId": str(op["playlist_id"]),
                "resourceId": {"kind": "youtube#video", "videoId": str(op["video_id"])},
            }
        }
        request = service.playlistItems().insert(part="snippet", body=body)
        return dict(request.execute())

    handlers: dict[str, Callable[[dict[str, object]], dict[str, object]]] = {
        "update_video": _update_video,
        "playlist_add_item": _playlist_add_item,
    }

    def mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            # Data API v3 has no native validate_only; preview the ops without applying.
            return {"validate_only": True, "operations": operations, "channel_id": account_id}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("action")))
            if handler is None:
                raise ValueError(f"unsupported youtube mutate action: {op.get('action')!r}")
            results.append(handler(op))
        return {"validate_only": False, "results": results}

    return mutate
