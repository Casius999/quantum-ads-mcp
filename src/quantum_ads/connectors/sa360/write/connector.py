"""Mount the guarded Search Ads 360 write tool (conversion upload) onto the FastMCP app.

The mutation runs through the shared :class:`WriteExecutor` (read-only guard -> validate_only
preview -> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"sa360.mutate"``; ``customer_id`` carries the SA360 account id (the ``account_id`` every
conversion ingest hangs off). When the backend is not wired the tool degrades gracefully with a
structured ``BACKEND_NOT_CONFIGURED`` error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from ..conversion_ops import build_upload_conversions_ops

BACKEND_KEY = "sa360.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_sa360_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def sa360_conversion_upload(
        customer_id: str,
        conversions: list[dict[str, object]],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="sa360.conversion.upload",
            customer_id=customer_id,
            operations=build_upload_conversions_ops(conversions),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "sa360.conversion.upload",
            "Upload SA360 conversions (guarded: preview + confirm token).",
            sa360_conversion_upload,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="sa360",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
