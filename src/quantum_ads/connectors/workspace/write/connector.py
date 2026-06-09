"""Mount guarded Google Workspace write tools (Sheets writes + Slides deck create) onto FastMCP.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"workspace.mutate"``; ``customer_id`` carries the target spreadsheet id for range writes, or
the literal ``"drive"`` for create operations that mint a brand-new file (no id exists yet).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .sheets_ops import build_create_deck_ops, build_create_spreadsheet_ops, build_write_range_ops

BACKEND_KEY = "workspace.mutate"

# Account scope for create ops that do not target an existing spreadsheet (Drive-level mint).
_DRIVE_ACCOUNT = "drive"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_workspace_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def workspace_sheets_write_range(
        spreadsheet_id: str,
        range_a1: str,
        values: list[object],
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="workspace.sheets.write_range",
            customer_id=spreadsheet_id,
            operations=build_write_range_ops(spreadsheet_id, range_a1, values),
            confirm=confirm,
        )

    def workspace_sheets_create(title: str, confirm: str | None = None) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="workspace.sheets.create",
            customer_id=_DRIVE_ACCOUNT,
            operations=build_create_spreadsheet_ops(title),
            confirm=confirm,
        )

    def workspace_slides_create_deck(title: str, confirm: str | None = None) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="workspace.slides.create_deck",
            customer_id=_DRIVE_ACCOUNT,
            operations=build_create_deck_ops(title),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "workspace.sheets.write_range",
            "Write values into an A1 range of a spreadsheet (guarded: preview + confirm token).",
            workspace_sheets_write_range,
        ),
        (
            "workspace.sheets.create",
            "Create a new spreadsheet with a title (guarded).",
            workspace_sheets_create,
        ),
        (
            "workspace.slides.create_deck",
            "Create a new Slides deck with a title (guarded).",
            workspace_slides_create_deck,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="workspace",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
