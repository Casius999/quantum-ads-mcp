"""Top-level Google Business Profile connector registrar: mounts the read + write planes together.

``register_gbp`` is the single entrypoint mounting both planes; the sub-registrars are re-exported
(via the package ``__init__``) for callers that want to mount one plane in isolation (tests).
"""

from __future__ import annotations

from fastmcp import FastMCP

from ...core.context import ServerContext
from .read.connector import register_gbp_read
from .write.connector import register_gbp_write


def register_gbp(app: FastMCP, ctx: ServerContext) -> None:
    """Mount all Google Business Profile tools (read accounts/locations/location/performance/reviews
    + guarded review-reply and location-update writes) onto the FastMCP app."""
    register_gbp_read(app, ctx)
    register_gbp_write(app, ctx)
