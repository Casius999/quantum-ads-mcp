"""Top-level Data Manager API connector registrar: mounts the read + write planes together."""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_datamanager_read
from .write.connector import register_datamanager_write


def register_datamanager(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all Data Manager tools (status/destinations read + guarded first-party uploads)."""
    register_datamanager_read(app, ctx)
    register_datamanager_write(app, ctx)
