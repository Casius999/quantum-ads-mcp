"""Mount the GTM (Tag Manager API v2) read + guarded-write tools onto the FastMCP app.

Read tools degrade gracefully when the ``gtm.api`` backend is unwired; write tools are
guarded by the shared ``WriteExecutor`` (validate_only preview + two-step confirm + audit)
and degrade when the ``gtm.mutate`` backend is unwired.

Consent Mode v2: server-side GTM is where consent signals are wired into tags — this
connector exposes the tag/version surface but does not implement consent logic itself.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from ...core.safety.write_executor import MutateFn, WriteExecutor
from .read import list_tools
from .read.list_tools import ReadFn
from .write.mutate_tools import (
    build_create_tag_ops,
    build_create_version_ops,
    build_publish_version_ops,
    build_update_tag_ops,
)

_READ_BACKEND = "gtm.api"
_MUTATE_BACKEND = "gtm.mutate"

_READ_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "gtm.api not wired"}
}
_MUTATE_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "gtm.mutate not wired"}
}


def register_gtm(app: FastMCP, ctx: ServerContext) -> None:
    # --- read tools (backend: gtm.api) ---
    def _read() -> ReadFn | None:
        backend = ctx.backend(_READ_BACKEND)
        if backend is None:
            return None
        return cast(ReadFn, backend)

    def gtm_list_accounts() -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_accounts(read=read)

    def gtm_list_containers(account_path: str) -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_containers(account_path=account_path, read=read)

    def gtm_list_workspaces(container_path: str) -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_workspaces(container_path=container_path, read=read)

    def gtm_list_tags(workspace_path: str) -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_tags(workspace_path=workspace_path, read=read)

    def gtm_list_triggers(workspace_path: str) -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_triggers(workspace_path=workspace_path, read=read)

    def gtm_list_variables(workspace_path: str) -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_variables(workspace_path=workspace_path, read=read)

    def gtm_list_versions(container_path: str) -> dict[str, object]:
        read = _read()
        if read is None:
            return dict(_READ_NOT_CONFIGURED)
        return list_tools.list_versions(container_path=container_path, read=read)

    read_tools: list[tuple[str, str, Callable[..., Any]]] = [
        ("gtm.list_accounts", "List accessible GTM accounts.", gtm_list_accounts),
        ("gtm.list_containers", "List containers under an account path.", gtm_list_containers),
        ("gtm.list_workspaces", "List workspaces under a container path.", gtm_list_workspaces),
        ("gtm.list_tags", "List tags under a workspace path.", gtm_list_tags),
        ("gtm.list_triggers", "List triggers under a workspace path.", gtm_list_triggers),
        (
            "gtm.list_variables",
            "List user-defined variables under a workspace path.",
            gtm_list_variables,
        ),
        (
            "gtm.list_versions",
            "List container version headers under a container path.",
            gtm_list_versions,
        ),
    ]

    # --- write tools (backend: gtm.mutate, guarded) ---
    holder: dict[str, WriteExecutor] = {}

    def executor() -> WriteExecutor | None:
        backend = ctx.backend(_MUTATE_BACKEND)
        if backend is None:
            return None
        if "ex" not in holder:
            holder["ex"] = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return holder["ex"]

    def gtm_create_tag(
        workspace_path: str,
        tag_name: str,
        tag_type: str,
        parameters: list[dict[str, object]] | None = None,
        confirm: str | None = None,
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_MUTATE_NOT_CONFIGURED)
        return ex.execute(
            op="gtm.create_tag",
            customer_id=workspace_path,
            operations=build_create_tag_ops(workspace_path, tag_name, tag_type, parameters),
            confirm=confirm,
        )

    def gtm_update_tag(
        tag_path: str, fields: dict[str, object], confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_MUTATE_NOT_CONFIGURED)
        return ex.execute(
            op="gtm.update_tag",
            customer_id=tag_path,
            operations=build_update_tag_ops(tag_path, fields),
            confirm=confirm,
        )

    def gtm_create_version(
        workspace_path: str, name: str, confirm: str | None = None
    ) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_MUTATE_NOT_CONFIGURED)
        return ex.execute(
            op="gtm.create_version",
            customer_id=workspace_path,
            operations=build_create_version_ops(workspace_path, name),
            confirm=confirm,
        )

    def gtm_publish_version(version_path: str, confirm: str | None = None) -> dict[str, object]:
        ex = executor()
        if ex is None:
            return dict(_MUTATE_NOT_CONFIGURED)
        return ex.execute(
            op="gtm.publish_version",
            customer_id=version_path,
            operations=build_publish_version_ops(version_path),
            confirm=confirm,
        )

    write_tools: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "gtm.create_tag",
            "Create a tag in a workspace (guarded: validate_only preview + confirm token).",
            gtm_create_tag,
        ),
        (
            "gtm.update_tag",
            "Update an existing tag by path (guarded).",
            gtm_update_tag,
        ),
        (
            "gtm.create_version",
            "Freeze a workspace into a new container version (guarded).",
            gtm_create_version,
        ),
        (
            "gtm.publish_version",
            "Publish a container version (guarded).",
            gtm_publish_version,
        ),
    ]

    for name, description, fn in read_tools + write_tools:
        add_tool(app, name, description, fn)

    ctx.registry.register(
        Capability(
            connector="gtm",
            domain="read",
            tools=[ToolSpec(name=name, summary=description) for name, description, _ in read_tools],
        )
    )
    ctx.registry.register(
        Capability(
            connector="gtm",
            domain="write",
            tools=[
                ToolSpec(name=name, summary=description, read_only=False)
                for name, description, _ in write_tools
            ],
        )
    )
