"""Mount the read-only Search Console tools onto the FastMCP app + register capabilities.

Read backend is keyed ``"searchconsole.api"`` (a ``ReadFn``). When it is not wired the tools
degrade gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.

Search Console covers the **organic / SEO** surface (queries, pages, countries, devices,
clicks/impressions/ctr/position), pairing the paid Google Ads connectors with the earned side.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import search_analytics_tools as tools_mod

BACKEND_KEY = "searchconsole.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_searchconsole_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def searchconsole_search_analytics(
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: list[str],
        row_limit: int = tools_mod.DEFAULT_ROW_LIMIT,
    ) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.search_analytics(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions,
            row_limit=row_limit,
            read=read,
        )

    def searchconsole_sites_list() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.list_sites(read=read)

    def searchconsole_sitemaps_list(site_url: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.list_sitemaps(site_url=site_url, read=read)

    def searchconsole_url_inspect(site_url: str, inspection_url: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return tools_mod.inspect_url(site_url=site_url, inspection_url=inspection_url, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "searchconsole.search_analytics",
            "Query Search Analytics (organic clicks/impressions/ctr/position) for a property.",
            searchconsole_search_analytics,
        ),
        (
            "searchconsole.sites.list",
            "List Search Console properties the authenticated user can access.",
            searchconsole_sites_list,
        ),
        (
            "searchconsole.sitemaps.list",
            "List sitemaps submitted for a property.",
            searchconsole_sitemaps_list,
        ),
        (
            "searchconsole.url_inspect",
            "Inspect a URL's index status for a property (URL Inspection API).",
            searchconsole_url_inspect,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="searchconsole",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
