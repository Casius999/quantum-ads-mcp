"""Undo for Google Ads mutations: masks, before-state queries and inverse operations.

Before an update is applied, the current value of every field in its update mask is read with
GAQL; the inverse is an update restoring those values. A create is undone by removing what it
created. A remove cannot be undone through the API (the object is gone), so it is reported as
irreversible. Inverses are stored in the signed audit record of the write and replayed by
``ads.rollback``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_SUFFIX = "_operation"


def resource_of(kind: str) -> str:
    """``campaign_criterion_operation`` -> ``campaign_criterion`` (the GAQL resource name)."""
    return kind[: -len(_SUFFIX)] if kind.endswith(_SUFFIX) else kind


def _paths(value: Mapping[str, Any], prefix: str = "") -> list[str]:
    out: list[str] = []
    for key, item in value.items():
        if key == "resource_name":
            continue
        path = f"{prefix}{key}"
        if isinstance(item, Mapping) and item:
            out.extend(_paths(item, f"{path}."))
        else:
            out.append(path)
    return out


def with_update_masks(operations: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill a missing ``update_mask`` from the fields an update sets (the API requires one)."""
    filled: list[dict[str, Any]] = []
    for operation in operations:
        kind, body = next(iter(operation.items())) if len(operation) == 1 else ("", None)
        if kind and isinstance(body, dict) and "update" in body and "update_mask" not in body:
            body = {**body, "update_mask": ",".join(_paths(body["update"]))}
            filled.append({kind: body})
        else:
            filled.append(operation)
    return filled


def _snake(path: str) -> str:
    return ".".join(re.sub(r"(?<!^)(?=[A-Z])", "_", part).lower() for part in path.split("."))


def mask_paths(body: Mapping[str, Any]) -> list[str]:
    """Update-mask paths in snake_case (GAQL field form), whatever form they were given in."""
    mask = body.get("update_mask") or ""
    if isinstance(mask, Mapping):
        mask = mask.get("paths", [])
    paths = mask if isinstance(mask, list) else str(mask).split(",")
    return [_snake(str(p).strip()) for p in paths if str(p).strip()]


def before_state_query(kind: str, resource_name: str, paths: Sequence[str]) -> str:
    resource = resource_of(kind)
    fields = ", ".join(f"{resource}.{path}" for path in paths)
    return (
        f"SELECT {resource}.resource_name, {fields} FROM {resource} "
        f"WHERE {resource}.resource_name = '{resource_name}'"
    )


def _pick(row: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    node: Any = row
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _nest(paths_values: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, value in paths_values:
        node = out
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def inverse_of_update(
    kind: str, resource_name: str, paths: Sequence[str], row: Mapping[str, Any]
) -> dict[str, Any]:
    """Update restoring ``paths`` to the values in ``row`` (a GAQL row keyed by resource).

    A field absent from the row was unset (GAQL omits defaults), so it is restored by keeping it
    in the mask without a value, which clears it.
    """
    current = row.get(resource_of(kind), {})
    restored = [(p, value) for p in paths for found, value in [_pick(current, p)] if found]
    update = {"resource_name": resource_name, **_nest(restored)}
    return {kind: {"update": update, "update_mask": ",".join(paths)}}


def inverse_of_creates(kind: str, created: Sequence[str]) -> list[dict[str, Any]]:
    return [{kind: {"remove": name}} for name in created]


def created_names(response: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(operation kind, resource name) for every create result in a Mutate response."""
    found: list[tuple[str, str]] = []
    for item in response.get("mutate_operation_responses", []):
        for result_key, result in item.items():
            if result_key.endswith("_result") and isinstance(result, Mapping):
                name = result.get("resource_name")
                if name:
                    found.append((result_key[: -len("_result")] + _SUFFIX, str(name)))
    return found
