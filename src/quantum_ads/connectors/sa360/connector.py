"""Top-level Search Ads 360 connector registrar: mounts the read + write planes together.

``register_sa360`` is the single entrypoint mounting both planes; the sub-registrars are
re-exported (via the package ``__init__``) for callers that want to mount one plane in isolation.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_sa360_read
from .write.connector import register_sa360_write


def register_sa360(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all SA360 tools (read search/reports/listAccessible + guarded conversion upload)."""
    register_sa360_read(app, ctx)
    register_sa360_write(app, ctx)
