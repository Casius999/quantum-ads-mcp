"""Looker connector registrar: mounts the read + guarded write planes in one call.

Read backend is keyed ``"looker.api"`` (a ``ReadFn``); write backend ``"looker.mutate"`` (a
``MutateFn`` whose ``account_id`` is the constant ``"looker"``). Both degrade gracefully: when a
backend is not wired the tools return a structured ``*_NOT_CONFIGURED`` error rather than raising.

Read surface: list dashboards, list looks, run a saved look (look_id + result_format), run an
inline model/view query (model + view + fields + filters). Dashboard creation is a guarded mutation
(validate_only preview -> confirm token -> signed audit).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from ...core.safety.write_executor import MutateFn, WriteExecutor
from . import read_tools
from .read_tools import DEFAULT_RESULT_FORMAT
from .types import ReadFn
from .write_ops import build_create_dashboard_ops

READ_BACKEND_KEY = "looker.api"
WRITE_BACKEND_KEY = "looker.mutate"

# The Looker mutate plane is a single-instance surface; the MutateFn's account_id is constant.
LOOKER_ACCOUNT_ID = "looker"

_READ_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{READ_BACKEND_KEY} not wired"}
}
_WRITE_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{WRITE_BACKEND_KEY} not wired"}
}


def register_looker(app: FastMCP, ctx: ServerContext) -> None:
    """Mount the full Looker connector (read + guarded write) onto the FastMCP app."""
    _register_read(app, ctx)
    _register_write(app, ctx)


def _register_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(READ_BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def looker_dashboards_list() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.list_dashboards(read=read)

    def looker_looks_list() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.list_looks(read=read)

    def looker_look_run(
        look_id: str, result_format: str = DEFAULT_RESULT_FORMAT
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.run_look(look_id=look_id, read=read, result_format=result_format)

    def looker_query_run(
        model: str, view: str, fields: list[str], filters: dict[str, object]
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return read_tools.run_query(
            model=model, view=view, fields=fields, filters=filters, read=read
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "looker.dashboards.list",
            "List dashboards on the Looker instance.",
            looker_dashboards_list,
        ),
        (
            "looker.looks.list",
            "List saved looks on the Looker instance.",
            looker_looks_list,
        ),
        (
            "looker.look.run",
            "Run a saved look by id (result_format defaults to json).",
            looker_look_run,
        ),
        (
            "looker.query.run",
            "Run an inline model/view query with fields + filters.",
            looker_query_run,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="looker",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )


def _register_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(WRITE_BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def looker_dashboard_create(
        title: str, model: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_WRITE_NOT_CONFIGURED)
        return ex.execute(
            op="looker.dashboard.create",
            customer_id=LOOKER_ACCOUNT_ID,
            operations=build_create_dashboard_ops(title, model),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "looker.dashboard.create",
            "Create a dashboard under a model (guarded: validate_only preview + confirm token).",
            looker_dashboard_create,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="looker",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
