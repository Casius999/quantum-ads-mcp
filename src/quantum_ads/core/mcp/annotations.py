"""MCP tool annotations derived from the connector registry.

Clients use annotations to decide how to treat a tool (auto-run reads, gate destructive writes,
retry idempotent calls). The registry already knows which tools write; this derives the rest:

- ``read_only_hint``: from the registry's read/write flag.
- ``destructive_hint``: a write that changes or removes existing state (update, set status,
  delete, publish, remove, reply...) rather than only adding new state (create, insert, upload,
  submit, add).
- ``idempotent_hint``: reads, and writes that converge to the same state when repeated
  (update, set status, delete) — not creations.
- ``open_world_hint``: everything that calls an external API (all connectors, and anchoring to
  public calendars); core metadata tools are closed-world.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastmcp.server.transforms import Transform
from mcp.types import ToolAnnotations

from ..registry.registry import ConnectorRegistry

_ADDITIVE = ("create", "insert", "upload", "submit", "add", "annotate", "anchor", "generate")
_IDEMPOTENT_WRITES = ("update", "set_status", "delete", "remove", "publish")
_CLOSED_WORLD = {"health", "list_capabilities", "describe_tool", "audit.status"}


def _verb(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _title(name: str) -> str:
    return " ".join(part.replace("_", " ") for part in name.split(".")).capitalize()


def annotations_for(name: str, *, connector: str, read_only: bool) -> ToolAnnotations:
    verb = _verb(name)
    additive = any(verb.startswith(prefix) for prefix in _ADDITIVE)
    idempotent = read_only or any(verb.startswith(prefix) for prefix in _IDEMPOTENT_WRITES)
    return ToolAnnotations(
        title=_title(name),
        read_only_hint=read_only,
        destructive_hint=False if read_only else not additive,
        idempotent_hint=idempotent,
        open_world_hint=not (connector == "core" and name in _CLOSED_WORLD),
    )


class RegistryAnnotations(Transform):
    """Attach registry-derived annotations to every listed or fetched tool."""

    def __init__(self, registry: ConnectorRegistry) -> None:
        self._registry = registry
        self._cache: dict[str, ToolAnnotations] | None = None

    def _table(self) -> dict[str, ToolAnnotations]:
        if self._cache is None:
            self._cache = {
                spec.name: annotations_for(
                    spec.name, connector=cap.connector, read_only=spec.read_only
                )
                for cap in self._registry.list_capabilities()
                for spec in cap.tools
            }
        return self._cache

    def _annotate(self, tool: Any) -> Any:
        annotations = self._table().get(tool.name)
        if annotations is None or tool.annotations is not None:
            return tool
        return tool.model_copy(update={"annotations": annotations})

    async def list_tools(self, tools: Sequence[Any]) -> Sequence[Any]:
        return [self._annotate(tool) for tool in tools]

    async def get_tool(self, name: str, call_next: Any, *, version: Any = None) -> Any:
        tool = await call_next(name, version=version)
        return self._annotate(tool) if tool is not None else None
