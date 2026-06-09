"""Top-level Ads Data Hub (ADH) connector registrar: mounts the read + write planes together.

``register_adh`` is the single entrypoint mounting both planes; the sub-registrars are re-exported
(via the package ``__init__``) for callers that want to mount one plane in isolation.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_adh_read
from .write.connector import register_adh_write


def register_adh(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all ADH tools (read customers/queries/start/jobs + guarded analysis-query create)."""
    register_adh_read(app, ctx)
    register_adh_write(app, ctx)
