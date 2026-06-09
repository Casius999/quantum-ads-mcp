"""GTM read tools: pure param builders + a thin backend-invoking runner.

Each GTM resource is listed by naming the resource in ``operation`` and carrying the
parent path in ``params`` (the ``ReadFn`` contract). Builders are pure and unit-tested
directly; the runner wraps the injected backend and shapes ``{"rows", "row_count"}``.
"""

from __future__ import annotations

from collections.abc import Callable

# (operation, params) -> rows.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]


def build_parent_params(parent: str) -> dict[str, object]:
    """Pure: wrap a parent path (account/container/workspace) as backend params."""
    params: dict[str, object] = {"parent": parent}
    return params


def run_read(*, operation: str, params: dict[str, object], read: ReadFn) -> dict[str, object]:
    """Invoke the GTM read backend for ``operation`` and wrap rows or a structured error."""
    rows = read(operation, params)
    return {"rows": rows, "row_count": len(rows)}


def list_accounts(*, read: ReadFn) -> dict[str, object]:
    """Tool: list all GTM accounts the credentials can access."""
    return run_read(operation="list_accounts", params=build_parent_params(""), read=read)


def list_containers(*, account_path: str, read: ReadFn) -> dict[str, object]:
    """Tool: list containers under an account path (``accounts/{id}``)."""
    return run_read(
        operation="list_containers", params=build_parent_params(account_path), read=read
    )


def list_workspaces(*, container_path: str, read: ReadFn) -> dict[str, object]:
    """Tool: list workspaces under a container path (``accounts/{id}/containers/{id}``)."""
    return run_read(
        operation="list_workspaces", params=build_parent_params(container_path), read=read
    )


def list_tags(*, workspace_path: str, read: ReadFn) -> dict[str, object]:
    """Tool: list tags under a workspace path."""
    return run_read(operation="list_tags", params=build_parent_params(workspace_path), read=read)


def list_triggers(*, workspace_path: str, read: ReadFn) -> dict[str, object]:
    """Tool: list triggers under a workspace path."""
    return run_read(
        operation="list_triggers", params=build_parent_params(workspace_path), read=read
    )


def list_variables(*, workspace_path: str, read: ReadFn) -> dict[str, object]:
    """Tool: list user-defined variables under a workspace path."""
    return run_read(
        operation="list_variables", params=build_parent_params(workspace_path), read=read
    )


def list_versions(*, container_path: str, read: ReadFn) -> dict[str, object]:
    """Tool: list container version headers under a container path."""
    return run_read(
        operation="list_versions", params=build_parent_params(container_path), read=read
    )
