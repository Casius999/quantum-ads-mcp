"""Mount guarded DV360 write tools (line-item mutations) onto the FastMCP app.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"dv360.mutate"``; ``customer_id`` carries the DV360 advertiser id (the parent every line-item
mutation hangs off).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .mutate_tools import build_set_line_item_status_ops, build_update_line_item_ops

BACKEND_KEY = "dv360.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_dv360_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def dv360_line_item_update(
        advertiser_id: str,
        line_item_id: str,
        fields: dict[str, object],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="dv360.line_item.update",
            customer_id=advertiser_id,
            operations=build_update_line_item_ops(advertiser_id, line_item_id, fields),
            confirm=confirm,
        )

    def dv360_line_item_set_status(
        advertiser_id: str,
        line_item_id: str,
        entity_status: str,
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="dv360.line_item.set_status",
            customer_id=advertiser_id,
            operations=build_set_line_item_status_ops(advertiser_id, line_item_id, entity_status),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "dv360.line_item.update",
            "Update a line item by id with a partial field set (guarded: preview + confirm token).",
            dv360_line_item_update,
        ),
        (
            "dv360.line_item.set_status",
            "Set a line item's entityStatus (activate/pause/archive) (guarded).",
            dv360_line_item_set_status,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="dv360",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
