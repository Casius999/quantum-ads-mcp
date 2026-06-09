"""Bind a verified bearer token to a per-tenant ServerContext (SP8 remote serving).

The actual Streamable-HTTP transport is FastMCP's runtime concern; this is the testable
auth -> tenant -> context core that a per-request handler calls. Read vs write is derived
from the token scopes (least privilege), independent of the global read-only flag.
"""

from __future__ import annotations

from ..auth.secret_store import SecretStore
from ..context import MutateFactory, ServerContext, StreamFactory
from ..registry.registry import ConnectorRegistry
from ..safety.audit import AuditLedger
from ..safety.mode import SafetyMode
from ..versioning.version_manager import VersionManager
from .token import TokenClaims, verify_hs256


def build_remote_context(
    *,
    token: str,
    secret: str,
    now: int,
    secret_store: SecretStore,
    stream_factory: StreamFactory,
    mutate_factory: MutateFactory | None = None,
    backends: dict[str, object] | None = None,
    version: str = "v24",
) -> tuple[ServerContext, TokenClaims]:
    claims = verify_hs256(token, secret, now)
    creds = secret_store.get(claims.tenant_id).to_google_ads_dict()
    ctx = ServerContext(
        creds=creds,
        version=version,
        stream_factory=stream_factory,
        version_manager=VersionManager(version, client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=not claims.allows_write()),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        mutate_factory=mutate_factory,
        backends=backends or {},
    )
    return ctx, claims
