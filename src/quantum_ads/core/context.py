"""Shared server context passed to every connector registrar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .query.runner import StreamFn
from .registry.registry import ConnectorRegistry
from .safety.mode import SafetyMode
from .versioning.version_manager import VersionManager

# Given a credentials dict + API version, returns a bound stream function (customer_id, query) -> rows.
StreamFactory = Callable[[dict[str, object], str], StreamFn]


@dataclass
class ServerContext:
    creds: dict[str, object]
    version: str
    stream_factory: StreamFactory
    version_manager: VersionManager
    safety: SafetyMode
    registry: ConnectorRegistry

    def stream(self) -> StreamFn:
        """Build the bound stream function for the configured tenant + version."""
        return self.stream_factory(self.creds, self.version)
