"""Top-level Display & Video 360 connector registrar: mounts the read + write planes together.

``register_dv360`` is the single entrypoint mounting both planes; the sub-registrars are
re-exported for callers that want to mount one plane in isolation (tests).
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_dv360_read
from .write.connector import register_dv360_write

__all__ = ["register_dv360", "register_dv360_read", "register_dv360_write"]


def register_dv360(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all DV360 tools (read advertisers/campaigns/IOs/line-items + guarded LI writes)."""
    register_dv360_read(app, ctx)
    register_dv360_write(app, ctx)
