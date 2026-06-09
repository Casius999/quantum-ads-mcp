"""Search Ads 360 connector: cross-engine search-management reporting + conversion uploads.

Public entry point: :func:`register_sa360` mounts both the read and write tool planes. The read
plane wraps the new Search Ads 360 Reporting API v0 — a GAQL-like query language exposed via
``searchAds360:search`` (arbitrary queries + opinionated campaign / ad-group report shortcuts)
plus ``customers:listAccessible``. The guarded write plane covers conversion uploads
(``conversions:ingest``).

``register_sa360`` is the single entrypoint; the sub-registrars are re-exported for callers that
want to mount one plane in isolation (tests).
"""

from __future__ import annotations

from .connector import register_sa360
from .read.connector import register_sa360_read
from .write.connector import register_sa360_write

__all__ = ["register_sa360", "register_sa360_read", "register_sa360_write"]
