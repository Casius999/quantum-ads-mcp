"""Top-level Campaign Manager 360 connector registrar: mounts the read + write planes together.

``register_cm360`` is the single entrypoint mounting both planes; the sub-registrars are
re-exported for callers that want to mount one plane in isolation (tests).
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_cm360_read
from .write.connector import register_cm360_write

__all__ = ["register_cm360", "register_cm360_read", "register_cm360_write"]


def register_cm360(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all CM360 tools (read profiles/campaigns/placements/reports/Floodlight + guarded writes)."""
    register_cm360_read(app, ctx)
    register_cm360_write(app, ctx)
