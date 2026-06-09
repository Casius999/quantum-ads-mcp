import pytest

from quantum_ads.core.auth.multitenant import MappingTenantResolver, MultiTenantSecretStore


def _env(token: str) -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": token,
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
    }


def test_multitenant_get_returns_per_tenant_creds():
    store = MultiTenantSecretStore({"acme": _env("acme-dev"), "globex": _env("globex-dev")})
    assert store.get("acme").developer_token == "acme-dev"
    assert store.get("globex").developer_token == "globex-dev"
    assert set(store.tenants()) == {"acme", "globex"}


def test_multitenant_unknown_tenant_raises():
    with pytest.raises(KeyError):
        MultiTenantSecretStore({}).get("nope")


def test_mapping_resolver_matches_raw_and_normalized():
    resolver = MappingTenantResolver({"123-456-7890": "acme"})
    assert resolver.resolve("123-456-7890") == "acme"
    assert resolver.resolve("1234567890") == "acme"


def test_mapping_resolver_defaults_when_unmapped():
    assert MappingTenantResolver({"x": "acme"}).resolve("999") == "default"
