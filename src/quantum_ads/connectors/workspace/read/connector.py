"""Mount the read-only Google Workspace tools onto the FastMCP app + register capabilities.

Read backend is keyed ``"workspace.api"`` (a ``ReadFn``). When it is not wired the tools degrade
gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.

Workspace covers the **agency ops** surface: Drive file discovery (shared files), Sheets range
reads + spreadsheet metadata (reporting exports), pairing the platform connectors with the
deliverable side.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import list_tools as tools_mod

BACKEND_KEY = "workspace.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_workspace_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def workspace_drive_list_files(query: str = "") -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.list_files(query=query, read=read)

    def workspace_sheets_read_range(spreadsheet_id: str, range_a1: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.read_range(spreadsheet_id=spreadsheet_id, range_a1=range_a1, read=read)

    def workspace_sheets_get_metadata(spreadsheet_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.get_metadata(spreadsheet_id=spreadsheet_id, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "workspace.drive.list_files",
            "List Drive files the authenticated user can access (optional files.list query).",
            workspace_drive_list_files,
        ),
        (
            "workspace.sheets.read_range",
            "Read a cell range (A1 notation) from a spreadsheet.",
            workspace_sheets_read_range,
        ),
        (
            "workspace.sheets.get_metadata",
            "Fetch spreadsheet metadata (title, sheet tabs, grid sizes).",
            workspace_sheets_get_metadata,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="workspace",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
