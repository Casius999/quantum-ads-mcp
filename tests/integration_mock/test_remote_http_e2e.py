"""Real Streamable-HTTP server + real MCP client: OAuth 2.1 bearer auth and tenant isolation.

The server runs on a local uvicorn port exactly as ``quantum-ads-mcp serve --transport http``
assembles it (``__main__.assemble``), with tokens minted by the local Ed25519 issuer. Backends
are fakes that report which tenant's credentials they were built from, so isolation is observable.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2 as httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

import quantum_ads.__main__ as entry
from quantum_ads.core.remote.http import remote_config_from_env
from quantum_ads.core.remote.issuer import keygen, mint_token
from quantum_ads.core.tenancy import SCOPE_READ, SCOPE_WRITE

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _fake_backends(env: dict[str, str]) -> dict[str, object]:
    project = env.get("GOOGLE_CLOUD_PROJECT", "operator")

    def read(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        return [{"tenant_project": project, "op": op}]

    def mutate(parent: str, ops: list[dict[str, object]], validate_only: bool) -> dict[str, object]:
        return {"tenant_project": project, "validate_only": validate_only}

    return {"ga4.admin": read, "ga4.admin.mutate": mutate}


class _Server:
    def __init__(self, tmp: Path, *, multi_tenant: bool, read_only: str = "false") -> None:
        keys = keygen(tmp / "issuer")
        self.private_key = keys.private_key
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}/mcp"
        env = {
            "QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE": str(keys.public_key),
            "QUANTUM_ADS_HTTP_PORT": str(self.port),
            "QUANTUM_ADS_AUDIT_DIR": str(tmp / "audit"),
            "QUANTUM_ADS_READ_ONLY": read_only,
            "QUANTUM_ADS_CONNECTORS": "ga4",
            "GOOGLE_CLOUD_PROJECT": "operator-project",
        }
        if multi_tenant:
            tenants = {
                "acme": {"GOOGLE_CLOUD_PROJECT": "acme-project"},
                "globex": {"GOOGLE_CLOUD_PROJECT": "globex-project"},
            }
            path = tmp / "tenants.json"
            path.write_text(json.dumps({"tenants": tenants}), encoding="utf-8")
            env["QUANTUM_ADS_TENANTS_FILE"] = str(path)
        self.env = env
        self.audit_log = tmp / "audit" / "audit.jsonl"

    def token(self, tenant: str, scopes: list[str], **kwargs: object) -> str:
        return mint_token(
            self.private_key,
            tenant=tenant,
            subject=f"{tenant}-user",
            scopes=scopes,
            audience=str(kwargs.pop("audience", self.url)),
            **kwargs,  # type: ignore[arg-type]
        )

    def run(self) -> Iterator[_Server]:
        remote = remote_config_from_env(self.env)
        original = entry.build_backends
        entry.build_backends = _fake_backends  # type: ignore[assignment]
        try:
            app = entry.assemble(self.env, remote).app
        finally:
            entry.build_backends = original  # type: ignore[assignment]
        thread = threading.Thread(
            target=lambda: asyncio.run(
                app.run_http_async(
                    show_banner=False,
                    host="127.0.0.1",
                    port=self.port,
                    path=remote.path,
                    log_level="warning",
                )
            ),
            daemon=True,
        )
        thread.start()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    break
            time.sleep(0.05)
        yield self


@pytest.fixture
def multi(tmp_path: Path) -> Iterator[_Server]:
    yield from _Server(tmp_path, multi_tenant=True).run()


@pytest.fixture
def single(tmp_path: Path) -> Iterator[_Server]:
    yield from _Server(tmp_path, multi_tenant=False).run()


def _call(server: _Server, token: str, tool: str, args: dict[str, object]) -> object:
    async def scenario() -> object:
        transport = StreamableHttpTransport(
            server.url, headers={"Authorization": f"Bearer {token}"}
        )
        async with Client(transport) as client:
            result = await client.call_tool(tool, args, raise_on_error=False)
            return result.structured_content if not result.is_error else f"ERROR {result.content}"

    return asyncio.run(scenario())


def _post_initialize(server: _Server, headers: dict[str, str]) -> httpx.Response:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "0"},
        },
    }
    return httpx.post(
        server.url,
        json=body,
        headers={"Accept": "application/json, text/event-stream", **headers},
        timeout=10,
    )


def test_request_without_a_token_is_rejected_with_a_bearer_challenge(multi: _Server):
    response = _post_initialize(multi, {})
    assert response.status_code == 401
    assert response.headers["www-authenticate"].lower().startswith("bearer")


@pytest.mark.parametrize(
    "mutation",
    ["wrong_audience", "expired", "forged"],
)
def test_invalid_tokens_are_rejected(multi: _Server, tmp_path: Path, mutation: str):
    if mutation == "wrong_audience":
        token = multi.token("acme", [SCOPE_READ], audience="https://elsewhere.example/mcp")
    elif mutation == "expired":
        token = multi.token("acme", [SCOPE_READ], now=int(time.time()) - 7200, ttl_seconds=60)
    else:
        other = keygen(tmp_path / "attacker")
        token = mint_token(
            other.private_key, tenant="acme", scopes=[SCOPE_READ], audience=multi.url
        )
    assert _post_initialize(multi, {"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_without_the_read_scope_is_rejected(multi: _Server):
    token = multi.token("acme", ["something:else"])
    assert _post_initialize(multi, {"Authorization": f"Bearer {token}"}).status_code in (401, 403)


def test_each_tenant_only_reaches_its_own_credentials(multi: _Server):
    args = {"account_id": "123"}
    acme = _call(multi, multi.token("acme", [SCOPE_READ]), "ga4.admin.list_properties", args)
    globex = _call(multi, multi.token("globex", [SCOPE_READ]), "ga4.admin.list_properties", args)
    assert acme == {
        "rows": [{"tenant_project": "acme-project", "op": "listProperties"}],
        "row_count": 1,
    }
    assert isinstance(globex, dict)
    assert globex["rows"][0]["tenant_project"] == "globex-project"  # type: ignore[index]


def test_unknown_tenant_is_refused(multi: _Server):
    result = _call(
        multi,
        multi.token("initech", [SCOPE_READ]),
        "ga4.admin.list_properties",
        {"account_id": "1"},
    )
    assert isinstance(result, str) and "not served" in result


def test_read_scope_cannot_write_even_with_writes_enabled(multi: _Server):
    args = {"property_id": "properties/1", "event_name": "purchase"}
    result = _call(multi, multi.token("acme", [SCOPE_READ]), "ga4.admin.create_key_event", args)
    assert isinstance(result, dict)
    assert result["error"]["code"] == "READ_ONLY"  # type: ignore[index]
    assert "ads:write" in result["error"]["message"]  # type: ignore[index]


def test_write_scope_runs_the_guarded_flow_and_audits_the_tenant(multi: _Server):
    token = multi.token("acme", [SCOPE_READ, SCOPE_WRITE])
    args: dict[str, object] = {"property_id": "properties/1", "event_name": "purchase"}
    preview = _call(multi, token, "ga4.admin.create_key_event", args)
    assert isinstance(preview, dict) and preview["applied"] is False
    assert preview["preview"] == {"tenant_project": "acme-project", "validate_only": True}
    applied = _call(
        multi, token, "ga4.admin.create_key_event", {**args, "confirm": preview["confirm_token"]}
    )
    assert isinstance(applied, dict) and applied["applied"] is True
    record = json.loads(multi.audit_log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["actor"] == "acme:acme-user"
    assert record["op"] == "ga4.admin.create_key_event"


def test_single_tenant_server_serves_the_default_tenant_only(single: _Server):
    ok = _call(
        single,
        single.token("default", [SCOPE_READ]),
        "ga4.admin.list_properties",
        {"account_id": "1"},
    )
    assert isinstance(ok, dict)
    assert ok["rows"][0]["tenant_project"] == "operator-project"  # type: ignore[index]
    refused = _call(
        single, single.token("acme", [SCOPE_READ]), "ga4.admin.list_properties", {"account_id": "1"}
    )
    assert isinstance(refused, str) and "single-tenant" in refused


def test_external_identity_provider_via_jwks_and_protected_resource_metadata(tmp_path: Path):
    """IdP mode: RS256 tokens verified against a remote JWKS; RFC 9728 metadata is published."""
    import http.server

    from fastmcp.server.auth.providers.jwt import RSAKeyPair
    from joserfc import jwk

    pair = RSAKeyPair.generate()
    public = jwk.import_key(pair.public_key.encode(), "RSA").as_dict()
    jwks = json.dumps({"keys": [{**public, "kid": "k1", "use": "sig", "alg": "RS256"}]}).encode()

    class JwksHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(jwks)

        def log_message(self, *args: object) -> None:
            return None

    idp = http.server.ThreadingHTTPServer(("127.0.0.1", 0), JwksHandler)
    threading.Thread(target=idp.serve_forever, daemon=True).start()
    issuer = f"http://127.0.0.1:{idp.server_address[1]}"

    server = _Server(tmp_path, multi_tenant=True)
    server.env.pop("QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE")
    server.env.update(
        QUANTUM_ADS_OAUTH_JWKS_URI=f"{issuer}/jwks.json",
        QUANTUM_ADS_OAUTH_ISSUER=issuer,
    )
    try:
        running = next(server.run())
        metadata = httpx.get(
            f"http://127.0.0.1:{running.port}/.well-known/oauth-protected-resource/mcp", timeout=10
        ).json()
        assert metadata["resource"] == running.url
        assert [s.rstrip("/") for s in metadata["authorization_servers"]] == [issuer]
        assert set(metadata["scopes_supported"]) == {SCOPE_READ, SCOPE_WRITE}

        challenge = _post_initialize(running, {}).headers["www-authenticate"]
        assert "resource_metadata=" in challenge

        token = pair.create_token(
            subject="alice",
            issuer=issuer,
            audience=running.url,
            scopes=[SCOPE_READ],
            additional_claims={"tenant": "globex"},
            kid="k1",
        )
        result = _call(running, token, "ga4.admin.list_properties", {"account_id": "1"})
        assert isinstance(result, dict)
        assert result["rows"][0]["tenant_project"] == "globex-project"  # type: ignore[index]
    finally:
        idp.shutdown()
