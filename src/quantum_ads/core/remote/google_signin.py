"""Remote serving with "Sign in with Google": each user's own Google account is the credential.

``QUANTUM_ADS_AUTH=google`` turns the HTTP server into an OAuth proxy in front of Google
(FastMCP ``GoogleProvider``: Dynamic Client Registration and CIMD for MCP clients, PKCE, consent
screen). A user signs in with Google and consents to the marketing scopes; the server never sees
a password, keeps only an encrypted, revocable token, and runs every tool on that user's own
Google token — so each user reaches exactly the accounts their Google identity can reach.

What stays on the operator side: the Google Ads developer token, the GCP project, optional free
LLM endpoints. Who may use the server is explicit and fail-closed: ``QUANTUM_ADS_GOOGLE_ALLOWED``
lists e-mails and ``@domains``; ``QUANTUM_ADS_GOOGLE_WRITERS`` (same syntax) may write, everyone
else is read-only. Over 100 external users, Google requires verifying the OAuth app for the
sensitive marketing scopes.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

from ..tenancy import (
    SCOPE_READ,
    SCOPE_WRITE,
    Principal,
    TenantDirectory,
    acting_as,
    current_principal,
)
from .http import RemoteConfigError, _csv, _endpoint

GOOGLE_SCOPES: tuple[str, ...] = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/tagmanager.edit.containers",
    "https://www.googleapis.com/auth/content",
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/youtube.readonly",
)
# Operator secrets a signed-in user must never borrow.
_OPERATOR_ONLY = ("REFRESH_TOKEN", "CLIENT_SECRET", "LOOKERSDK_", "QUANTUM_ADS_TENANTS")


@dataclass(frozen=True)
class SignInConfig:
    client_id: str
    client_secret: str
    public_url: str
    path: str
    host: str
    port: int
    allowed: tuple[str, ...]
    writers: tuple[str, ...]
    scopes: tuple[str, ...]
    rate_limit_rps: float
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    jwt_signing_key: str | None


def signin_config_from_env(
    env: Mapping[str, str], *, host: str | None = None, port: int | None = None
) -> SignInConfig:
    """Read the sign-in settings; refuse to start without an OAuth client and an allowlist."""
    bind_host, bind_port, path, public_url = _endpoint(env, host, port)
    client_id = env.get("QUANTUM_ADS_GOOGLE_CLIENT_ID")
    client_secret = env.get("QUANTUM_ADS_GOOGLE_CLIENT_SECRET")
    if not (client_id and client_secret):
        raise RemoteConfigError(
            "QUANTUM_ADS_AUTH=google needs QUANTUM_ADS_GOOGLE_CLIENT_ID and "
            "QUANTUM_ADS_GOOGLE_CLIENT_SECRET (a Web OAuth client whose redirect URI is "
            "<QUANTUM_ADS_PUBLIC_URL>/auth/callback)"
        )
    allowed = _csv(env.get("QUANTUM_ADS_GOOGLE_ALLOWED"))
    if not allowed:
        raise RemoteConfigError(
            "QUANTUM_ADS_GOOGLE_ALLOWED is required (e-mails and/or @domains): without it any "
            "Google account could use this server and its developer token"
        )
    return SignInConfig(
        client_id=client_id,
        client_secret=client_secret,
        public_url=public_url,
        path=path,
        host=bind_host,
        port=bind_port,
        allowed=allowed,
        writers=_csv(env.get("QUANTUM_ADS_GOOGLE_WRITERS")),
        scopes=_csv(env.get("QUANTUM_ADS_GOOGLE_SCOPES")) or GOOGLE_SCOPES,
        rate_limit_rps=float(env.get("QUANTUM_ADS_RATE_LIMIT_RPS") or "10"),
        allowed_hosts=_csv(env.get("QUANTUM_ADS_ALLOWED_HOSTS")),
        allowed_origins=_csv(env.get("QUANTUM_ADS_ALLOWED_ORIGINS")),
        jwt_signing_key=env.get("QUANTUM_ADS_JWT_SIGNING_KEY") or None,
    )


def matches(email: str, rules: tuple[str, ...]) -> bool:
    """``rules`` are exact e-mails or ``@domain`` suffixes, compared case-insensitively."""
    address = email.strip().lower()
    for rule in (r.strip().lower() for r in rules):
        if rule.startswith("@") and address.endswith(rule):
            return True
        if address == rule:
            return True
    return False


def build_google_auth(config: SignInConfig) -> AuthProvider:
    """The OAuth proxy: MCP clients register (DCR/CIMD) and users log in at Google."""
    from fastmcp.server.auth.providers.google import GoogleProvider

    return GoogleProvider(
        client_id=config.client_id,
        client_secret=config.client_secret,
        base_url=config.public_url,
        required_scopes=["openid", "https://www.googleapis.com/auth/userinfo.email"],
        valid_scopes=list(config.scopes),
        # Offline access so the proxy can refresh the user's Google token transparently.
        extra_authorize_params={"access_type": "offline", "prompt": "consent"},
        jwt_signing_key=config.jwt_signing_key,
    )


def principal_for_google_user(
    *, email: str, verified: bool, subject: str, token: str, config: SignInConfig
) -> Principal:
    if not (email and verified):
        raise ToolError("a verified Google e-mail is required")
    if not matches(email, config.allowed):
        raise ToolError(f"{email} is not allowed on this server")
    scopes = {SCOPE_READ} | ({SCOPE_WRITE} if matches(email, config.writers) else set())
    return Principal(
        tenant_id=email.lower(), subject=subject, scopes=frozenset(scopes), credential=token
    )


class GooglePrincipalMiddleware(Middleware):
    """Bind each request to the signed-in Google user, with their own token as credential."""

    def __init__(self, config: SignInConfig) -> None:
        self._config = config

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        return await self._as_user(context, call_next)

    async def on_read_resource(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        return await self._as_user(context, call_next)

    async def on_get_prompt(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        return await self._as_user(context, call_next)

    async def _as_user(self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]) -> Any:
        token = get_access_token()
        if token is None:
            raise ToolError("authentication required")
        claims = dict(token.claims or {})
        principal = principal_for_google_user(
            email=str(claims.get("email") or ""),
            verified=bool(claims.get("email_verified")),
            subject=str(claims.get("sub") or token.client_id),
            token=token.token,
            config=self._config,
        )
        with acting_as(principal):
            return await call_next(context)


def google_middleware(config: SignInConfig) -> list[Middleware]:
    def user_key(context: MiddlewareContext[Any]) -> str:
        token = get_access_token()
        claims = dict(token.claims or {}) if token is not None else {}
        return str(claims.get("email") or claims.get("sub") or "anonymous")

    return [
        GooglePrincipalMiddleware(config),
        RateLimitingMiddleware(
            max_requests_per_second=config.rate_limit_rps, get_client_id=user_key
        ),
    ]


class GoogleUserDirectory(TenantDirectory):
    """Backends built from the operator's environment plus the signed-in user's own token.

    Operator refresh tokens and client secrets are stripped, so a user only ever acts as
    themself. Backends are cached per token fingerprint (tokens rotate hourly; the latest
    one per user is kept).
    """

    def __init__(
        self,
        operator_env: Mapping[str, str],
        builder: Callable[[Mapping[str, str]], dict[str, object]],
    ) -> None:
        super().__init__({}, builder)
        self._base = {
            k: v for k, v in operator_env.items() if not any(m in k for m in _OPERATOR_ONLY)
        }
        self._user_backends: dict[str, tuple[str, dict[str, object]]] = {}
        self._user_lock = threading.Lock()

    @staticmethod
    def _signed_in(tenant_id: str) -> Principal:
        principal = current_principal()
        if principal is None or principal.tenant_id != tenant_id or not principal.credential:
            raise ToolError("no signed-in Google user for this request")
        return principal

    def backends(self, tenant_id: str) -> dict[str, object]:
        principal = self._signed_in(tenant_id)
        with self._user_lock:
            cached = self._user_backends.get(tenant_id)
            if cached is None or cached[0] != principal.credential_key:
                env = {**self._base, "QUANTUM_ADS_GOOGLE_ACCESS_TOKEN": str(principal.credential)}
                cached = (principal.credential_key, self._builder(env))
                self._user_backends[tenant_id] = cached
            return cached[1]

    def ads_creds(self, tenant_id: str) -> dict[str, object] | None:
        principal = self._signed_in(tenant_id)
        developer_token = self._base.get("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not developer_token:
            return None
        return {
            "developer_token": developer_token,
            "access_token": principal.credential,
            "use_proto_plus": True,
        }
