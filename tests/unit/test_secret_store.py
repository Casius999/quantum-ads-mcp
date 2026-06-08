import pytest

from quantum_ads.core.auth.secret_store import EnvSecretStore, TenantCredentials


def test_env_secret_store_loads_from_mapping():
    store = EnvSecretStore(
        {
            "GOOGLE_ADS_DEVELOPER_TOKEN": "dev",
            "GOOGLE_ADS_CLIENT_ID": "cid",
            "GOOGLE_ADS_CLIENT_SECRET": "sec",
            "GOOGLE_ADS_REFRESH_TOKEN": "ref",
            "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
        }
    )
    creds = store.get("default")
    assert isinstance(creds, TenantCredentials)
    assert creds.developer_token == "dev"
    assert creds.login_customer_id == "1234567890"
    assert creds.to_google_ads_dict()["login_customer_id"] == "1234567890"


def test_env_secret_store_missing_required_raises():
    with pytest.raises(KeyError):
        EnvSecretStore({}).get("default")


def test_credentials_never_repr_secrets():
    creds = TenantCredentials(
        developer_token="DEVTOKEN_zzz",
        client_id="CLIENTID_zzz",
        client_secret="CLIENTSECRET_zzz",
        refresh_token="REFRESH_zzz",
    )
    text = repr(creds)
    assert "DEVTOKEN_zzz" not in text
    assert "CLIENTSECRET_zzz" not in text
    assert "REFRESH_zzz" not in text
    assert "redacted=True" in text
