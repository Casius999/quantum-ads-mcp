"""Multi-tenant credential resolution for remote serving (SP8).

An agency runs one server for many clients; each client (tenant) has its own OAuth
credentials. SP0's single-tenant ``EnvSecretStore`` is wrapped per tenant here.
"""

from __future__ import annotations

from collections.abc import Mapping

from .secret_store import EnvSecretStore, TenantCredentials
from .tenant import normalize_customer_id


class MultiTenantSecretStore:
    """Secret store backed by a per-tenant mapping of env-style credential dicts."""

    def __init__(self, tenants: Mapping[str, Mapping[str, str]]):
        self._stores = {tid: EnvSecretStore(env) for tid, env in tenants.items()}

    def get(self, tenant_id: str) -> TenantCredentials:
        store = self._stores.get(tenant_id)
        if store is None:
            raise KeyError(f"unknown tenant: {tenant_id!r}")
        return store.get(tenant_id)

    def tenants(self) -> list[str]:
        return list(self._stores)


class MappingTenantResolver:
    """Resolve a customer id (or token subject) to a tenant id via an explicit map.

    Falls back to ``default`` when no mapping matches; matches both the raw and the
    dash-normalized customer id.
    """

    def __init__(self, mapping: Mapping[str, str] | None = None, default: str = "default"):
        self._map = dict(mapping or {})
        self._norm = {normalize_customer_id(k): v for k, v in self._map.items()}
        self._default = default

    def resolve(self, key: str) -> str:
        return self._map.get(key) or self._norm.get(normalize_customer_id(key)) or self._default
