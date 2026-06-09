"""Google Trends connector entry point: mount the read-only tool plane.

Trends is **read-only** — there is no write plane (it is a research / demand-signal surface, not a
mutable resource). :func:`register_trends` therefore delegates straight to the read registrar,
keeping the same public-registrar shape as the other connectors while declaring no writes.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_trends_read


def register_trends(app: FastMCP, ctx: ServerContext) -> None:
    """Mount the Google Trends read-only tools (no write plane)."""
    register_trends_read(app, ctx)
