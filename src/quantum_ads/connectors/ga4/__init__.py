"""GA4 (Google Analytics 4) connector: Data API v1 + Admin API v1 (read in batch 1; write guarded).

``register_ga4`` is the single entrypoint mounting both the read and write planes; the
sub-registrars are re-exported for callers that want to mount one plane in isolation (tests).
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_ga4_read
from .write.connector import register_ga4_write

__all__ = ["register_ga4", "register_ga4_read", "register_ga4_write"]


def register_ga4(app: FastMCP, ctx: ServerContext) -> None:
    """Mount the full GA4 connector (read + guarded write) onto the FastMCP app."""
    register_ga4_read(app, ctx)
    register_ga4_write(app, ctx)
