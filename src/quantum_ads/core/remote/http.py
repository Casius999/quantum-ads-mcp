"""Remote serving over Streamable HTTP with OAuth 2.1 bearer tokens, multi-tenant.

The server is an OAuth 2.1 *resource server* (MCP authorization spec):

- every request must carry ``Authorization: Bearer <JWT>``; FastMCP's ``JWTVerifier`` checks the
  signature (JWKS from your IdP, or the local issuer's public key), ``iss``, ``aud`` (bound to
  this server's resource URL, RFC 8707), expiry and the ``ads:read`` scope, and answers ``401``
  with a ``WWW-Authenticate`` challenge otherwise;
- with an external authorization server, Protected Resource Metadata (RFC 9728) is published at
  ``/.well-known/oauth-protected-resource<path>`` so MCP clients can discover where to log in;
- ``PrincipalMiddleware`` turns the verified token into a ``Principal`` (tenant from the
  configured claim, subject, scopes) for the duration of each tool call, so backends, the Ads
  client, the write guard (``ads:write``) and the audit actor all resolve per tenant;
- ``QUANTUM_ADS_TENANTS_FILE`` lists each tenant's credentials; without it the server is
  single-tenant (tenant ``default``) on the operator's environment.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, AuthProvider, RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

from ..tenancy import SCOPE_READ, SCOPE_WRITE, Principal, TenantDirectory, acting_as
from .issuer import ALGORITHM as LOCAL_ALGORITHM
from .issuer import LOCAL_ISSUER

DEFAULT_TENANT = "default"
DEFAULT_PATH = "/mcp"


class RemoteConfigError(ValueError):
    """The HTTP transport is misconfigured; the server refuses to start unauthenticated."""


@dataclass(frozen=True)
class RemoteConfig:
    public_url: str
    path: str
    host: str
    port: int
    audience: str
    issuer: str | None
    algorithm: str
    jwks_uri: str | None
    public_key_pem: str | None
    authorization_servers: tuple[str, ...]
    tenant_claim: str
    tenants_file: Path | None
    rate_limit_rps: float
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]

    @property
    def resource_url(self) -> str:
        return self.public_url.rstrip("/") + self.path


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())


def _endpoint(
    env: Mapping[str, str], host: str | None, port: int | None
) -> tuple[str, int, str, str]:
    bind_host = host or env.get("QUANTUM_ADS_HTTP_HOST") or "127.0.0.1"
    bind_port = port or int(env.get("QUANTUM_ADS_HTTP_PORT") or "8000")
    path = env.get("QUANTUM_ADS_HTTP_PATH") or DEFAULT_PATH
    if not path.startswith("/"):
        raise RemoteConfigError("QUANTUM_ADS_HTTP_PATH must start with '/'")
    public_url = env.get("QUANTUM_ADS_PUBLIC_URL") or f"http://{bind_host}:{bind_port}"
    return bind_host, bind_port, path, public_url


def default_audience(env: Mapping[str, str]) -> str:
    """The audience tokens must carry: QUANTUM_ADS_OAUTH_AUDIENCE, else the resource URL."""
    _, _, path, public_url = _endpoint(env, None, None)
    return env.get("QUANTUM_ADS_OAUTH_AUDIENCE") or public_url.rstrip("/") + path


def remote_config_from_env(
    env: Mapping[str, str], *, host: str | None = None, port: int | None = None
) -> RemoteConfig:
    """Read the HTTP transport settings; fail closed when no token verification is configured."""
    bind_host, bind_port, path, public_url = _endpoint(env, host, port)

    jwks_uri = env.get("QUANTUM_ADS_OAUTH_JWKS_URI") or None
    key_file = env.get("QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE") or None
    if bool(jwks_uri) == bool(key_file):
        raise RemoteConfigError(
            "set exactly one of QUANTUM_ADS_OAUTH_JWKS_URI (identity provider) or "
            "QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE (local issuer, see `quantum-ads-mcp keygen`)"
        )
    public_key_pem = Path(key_file).expanduser().read_text(encoding="utf-8") if key_file else None
    local = public_key_pem is not None
    issuer = env.get("QUANTUM_ADS_OAUTH_ISSUER") or (LOCAL_ISSUER if local else None)
    if not local and not issuer:
        raise RemoteConfigError("QUANTUM_ADS_OAUTH_ISSUER is required with a JWKS URI")
    algorithm = env.get("QUANTUM_ADS_OAUTH_ALGORITHM") or (LOCAL_ALGORITHM if local else "RS256")
    authorization_servers = _csv(env.get("QUANTUM_ADS_OAUTH_AUTHORIZATION_SERVERS")) or (
        (issuer,) if issuer and not local else ()
    )
    tenants_file = env.get("QUANTUM_ADS_TENANTS_FILE") or None
    config = RemoteConfig(
        public_url=public_url,
        path=path,
        host=bind_host,
        port=bind_port,
        audience="",
        issuer=issuer,
        algorithm=algorithm,
        jwks_uri=jwks_uri,
        public_key_pem=public_key_pem,
        authorization_servers=authorization_servers,
        tenant_claim=env.get("QUANTUM_ADS_TENANT_CLAIM") or "tenant",
        tenants_file=Path(tenants_file).expanduser() if tenants_file else None,
        rate_limit_rps=float(env.get("QUANTUM_ADS_RATE_LIMIT_RPS") or "10"),
        allowed_hosts=_csv(env.get("QUANTUM_ADS_ALLOWED_HOSTS")),
        allowed_origins=_csv(env.get("QUANTUM_ADS_ALLOWED_ORIGINS")),
    )
    audience = env.get("QUANTUM_ADS_OAUTH_AUDIENCE") or config.resource_url
    return RemoteConfig(**{**config.__dict__, "audience": audience})


def build_auth(config: RemoteConfig) -> AuthProvider:
    """Token verifier (+ RFC 9728 metadata when an external authorization server is named)."""
    verifier = JWTVerifier(
        public_key=config.public_key_pem,
        jwks_uri=config.jwks_uri,
        issuer=config.issuer,
        audience=config.audience,
        algorithm=config.algorithm,
        required_scopes=[SCOPE_READ],
        base_url=config.public_url,
    )
    if not config.authorization_servers:
        return verifier
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=list(config.authorization_servers),  # type: ignore[arg-type]
        base_url=config.public_url,
        scopes_supported=[SCOPE_READ, SCOPE_WRITE],
        resource_name="Quantum ADS MCP",
    )


def principal_from_token(
    token: AccessToken, *, tenant_claim: str, tenants: TenantDirectory | None
) -> Principal:
    """Map a verified token to a principal; refuse tenants this server does not serve."""
    claims: dict[str, Any] = dict(token.claims or {})
    subject = str(claims.get("sub") or token.client_id or "unknown")
    raw_tenant = claims.get(tenant_claim)
    if tenants is None:
        tenant = str(raw_tenant) if raw_tenant else DEFAULT_TENANT
        if tenant != DEFAULT_TENANT:
            raise ToolError(f"tenant {tenant!r} is not served (single-tenant server)")
    else:
        if not raw_tenant:
            raise ToolError(f"access token has no {tenant_claim!r} claim")
        tenant = str(raw_tenant)
        if tenant not in tenants.tenants():
            raise ToolError(f"tenant {tenant!r} is not served by this server")
    return Principal(tenant_id=tenant, subject=subject, scopes=frozenset(token.scopes or ()))


class PrincipalMiddleware(Middleware):
    """Install the request principal around every tool call."""

    def __init__(self, *, tenant_claim: str, tenants: TenantDirectory | None) -> None:
        self._tenant_claim = tenant_claim
        self._tenants = tenants

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        token = get_access_token()
        if token is None:
            raise ToolError("authentication required")
        principal = principal_from_token(
            token, tenant_claim=self._tenant_claim, tenants=self._tenants
        )
        with acting_as(principal):
            return await call_next(context)


def remote_middleware(config: RemoteConfig, tenants: TenantDirectory | None) -> list[Middleware]:
    """Principal binding, then a per-tenant token-bucket rate limit."""

    def tenant_key(context: MiddlewareContext[Any]) -> str:
        token = get_access_token()
        claims = dict(token.claims or {}) if token is not None else {}
        return str(claims.get(config.tenant_claim) or claims.get("sub") or "anonymous")

    return [
        PrincipalMiddleware(tenant_claim=config.tenant_claim, tenants=tenants),
        RateLimitingMiddleware(
            max_requests_per_second=config.rate_limit_rps, get_client_id=tenant_key
        ),
    ]
