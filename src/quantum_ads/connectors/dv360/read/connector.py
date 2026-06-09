"""Mount the read-only DV360 tools onto the FastMCP app + register their capabilities.

Read backend is keyed ``"dv360.api"`` (a ``ReadFn``). When it is not wired the tools degrade
gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.
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

BACKEND_KEY = "dv360.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_dv360_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def dv360_advertisers_list(partner_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_advertisers(partner_id=partner_id, read=read)

    def dv360_campaigns_list(advertiser_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_campaigns(advertiser_id=advertiser_id, read=read)

    def dv360_insertion_orders_list(advertiser_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_insertion_orders(advertiser_id=advertiser_id, read=read)

    def dv360_line_items_list(advertiser_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_line_items(advertiser_id=advertiser_id, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "dv360.advertisers.list",
            "List advertisers under a DV360 partner.",
            dv360_advertisers_list,
        ),
        (
            "dv360.campaigns.list",
            "List campaigns under a DV360 advertiser.",
            dv360_campaigns_list,
        ),
        (
            "dv360.insertion_orders.list",
            "List insertion orders under a DV360 advertiser.",
            dv360_insertion_orders_list,
        ),
        (
            "dv360.line_items.list",
            "List line items under a DV360 advertiser.",
            dv360_line_items_list,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="dv360",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
