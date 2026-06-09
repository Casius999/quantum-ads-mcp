"""Top-level Search Console connector registrar: mounts the read + write planes together.

``register_searchconsole`` is the single entrypoint mounting both planes; the sub-registrars are
re-exported (via the package ``__init__``) for callers that want to mount one plane in isolation.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_searchconsole_read
from .write.connector import register_searchconsole_write


def register_searchconsole(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all Search Console tools (read search-analytics/sites/sitemaps/url-inspect +
    guarded sitemap writes) onto the FastMCP app."""
    register_searchconsole_read(app, ctx)
    register_searchconsole_write(app, ctx)
