"""Mount guarded CM360 write tools (placement patch + report insert) onto the FastMCP app.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"cm360.mutate"``; ``customer_id`` carries the CM360 user profile id (every placement patch and
report insert is scoped to that profile).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .mutate_tools import build_insert_report_ops, build_update_placement_ops

BACKEND_KEY = "cm360.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_cm360_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def cm360_placement_update(
        profile_id: str,
        placement_id: str,
        fields: dict[str, object],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="cm360.placement.update",
            customer_id=profile_id,
            operations=build_update_placement_ops(profile_id, placement_id, fields),
            confirm=confirm,
        )

    def cm360_report_insert(
        profile_id: str,
        report: dict[str, object],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="cm360.report.insert",
            customer_id=profile_id,
            operations=build_insert_report_ops(profile_id, report),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "cm360.placement.update",
            "Update a placement by id with a partial field set (guarded: preview + confirm token).",
            cm360_placement_update,
        ),
        (
            "cm360.report.insert",
            "Create a report definition from a report body (guarded: preview + confirm token).",
            cm360_report_insert,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="cm360",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
