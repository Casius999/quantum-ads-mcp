"""Mount guarded Merchant API write tools (product mutations) onto the FastMCP app.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"merchant.mutate"``; ``customer_id`` carries the Merchant Center account id.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .product_ops import (
    build_delete_product_ops,
    build_insert_product_ops,
    build_update_product_ops,
)

BACKEND_KEY = "merchant.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_merchant_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def merchant_product_insert(
        merchant_id: str, product_input: dict[str, object], confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="merchant.product.insert",
            customer_id=merchant_id,
            operations=build_insert_product_ops(product_input),
            confirm=confirm,
        )

    def merchant_product_update(
        product_name: str, fields: dict[str, object], confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        # Merchant id is the account segment of the product resource name (accounts/{id}/...).
        merchant_id = _merchant_id_from_product_name(product_name)
        return ex.execute(
            op="merchant.product.update",
            customer_id=merchant_id,
            operations=build_update_product_ops(product_name, fields),
            confirm=confirm,
        )

    def merchant_product_delete(product_name: str, confirm: str | None = None) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        merchant_id = _merchant_id_from_product_name(product_name)
        return ex.execute(
            op="merchant.product.delete",
            customer_id=merchant_id,
            operations=build_delete_product_ops(product_name),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "merchant.product.insert",
            "Insert a product via productInput (guarded: validate_only preview + confirm token).",
            merchant_product_insert,
        ),
        (
            "merchant.product.update",
            "Update a product by resource name with a partial field set (guarded).",
            merchant_product_update,
        ),
        (
            "merchant.product.delete",
            "Delete a product by resource name (guarded).",
            merchant_product_delete,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="merchant",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )


def _merchant_id_from_product_name(product_name: str) -> str:
    """Extract the account id from ``accounts/{account}/products/{product}``.

    Falls back to the raw value when the resource name is not in the expected shape, so the audit
    record and validate_only preview still carry a meaningful customer id.
    """
    parts = product_name.split("/")
    if len(parts) >= 2 and parts[0] == "accounts":
        return parts[1]
    return product_name
