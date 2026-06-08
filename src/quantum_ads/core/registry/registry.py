"""Connector registry: connectors declare capabilities; meta-tools expose them on demand.

This is the source of truth for "what tools exist", enabling dynamic discovery so a client is
not flooded with hundreds of granular tools at once.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolSpec:
    name: str
    summary: str
    read_only: bool = True


@dataclass
class Capability:
    connector: str
    domain: str
    tools: list[ToolSpec]


class ConnectorRegistry:
    def __init__(self) -> None:
        self._caps: list[Capability] = []
        self._tools: dict[str, ToolSpec] = {}

    def register(self, capability: Capability) -> None:
        self._caps.append(capability)
        for tool in capability.tools:
            self._tools[tool.name] = tool

    def list_capabilities(self) -> list[Capability]:
        return list(self._caps)

    def describe_tool(self, name: str) -> ToolSpec:
        return self._tools[name]

    def all_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())
