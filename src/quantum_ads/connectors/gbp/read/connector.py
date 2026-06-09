"""Mount the read-only Google Business Profile tools onto the FastMCP app + register capabilities.

Two read backends are keyed independently so reviews can degrade on their own:
  - ``"gbp.api"``      (a ``ReadFn``) — accounts.list / locations.list / location.get / performance
  - ``"gbp.reviews"``  (a ``ReadFn``) — reviews.list on the legacy v4 ``mybusiness`` host

Reviews/Media/LocalPosts still live on the legacy v4 host and require separate Google allowlist
approval (weeks-to-months); the v1 family covers Account Management / Business Information /
Business Profile Performance. When either backend is not wired its tools degrade gracefully,
returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising — so ``reviews.list``
returns ``BACKEND_NOT_CONFIGURED`` until the ``gbp.reviews`` allowlist backend is configured.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import list_tools

# v1 API family (Account Management / Business Information / Business Profile Performance).
BACKEND_KEY = "gbp.api"
# Legacy v4 ``mybusiness`` host for reviews — separately allowlist-gated by Google.
REVIEWS_BACKEND_KEY = "gbp.reviews"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}
_REVIEWS_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{REVIEWS_BACKEND_KEY} not wired"}
}


def register_gbp_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def reviews_backend() -> ReadFn | None:
        backend = ctx.backend(REVIEWS_BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def gbp_accounts_list() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_accounts(read=read)

    def gbp_locations_list(account_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_locations(account_id=account_id, read=read)

    def gbp_location_get(location_name: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.get_location(location_name=location_name, read=read)

    def gbp_performance_fetch(
        location_name: str, start_date: str, end_date: str
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.fetch_performance(
            location_name=location_name, start_date=start_date, end_date=end_date, read=read
        )

    def gbp_reviews_list(location_name: str) -> dict[str, object]:
        # Reviews are allowlist-gated and live on the dedicated gbp.reviews backend; when that
        # backend is absent this degrades to BACKEND_NOT_CONFIGURED independently of gbp.api.
        read = reviews_backend()
        if read is None:
            return dict(_REVIEWS_NOT_CONFIGURED)
        return list_tools.list_reviews(location_name=location_name, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "gbp.accounts.list",
            "List Google Business Profile accounts the authenticated user can access.",
            gbp_accounts_list,
        ),
        (
            "gbp.locations.list",
            "List locations under a Google Business Profile account.",
            gbp_locations_list,
        ),
        (
            "gbp.location.get",
            "Fetch a single GBP location's details by resource name.",
            gbp_location_get,
        ),
        (
            "gbp.performance.fetch",
            "Fetch daily performance metrics (calls/directions/clicks/impressions) for a location.",
            gbp_performance_fetch,
        ),
        (
            "gbp.reviews.list",
            "List reviews for a location (legacy v4 host — requires Google allowlist approval).",
            gbp_reviews_list,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="gbp",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
