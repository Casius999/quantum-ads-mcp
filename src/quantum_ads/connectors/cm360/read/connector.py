"""Mount the read-only CM360 tools onto the FastMCP app + register their capabilities.

Read backend is keyed ``"cm360.api"`` (a ``ReadFn``). When it is not wired the tools degrade
gracefully, returning a structured ``BACKEND_NOT_CONFIGURED`` error rather than raising.

Every dfareporting call is scoped to a user profile, so ``profile_id`` leads each tool signature
(except ``cm360.user_profiles.list``, which enumerates the profiles themselves).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ....core.context import ServerContext
from ....core.mcp.register import add_tool
from ....core.registry.registry import Capability, ToolSpec
from ..types import ReadFn
from . import list_tools

BACKEND_KEY = "cm360.api"

_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": f"{BACKEND_KEY} not wired"}
}


def register_cm360_read(app: FastMCP, ctx: ServerContext) -> None:
    def read_backend() -> ReadFn | None:
        backend = ctx.backend(BACKEND_KEY)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def cm360_user_profiles_list() -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_user_profiles(read=read)

    def cm360_campaigns_list(profile_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_campaigns(profile_id=profile_id, read=read)

    def cm360_placements_list(profile_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_placements(profile_id=profile_id, read=read)

    def cm360_reports_list(profile_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_reports(profile_id=profile_id, read=read)

    def cm360_report_run(profile_id: str, report_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.run_report(profile_id=profile_id, report_id=report_id, read=read)

    def cm360_floodlight_activities_list(profile_id: str) -> dict[str, object]:
        read = read_backend()
        if read is None:
            return dict(_NOT_CONFIGURED)
        return list_tools.list_floodlight_activities(profile_id=profile_id, read=read)

    tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "cm360.user_profiles.list",
            "List the CM360 user profiles the authenticated user can access.",
            cm360_user_profiles_list,
        ),
        (
            "cm360.campaigns.list",
            "List campaigns visible to a CM360 user profile.",
            cm360_campaigns_list,
        ),
        (
            "cm360.placements.list",
            "List placements (ad-serving slots) visible to a CM360 user profile.",
            cm360_placements_list,
        ),
        (
            "cm360.reports.list",
            "List report definitions visible to a CM360 user profile.",
            cm360_reports_list,
        ),
        (
            "cm360.report.run",
            "Run a report definition by id under a CM360 user profile (returns the report file).",
            cm360_report_run,
        ),
        (
            "cm360.floodlight_activities.list",
            "List Floodlight activities (conversion tags) visible to a CM360 user profile.",
            cm360_floodlight_activities_list,
        ),
    ]
    for name, description, fn in tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="cm360",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in tools],
        )
    )
