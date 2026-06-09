"""Mount the guarded Ads Data Hub (ADH) write tool (stored analysis-query create) onto FastMCP.

The mutation runs through the shared :class:`WriteExecutor` (read-only guard -> validate_only
preview -> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"adh.mutate"``; ``customer_id`` carries the ADH account id (the ``account_id`` the created query
hangs off). When the backend is not wired the tool degrades gracefully with a structured
``BACKEND_NOT_CONFIGURED`` error.

``adh.query.create`` creates a stored analysis query only — it does not run it, so no data is read
and no privacy check fires at create time. Any later run (via ``adh.query.start``) is still subject
to ADH's server-side privacy checks (aggregation thresholds + difference checks); this tool does
not bypass that layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from ..query_ops import build_create_query_ops

BACKEND_KEY = "adh.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_adh_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def adh_query_create(
        customer_id: str,
        title: str,
        query_text: str,
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="adh.query.create",
            customer_id=customer_id,
            operations=build_create_query_ops(title, query_text),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "adh.query.create",
            "Create a stored ADH analysis query (guarded: validate_only preview + confirm token). "
            "Creates only; does not run the query.",
            adh_query_create,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="adh",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
