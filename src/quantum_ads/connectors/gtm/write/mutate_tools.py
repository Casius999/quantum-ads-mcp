"""Pure operation builders for GTM mutations (entity-agnostic dict operations).

Each op dict names the GTM ``action`` (create_tag / update_tag / create_version /
publish_version) plus the resource path or parent + body fields. The ``MutateFn`` backend
dispatches on ``action``. Builders are pure and unit-tested directly.
"""

from __future__ import annotations


def build_create_tag_ops(
    workspace_path: str,
    tag_name: str,
    tag_type: str,
    parameters: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Build a create-tag op under a workspace (``parameters`` are GTM tag parameter dicts)."""
    op: dict[str, object] = {
        "action": "create_tag",
        "workspace_path": workspace_path,
        "tag_name": tag_name,
        "tag_type": tag_type,
        "parameter": list(parameters) if parameters is not None else [],
    }
    return [op]


def build_update_tag_ops(tag_path: str, fields: dict[str, object]) -> list[dict[str, object]]:
    """Build an update-tag op for a full tag path (``.../tags/{id}``) with replacement fields."""
    op: dict[str, object] = {
        "action": "update_tag",
        "path": tag_path,
        "fields": dict(fields),
    }
    return [op]


def build_create_version_ops(workspace_path: str, name: str) -> list[dict[str, object]]:
    """Build a create-version op: freeze a workspace into a new container version."""
    op: dict[str, object] = {
        "action": "create_version",
        "workspace_path": workspace_path,
        "name": name,
    }
    return [op]


def build_publish_version_ops(version_path: str) -> list[dict[str, object]]:
    """Build a publish-version op for a full version path (``.../versions/{id}``)."""
    op: dict[str, object] = {
        "action": "publish_version",
        "path": version_path,
    }
    return [op]
