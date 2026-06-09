"""Mount guarded Search Console write tools (sitemap mutations) onto the FastMCP app.

Mutations run through the shared :class:`WriteExecutor` (read-only guard -> validate_only preview
-> confirm token -> signed audit). The concrete API call is the ``MutateFn`` backend keyed
``"searchconsole.mutate"``; ``customer_id`` carries the property ``site_url``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ....core.safety.write_executor import MutateFn, WriteExecutor
from .sitemap_ops import build_delete_sitemap_ops, build_submit_sitemap_ops

BACKEND_KEY = "searchconsole.mutate"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "MUTATE_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_searchconsole_write(app: FastMCP, ctx: ServerContext) -> None:
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def searchconsole_sitemaps_submit(
        site_url: str, feedpath: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="searchconsole.sitemaps.submit",
            customer_id=site_url,
            operations=build_submit_sitemap_ops(site_url, feedpath),
            confirm=confirm,
        )

    def searchconsole_sitemaps_delete(
        site_url: str, feedpath: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_NOT_CONFIGURED)
        return ex.execute(
            op="searchconsole.sitemaps.delete",
            customer_id=site_url,
            operations=build_delete_sitemap_ops(site_url, feedpath),
            confirm=confirm,
        )

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "searchconsole.sitemaps.submit",
            "Submit a sitemap feed path for a property (guarded: preview + confirm token).",
            searchconsole_sitemaps_submit,
        ),
        (
            "searchconsole.sitemaps.delete",
            "Delete a sitemap feed path for a property (guarded).",
            searchconsole_sitemaps_delete,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="searchconsole",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in tools
            ],
        )
    )
