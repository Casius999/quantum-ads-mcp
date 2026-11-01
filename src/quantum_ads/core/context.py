"""Shared server context passed to every connector registrar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from .query.runner import StreamFn
from .registry.registry import ConnectorRegistry
from .safety.audit import AuditLedger
from .safety.mode import SafetyMode
from .tenancy import TenantDirectory, current_principal
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
    # Per-connector data-access objects keyed by name (e.g. "ga4.read", "gtm.write").
    # Lets every product connector bring its own client without bloating the context.
    backends: dict[str, object] = field(default_factory=dict)
    # Remote multi-tenant serving: per-tenant credentials, selected by the request principal.
    tenants: TenantDirectory | None = None
    _clients: dict[tuple[str, str], object] = field(default_factory=dict, repr=False)

    def _tenant_id(self) -> str | None:
        """The request's tenant when serving a tenant directory, else None (operator creds)."""
        principal = current_principal()
        if principal is None or self.tenants is None:
            return None
        return principal.tenant_id

    def _ads_creds(self, tenant_id: str | None) -> dict[str, object]:
        if tenant_id is None or self.tenants is None:
            return self.creds
        creds = self.tenants.ads_creds(tenant_id)
        if creds is None:
            raise RuntimeError(f"tenant {tenant_id!r} has no Google Ads credentials configured")
        return creds

    def _client(self, kind: str, build: Callable[[dict[str, object]], object]) -> object:
        tenant_id = self._tenant_id()
        key = (kind, tenant_id or "")
        if key not in self._clients:
            self._clients[key] = build(self._ads_creds(tenant_id))
        return self._clients[key]

    def backend(self, name: str) -> object | None:
        """Return the named backend or None if not configured (connector degrades gracefully).

        Under a tenant principal only that tenant's backends are visible — never the operator's.
        """
        tenant_id = self._tenant_id()
        if tenant_id is not None and self.tenants is not None:
            return self.tenants.backends(tenant_id).get(name)
        return self.backends.get(name)

    def stream(self) -> StreamFn:
        """Return the read-stream for the configured tenant + version, built on first use.

        Building the real client authenticates (token refresh), so doing it at registration
        would crash server startup on missing or invalid Google Ads credentials and take every
        other connector down with it. The client is built on the first call — once per tenant
        under remote serving — and reused; a failed build is retried on the next call.
        """

        def lazy_stream(customer_id: str, query: str) -> list[dict[str, object]]:
            stream = self._client("stream", lambda creds: self.stream_factory(creds, self.version))
            return cast(StreamFn, stream)(customer_id, query)

        return lazy_stream

    def mutate(self) -> MutateFn:
        """The bound mutate function for the current tenant (built once per tenant)."""
        factory = self.mutate_factory
        if factory is None:
            raise RuntimeError("no mutate_factory configured")
        return cast(MutateFn, self._client("mutate", lambda creds: factory(creds, self.version)))
