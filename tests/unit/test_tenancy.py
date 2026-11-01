"""Per-request tenancy: principal context, tenant directory isolation, scope-gated writes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from quantum_ads.core.safety.mode import MutationBlocked, SafetyMode
from quantum_ads.core.tenancy import (
    SCOPE_READ,
    SCOPE_WRITE,
    Principal,
    TenantDirectory,
    UnknownTenantError,
    acting_as,
    current_principal,
)

_ADS = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "dev",
    "GOOGLE_ADS_CLIENT_ID": "cid",
    "GOOGLE_ADS_CLIENT_SECRET": "sec",
}


def _tenant_env(refresh: str) -> dict[str, str]:
    return {**_ADS, "GOOGLE_ADS_REFRESH_TOKEN": refresh, "GOOGLE_CLOUD_PROJECT": f"proj-{refresh}"}


def test_no_principal_outside_a_request():
    assert current_principal() is None


def test_acting_as_sets_and_restores_the_principal():
    alice = Principal(tenant_id="acme", subject="alice", scopes=frozenset({SCOPE_READ}))
    with acting_as(alice):
        assert current_principal() == alice
    assert current_principal() is None


def test_principal_is_isolated_between_concurrent_tasks():
    async def run(tenant: str) -> str:
        with acting_as(Principal(tenant, tenant, frozenset({SCOPE_READ}))):
            await asyncio.sleep(0)
            principal = current_principal()
            assert principal is not None
            return principal.tenant_id

    async def both() -> list[str]:
        return list(await asyncio.gather(run("a"), run("b")))

    assert asyncio.run(both()) == ["a", "b"]


def test_write_requires_the_write_scope():
    assert Principal("t", "s", frozenset({SCOPE_READ, SCOPE_WRITE})).can_write
    assert not Principal("t", "s", frozenset({SCOPE_READ})).can_write


def test_safety_blocks_a_read_only_principal_even_when_writes_are_enabled():
    safety = SafetyMode(read_only=False)
    safety.guard_mutation("gtm.create_tag")  # stdio: no principal, global flag decides
    with acting_as(Principal("t", "s", frozenset({SCOPE_READ}))), pytest.raises(MutationBlocked):
        safety.guard_mutation("gtm.create_tag")
    with acting_as(Principal("t", "s", frozenset({SCOPE_READ, SCOPE_WRITE}))):
        safety.guard_mutation("gtm.create_tag")


def test_global_read_only_wins_over_a_write_scope():
    with (
        acting_as(Principal("t", "s", frozenset({SCOPE_WRITE}))),
        pytest.raises(MutationBlocked),
    ):
        SafetyMode(read_only=True).guard_mutation("gtm.create_tag")


def test_directory_gives_each_tenant_its_own_credentials_and_backends():
    built: list[str] = []

    def builder(env: dict[str, str]) -> dict[str, object]:
        built.append(env["GOOGLE_ADS_REFRESH_TOKEN"])
        return {"ga4.data": f"backend-{env['GOOGLE_ADS_REFRESH_TOKEN']}"}

    directory = TenantDirectory({"a": _tenant_env("ra"), "b": _tenant_env("rb")}, builder)
    assert directory.tenants() == ["a", "b"]
    assert directory.backends("a")["ga4.data"] == "backend-ra"
    assert directory.backends("b")["ga4.data"] == "backend-rb"
    assert directory.backends("a")["ga4.data"] == "backend-ra"
    assert built == ["ra", "rb"]  # built once per tenant, then cached
    assert directory.ads_creds("b")["refresh_token"] == "rb"


def test_unknown_tenant_is_refused():
    directory = TenantDirectory({"a": _tenant_env("ra")}, lambda env: {})
    with pytest.raises(UnknownTenantError):
        directory.backends("mallory")


def test_tenant_without_ads_credentials_has_no_ads_creds():
    directory = TenantDirectory({"a": {"GOOGLE_CLOUD_PROJECT": "p"}}, lambda env: {})
    assert directory.ads_creds("a") is None


def test_directory_loads_from_a_json_file(tmp_path: Path):
    path = tmp_path / "tenants.json"
    path.write_text(json.dumps({"tenants": {"acme": _tenant_env("r1")}}), encoding="utf-8")
    directory = TenantDirectory.from_file(path, lambda env: {"k": env["GOOGLE_CLOUD_PROJECT"]})
    assert directory.backends("acme") == {"k": "proj-r1"}


def test_directory_file_rejects_non_string_values(tmp_path: Path):
    path = tmp_path / "tenants.json"
    path.write_text(json.dumps({"tenants": {"acme": {"GOOGLE_CLOUD_PROJECT": 1}}}))
    with pytest.raises(ValueError, match="acme"):
        TenantDirectory.from_file(path, lambda env: {})
