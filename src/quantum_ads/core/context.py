"""Shared server context passed to every connector registrar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .query.runner import StreamFn
from .registry.registry import ConnectorRegistry
from .safety.audit import AuditLedger
from .safety.mode import SafetyMode
from .versioning.version_manager import VersionManager

# (creds dict, API version) -> bound stream function (customer_id, query) -> rows.
StreamFactory = Callable[[dict[str, object], str], StreamFn]
# (customer_id, operations, validate_only) -> API result.
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]
# (creds dict, API version) -> bound mutate function.
MutateFactory = Callable[[dict[str, object], str], MutateFn]


@dataclass
class ServerContext:
    creds: dict[str, object]
    version: str
    stream_factory: StreamFactory
    version_manager: VersionManager
    safety: SafetyMode
    registry: ConnectorRegistry
    audit: AuditLedger
    mutate_factory: MutateFactory | None = None

    def stream(self) -> StreamFn:
        """Build the bound read-stream function for the configured tenant + version."""
        return self.stream_factory(self.creds, self.version)

    def mutate(self) -> MutateFn:
        """Build the bound mutate function; raises if no mutate factory was configured."""
        if self.mutate_factory is None:
            raise RuntimeError("no mutate_factory configured")
        return self.mutate_factory(self.creds, self.version)
