"""Mount guarded GA4 Admin write tools (mutations) onto the FastMCP app.

The mutate backend is read lazily via ``ctx.backend("ga4.admin.mutate")`` (a ``MutateFn``);
when absent the tools return a structured BACKEND_NOT_CONFIGURED error. Each write runs through
``WriteExecutor`` (read-only guard -> validate_only preview -> confirm token -> signed audit),
with ``customer_id`` bound to the GA4 ``property_id``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from typing import cast as _cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .mutate_tools import build_create_audience_ops, build_create_key_event_ops

_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "ga4.admin.mutate not wired"}
}


def register_ga4_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend("ga4.admin.mutate")
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(_cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def ga4_admin_create_key_event(
        property_id: str, event_name: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_BACKEND_NOT_CONFIGURED)
        return ex.execute(
            op="ga4.admin.create_key_event",
            customer_id=property_id,
            operations=build_create_key_event_ops(property_id, event_name),
            confirm=confirm,
        )

    def ga4_admin_create_audience(
        property_id: str,
        display_name: str,
        filter_clauses: list[dict[str, object]],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_BACKEND_NOT_CONFIGURED)
        return ex.execute(
            op="ga4.admin.create_audience",
            customer_id=property_id,
            operations=build_create_audience_ops(property_id, display_name, filter_clauses),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "ga4.admin.create_key_event",
            "Create a key event (conversion) on a property (guarded: preview + confirm token).",
            ga4_admin_create_key_event,
        ),
        (
            "ga4.admin.create_audience",
            "Create an audience with filter clauses on a property (guarded).",
            ga4_admin_create_audience,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="ga4",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
