"""YouTube connector: Data API v3 + Analytics/Reporting (read) + guarded video/playlist write.

Organic video surface that pairs with Google Ads video campaigns: channel/video metadata and
batch stats from the Data API, organic performance from the Analytics API, and bulk export jobs
from the Reporting API. Writes (video metadata update, playlist add) are guarded by the shared
``WriteExecutor`` (validate_only preview + two-step confirm + signed audit).

``register_youtube`` is the single entrypoint mounting both planes onto the FastMCP app.
"""

from .connector import register_youtube

__all__ = ["register_youtube"]
