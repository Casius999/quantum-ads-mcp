"""Sign in with Google: fail-closed config, per-user principal and credentials, OAuth discovery."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken

from quantum_ads.__main__ import assemble
from quantum_ads.core.remote import google_signin
from quantum_ads.core.remote.http import RemoteConfigError
from quantum_ads.core.tenancy import SCOPE_WRITE, Principal, acting_as, current_principal
from quantum_ads.server import build_server

ENV = {
    "QUANTUM_ADS_AUTH": "google",
    "QUANTUM_ADS_GOOGLE_CLIENT_ID": "cid.apps.googleusercontent.com",
    "QUANTUM_ADS_GOOGLE_CLIENT_SECRET": "sec",
    "QUANTUM_ADS_PUBLIC_URL": "https://ads.example",
    "QUANTUM_ADS_GOOGLE_ALLOWED": "boss@agency.example,@agency.example",
    "QUANTUM_ADS_GOOGLE_WRITERS": "boss@agency.example",
    "QUANTUM_ADS_JWT_SIGNING_KEY": "test-signing-key",
}


def test_config_is_fail_closed_and_defaults_the_scopes():
    config = google_signin.signin_config_from_env(ENV)
    assert config.public_url == "https://ads.example" and config.path == "/mcp"
    assert config.scopes == google_signin.GOOGLE_SCOPES
    assert config.writers == ("boss@agency.example",)
    with pytest.raises(RemoteConfigError, match="CLIENT_ID"):
        google_signin.signin_config_from_env({**ENV, "QUANTUM_ADS_GOOGLE_CLIENT_SECRET": ""})
    with pytest.raises(RemoteConfigError, match="QUANTUM_ADS_GOOGLE_ALLOWED is required"):
        google_signin.signin_config_from_env({**ENV, "QUANTUM_ADS_GOOGLE_ALLOWED": ""})
    custom = google_signin.signin_config_from_env({**ENV, "QUANTUM_ADS_GOOGLE_SCOPES": "openid,x"})
    assert custom.scopes == ("openid", "x")


def test_allowlist_matches_emails_and_domains():
    rules = ("boss@agency.example", "@client.example")
    assert google_signin.matches("Boss@Agency.example", rules)
    assert google_signin.matches("anyone@client.example", rules)
    assert not google_signin.matches("intruder@evil.example", rules)
    assert not google_signin.matches("x@notclient.example.org", rules)


def test_principal_reads_or_writes_by_allowlist():
    config = google_signin.signin_config_from_env(ENV)
    boss = google_signin.principal_for_google_user(
        email="boss@agency.example", verified=True, subject="1", token="ya29.boss", config=config
    )
    staff = google_signin.principal_for_google_user(
        email="Staff@agency.example", verified=True, subject="2", token="ya29.staff", config=config
    )
    assert boss.can_write and not staff.can_write
    assert staff.tenant_id == "staff@agency.example" and staff.credential == "ya29.staff"
    assert "ya29" not in repr(staff)
    for email, verified in (("boss@agency.example", False), ("x@evil.example", True), ("", True)):
        with pytest.raises(ToolError):
            google_signin.principal_for_google_user(
                email=email, verified=verified, subject="3", token="t", config=config
            )


def test_user_directory_builds_backends_from_the_users_token_only():
    built: list[dict[str, str]] = []

    def builder(env):  # type: ignore[no-untyped-def]
        built.append(dict(env))
        return {"marker": len(built)}

    operator = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "dev",
        "GOOGLE_OAUTH_REFRESH_TOKEN": "operator-refresh",
        "GOOGLE_ADS_REFRESH_TOKEN": "operator-ads-refresh",
        "GOOGLE_ADS_CLIENT_SECRET": "operator-secret",
        "LOOKERSDK_CLIENT_SECRET": "looker",
        "GOOGLE_CLOUD_PROJECT": "p",
    }
    directory = google_signin.GoogleUserDirectory(operator, builder)
    alice = Principal("alice@a.example", "1", frozenset(), credential="tok-1")
    with acting_as(alice):
        first = directory.backends("alice@a.example")
        assert directory.backends("alice@a.example") is first  # cached for the same token
        assert directory.ads_creds("alice@a.example") == {
            "developer_token": "dev",
            "access_token": "tok-1",
            "use_proto_plus": True,
        }
    assert built[0] == {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "dev",
        "GOOGLE_CLOUD_PROJECT": "p",
        "QUANTUM_ADS_GOOGLE_ACCESS_TOKEN": "tok-1",
    }
    with acting_as(Principal("alice@a.example", "1", frozenset(), credential="tok-2")):
        assert directory.backends("alice@a.example") == {"marker": 2}  # hourly rotation
    with pytest.raises(ToolError, match="no signed-in Google user"):
        directory.backends("alice@a.example")
    with acting_as(alice), pytest.raises(ToolError):
        directory.backends("bob@a.example")
    with acting_as(alice):
        assert google_signin.GoogleUserDirectory({}, builder).ads_creds("alice@a.example") is None


def _token(email: str, token: str = "ya29.user") -> AccessToken:
    return AccessToken(
        token=token,
        client_id="sub-1",
        scopes=["openid"],
        claims={"sub": "sub-1", "email": email, "email_verified": True},
    )


def test_middleware_runs_each_tool_as_the_signed_in_user(monkeypatch: pytest.MonkeyPatch):
    config = google_signin.signin_config_from_env(ENV)
    seen: list[tuple[str, bool, str | None]] = []
    current: dict[str, AccessToken | None] = {"token": _token("boss@agency.example")}
    monkeypatch.setattr(google_signin, "get_access_token", lambda: current["token"])

    def whoami() -> dict[str, object]:
        principal = current_principal()
        assert principal is not None
        seen.append((principal.tenant_id, SCOPE_WRITE in principal.scopes, principal.credential))
        return {"ok": True}

    def register(app, ctx):  # type: ignore[no-untyped-def]
        app.tool(name="whoami")(whoami)

    app = build_server(
        env={"QUANTUM_ADS_READ_ONLY": "false"},
        stream_factory=lambda c, v: lambda cid, q: [],
        connectors=[register],
        middleware=google_signin.google_middleware(config),
    ).app

    async def scenario() -> list[bool]:
        errors = []
        async with Client(app) as client:
            for token in (_token("boss@agency.example"), _token("x@evil.example"), None):
                current["token"] = token
                result = await client.call_tool("whoami", {}, raise_on_error=False)
                errors.append(result.is_error)
        return errors

    assert asyncio.run(scenario()) == [False, True, True]
    assert seen == [("boss@agency.example", True, "ya29.user")]


def test_served_app_publishes_oauth_metadata_and_dynamic_registration(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTMCP_HOME", str(tmp_path))
    env = {**ENV, "QUANTUM_ADS_AUDIT_DIR": "", "QUANTUM_ADS_LOG_CALLS": "false"}
    config = google_signin.signin_config_from_env(env)
    http_app = assemble(env, config).app.http_app(path=config.path)

    async def scenario() -> tuple[int, dict[str, object], int]:
        transport = httpx.ASGITransport(app=http_app)
        async with httpx.AsyncClient(transport=transport, base_url="https://ads.example") as client:
            meta = await client.get("/.well-known/oauth-authorization-server")
            unauth = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
            return meta.status_code, meta.json(), unauth.status_code

    status, metadata, unauthenticated = asyncio.run(scenario())
    assert status == 200
    assert str(metadata["registration_endpoint"]).endswith("/register")
    assert "https://www.googleapis.com/auth/adwords" in metadata["scopes_supported"]  # type: ignore[operator]
    assert unauthenticated == 401


def test_ads_client_follows_the_users_token_rotation(monkeypatch: pytest.MonkeyPatch):
    config = google_signin.signin_config_from_env(ENV)
    current = {"token": _token("boss@agency.example", "tok-1")}
    monkeypatch.setattr(google_signin, "get_access_token", lambda: current["token"])
    clients: list[dict[str, object]] = []

    def stream_factory(creds, version):  # type: ignore[no-untyped-def]
        clients.append(creds)
        return lambda customer_id, query: [{"n": len(clients)}]

    def register(app, ctx):  # type: ignore[no-untyped-def]
        stream = ctx.stream()
        app.tool(name="peek")(lambda: {"rows": stream("1", "SELECT customer.id FROM customer")})

    app = build_server(
        env={"GOOGLE_ADS_DEVELOPER_TOKEN": "dev"},
        stream_factory=stream_factory,
        connectors=[register],
        middleware=google_signin.google_middleware(config),
        tenants=google_signin.GoogleUserDirectory(
            {"GOOGLE_ADS_DEVELOPER_TOKEN": "dev"}, lambda e: {}
        ),
    ).app

    async def scenario() -> None:
        async with Client(app) as client:
            for token in ("tok-1", "tok-1", "tok-2"):
                current["token"] = _token("boss@agency.example", token)
                await client.call_tool("peek", {})

    asyncio.run(scenario())
    assert [c["access_token"] for c in clients] == ["tok-1", "tok-2"]
