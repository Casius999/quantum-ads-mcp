"""Mount the read-only Merchant API tools onto the FastMCP app + register capabilities.

Read backend is keyed ``"merchant.api"`` (a ``ReadFn``). When it is not wired the tools degrade
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
from . import product_tools

BACKEND_KEY = "merchant.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_merchant_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def merchant_products_list(merchant_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return product_tools.list_products(merchant_id=merchant_id, read=read)

    def merchant_product_get(product_name: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return product_tools.get_product(product_name=product_name, read=read)

    def merchant_product_statuses_list(merchant_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return product_tools.list_product_statuses(merchant_id=merchant_id, read=read)

    def merchant_accounts_get(merchant_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return product_tools.get_account(merchant_id=merchant_id, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "merchant.products.list",
            "List products under a Merchant Center account.",
            merchant_products_list,
        ),
        (
            "merchant.product.get",
            "Get a single product by its resource name.",
            merchant_product_get,
        ),
        (
            "merchant.product_statuses.list",
            "List item-level product statuses/issues for an account.",
            merchant_product_statuses_list,
        ),
        (
            "merchant.accounts.get",
            "Get a Merchant Center account.",
            merchant_accounts_get,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="merchant",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
