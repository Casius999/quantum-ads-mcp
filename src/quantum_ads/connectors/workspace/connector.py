"""Top-level Google Workspace connector registrar: mounts the read + write planes together.

``register_workspace`` is the single entrypoint mounting both planes; the sub-registrars are
re-exported (via the package ``__init__``) for callers that want to mount one plane in isolation.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_workspace_read
from .write.connector import register_workspace_write


def register_workspace(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all Workspace tools (read Drive files / Sheets range + metadata + guarded Sheets
    writes / Slides deck creation) onto the FastMCP app."""
    register_workspace_read(app, ctx)
    register_workspace_write(app, ctx)
