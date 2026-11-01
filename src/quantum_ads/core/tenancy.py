"""Per-request tenancy for remote (HTTP) serving.

Over stdio there is one operator and the process environment holds its credentials. Over HTTP
each request carries an OAuth 2.1 bearer token; the auth middleware turns it into a
``Principal`` (tenant + subject + scopes) and installs it with ``acting_as`` for the duration of
the tool call. Everything credential-bearing — connector backends, the Google Ads stream and
mutate clients, the write guard, the audit actor — resolves through ``current_principal()``, so
one tenant's call can never reach another tenant's credentials. ``ContextVar`` keeps the
principal isolated across concurrent requests (each asyncio task / worker thread sees its own).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from .auth.secret_store import EnvSecretStore

SCOPE_READ = "ads:read"
SCOPE_WRITE = "ads:write"

BackendBuilder = Callable[[dict[str, str]], dict[str, object]]


class UnknownTenantError(KeyError):
    """The token names a tenant this server has no credentials for."""


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    subject: str
    scopes: frozenset[str]

    @property
    def can_write(self) -> bool:
        return SCOPE_WRITE in self.scopes

    @property
    def actor(self) -> str:
        return f"{self.tenant_id}:{self.subject}"


_CURRENT: ContextVar[Principal | None] = ContextVar("quantum_ads_principal", default=None)


def current_principal() -> Principal | None:
    return _CURRENT.get()


@contextmanager
def acting_as(principal: Principal) -> Iterator[Principal]:
    token = _CURRENT.set(principal)
    try:
        yield principal
    finally:
        _CURRENT.reset(token)


class TenantDirectory:
    """Tenant id -> env-style credential mapping, with backends built once per tenant."""

    def __init__(self, tenants: Mapping[str, Mapping[str, str]], builder: BackendBuilder) -> None:
        self._envs = {tid: dict(env) for tid, env in tenants.items()}
        self._builder = builder
        self._backends: dict[str, dict[str, object]] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_file(cls, path: Path, builder: BackendBuilder) -> TenantDirectory:
        """Load ``{"tenants": {"<id>": {"GOOGLE_...": "..."}}}`` (the same variable names as .env)."""
        return cls.from_json(path.read_text(encoding="utf-8"), builder, source=str(path))

    @classmethod
    def from_json(cls, text: str, builder: BackendBuilder, *, source: str) -> TenantDirectory:
        """Parse and validate the tenant map; ``source`` names the origin in error messages."""
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source}: tenants map is not valid JSON ({exc.msg})") from exc
        tenants = raw.get("tenants") if isinstance(raw, dict) else None
        if not isinstance(tenants, dict):
            raise ValueError(f"{source}: expected an object with a 'tenants' mapping")
        for tenant_id, env in tenants.items():
            if not isinstance(env, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in env.items()
            ):
                raise ValueError(f"{source}: tenant {tenant_id!r} must map names to strings")
        return cls(tenants, builder)

    def tenants(self) -> list[str]:
        return list(self._envs)

    def _env(self, tenant_id: str) -> dict[str, str]:
        env = self._envs.get(tenant_id)
        if env is None:
            raise UnknownTenantError(tenant_id)
        return env

    def backends(self, tenant_id: str) -> dict[str, object]:
        env = self._env(tenant_id)
        with self._lock:
            if tenant_id not in self._backends:
                self._backends[tenant_id] = self._builder(env)
            return self._backends[tenant_id]

    def ads_creds(self, tenant_id: str) -> dict[str, object] | None:
        """Google Ads client dict for the tenant, or None when it has no Ads credentials."""
        try:
            return EnvSecretStore(self._env(tenant_id)).get(tenant_id).to_google_ads_dict()
        except UnknownTenantError:
            raise
        except KeyError:
            return None
