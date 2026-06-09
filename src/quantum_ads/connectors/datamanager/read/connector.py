"""Mount the read-only Data Manager tools onto the FastMCP app + register capabilities.

Two tools:
  - ``datamanager.status``           -> dependency-free plane identity + operator contract.
  - ``datamanager.destinations.list`` -> lists destinations via the optional ``datamanager.read``
    ReadFn backend; degrades gracefully (structured BACKEND_NOT_CONFIGURED error) when unwired.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from . import status_tools

BACKEND_KEY = "datamanager.read"


def register_datamanager_read(app: FastMCP, ctx: ServerContext) -> None:
    def datamanager_status() -> dict[str, object]:
        return status_tools.status()

    def datamanager_destinations_list(account_id: str) -> dict[str, object]:
        return status_tools.list_destinations(
            account_id=account_id, backend=ctx.backend(BACKEND_KEY)
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "datamanager.status",
            "Report the Data Manager upload plane identity + operator contract (hashing/consent).",
            datamanager_status,
        ),
        (
            "datamanager.destinations.list",
            "List Data Manager destinations under an account (optional read backend).",
            datamanager_destinations_list,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="datamanager",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
