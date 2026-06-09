"""Search Console connector: organic / SEO surface, pairing the paid Google Ads connectors.

Public entry point: :func:`register_searchconsole` mounts both the read and write tool planes.
The read plane wraps the Search Console / webmasters v3 API (searchAnalytics, sites, sitemaps)
plus the Search Console URL Inspection API; the guarded write plane covers sitemap submit/delete.
"""

from __future__ import annotations

from .connector import register_searchconsole
from .read.connector import register_searchconsole_read
from .write.connector import register_searchconsole_write

__all__ = [
    "register_searchconsole",
    "register_searchconsole_read",
    "register_searchconsole_write",
]
