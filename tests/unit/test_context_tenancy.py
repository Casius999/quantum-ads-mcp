"""ServerContext resolves every credential-bearing object through the request principal."""

from __future__ import annotations

import pytest

from quantum_ads.core.context import ServerContext
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.tenancy import (
    SCOPE_READ,
    Principal,
    TenantDirectory,
    UnknownTenantError,
    acting_as,
)
from quantum_ads.core.versioning.version_manager import VersionManager


def _env(refresh: str) -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": refresh,
    }


def _ctx(tenants: TenantDirectory | None, stream_calls: list[object]) -> ServerContext:
    def stream_factory(creds: dict[str, object], version: str):  # type: ignore[no-untyped-def]
        stream_calls.append(creds["refresh_token"])
        return lambda customer_id, query: [{"refresh_token": creds["refresh_token"]}]

    def mutate_factory(creds: dict[str, object], version: str):  # type: ignore[no-untyped-def]
        return lambda cid, ops, validate_only: {"refresh_token": creds["refresh_token"]}

    return ServerContext(
        creds={"refresh_token": "operator"},
        version="v26",
        stream_factory=stream_factory,
        version_manager=VersionManager("v26", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=True),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        mutate_factory=mutate_factory,
        backends={"ga4.data": "operator-backend"},
        tenants=tenants,
    )


def _as(tenant: str):  # type: ignore[no-untyped-def]
    return acting_as(Principal(tenant, "user", frozenset({SCOPE_READ})))


def _directory() -> TenantDirectory:
    return TenantDirectory(
        {"a": _env("ra"), "b": _env("rb")},
        lambda env: {"ga4.data": f"backend-{env['GOOGLE_ADS_REFRESH_TOKEN']}"},
    )


def test_stdio_without_principal_uses_the_operator_credentials():
    calls: list[object] = []
    ctx = _ctx(_directory(), calls)
    assert ctx.backend("ga4.data") == "operator-backend"
    assert ctx.stream()("1", "q") == [{"refresh_token": "operator"}]


def test_backends_follow_the_principal_and_never_fall_back_to_the_operator():
    ctx = _ctx(_directory(), [])
    with _as("a"):
        assert ctx.backend("ga4.data") == "backend-ra"
        assert ctx.backend("bigquery.api") is None
    with _as("b"):
        assert ctx.backend("ga4.data") == "backend-rb"


def test_ads_stream_and_mutate_use_the_tenant_credentials_built_once_per_tenant():
    calls: list[object] = []
    ctx = _ctx(_directory(), calls)
    stream = ctx.stream()  # captured at registration, resolved per call
    with _as("a"):
        assert stream("1", "q") == [{"refresh_token": "ra"}]
        assert stream("1", "q") == [{"refresh_token": "ra"}]
        assert ctx.mutate()("1", [], True) == {"refresh_token": "ra"}
    with _as("b"):
        assert stream("1", "q") == [{"refresh_token": "rb"}]
    assert calls == ["ra", "rb"]


def test_unknown_tenant_cannot_reach_any_backend():
    ctx = _ctx(_directory(), [])
    with _as("mallory"), pytest.raises(UnknownTenantError):
        ctx.backend("ga4.data")


def test_tenant_without_ads_credentials_gets_an_explicit_error():
    directory = TenantDirectory({"a": {"GOOGLE_CLOUD_PROJECT": "p"}}, lambda env: {})
    ctx = _ctx(directory, [])
    with _as("a"), pytest.raises(RuntimeError, match="Google Ads credentials"):
        ctx.stream()("1", "q")


def test_single_tenant_http_without_a_directory_uses_the_operator_credentials():
    ctx = _ctx(None, [])
    with _as("default"):
        assert ctx.backend("ga4.data") == "operator-backend"
