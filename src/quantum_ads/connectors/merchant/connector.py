"""Top-level Merchant API connector registrar: mounts the read + write planes together."""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_merchant_read
from .write.connector import register_merchant_write


def register_merchant(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all Merchant API tools (read products/statuses/account + guarded product writes)."""
    register_merchant_read(app, ctx)
    register_merchant_write(app, ctx)
