"""Pure operation builders for YouTube mutations (entity-agnostic dict operations).

Each op dict names the ``action`` (update_video / playlist_add_item) plus the target ids and
body fields. The ``MutateFn`` backend dispatches on ``action``. Builders are pure (unit-tested
directly) and never touch the SDK.

``video.update`` warning: this performs a metadata-only update (title/description/tags/category
via ``videos.update`` with the relevant ``part``). It does NOT upload media. New uploads via
``videos.insert`` are forced to ``private`` until the GCP project passes the YouTube API
compliance audit, so uploading is deliberately out of scope for this connector.
"""

from __future__ import annotations


def build_update_video_ops(video_id: str, fields: dict[str, object]) -> list[dict[str, object]]:
    """Build a metadata update op for a video id (``fields`` replace snippet/status members)."""
    op: dict[str, object] = {
        "action": "update_video",
        "video_id": video_id,
        "fields": dict(fields),
    }
    return [op]


def build_playlist_add_item_ops(playlist_id: str, video_id: str) -> list[dict[str, object]]:
    """Build an op inserting a video into a playlist (``playlistItems.insert``)."""
    op: dict[str, object] = {
        "action": "playlist_add_item",
        "playlist_id": playlist_id,
        "video_id": video_id,
    }
    return [op]
