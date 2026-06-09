import pytest

from quantum_ads.core.auth.multitenant import MultiTenantSecretStore
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.core.remote.session import build_remote_context
from quantum_ads.core.remote.token import TokenError, sign_hs256

SECRET = "s3cr3t"


def _store() -> MultiTenantSecretStore:
    return MultiTenantSecretStore(
        {
            "acme": {
                "GOOGLE_ADS_DEVELOPER_TOKEN": "acme-dev",
                "GOOGLE_ADS_CLIENT_ID": "c",
                "GOOGLE_ADS_CLIENT_SECRET": "x",
                "GOOGLE_ADS_REFRESH_TOKEN": "r",
            }
        }
    )


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def test_write_scope_yields_writable_context_for_tenant():
    token = sign_hs256({"sub": "acme", "scope": "ads:read ads:write", "exp": 2000}, SECRET)
    ctx, claims = build_remote_context(
        token=token, secret=SECRET, now=1000, secret_store=_store(), stream_factory=_stream
    )
    assert claims.tenant_id == "acme"
    assert ctx.safety.read_only is False
    assert ctx.creds["developer_token"] == "acme-dev"


def test_read_scope_yields_read_only_context():
    token = sign_hs256({"sub": "acme", "scope": "ads:read", "exp": 2000}, SECRET)
    ctx, _ = build_remote_context(
        token=token, secret=SECRET, now=1000, secret_store=_store(), stream_factory=_stream
    )
    assert ctx.safety.read_only is True


def test_invalid_token_rejected():
    with pytest.raises(TokenError):
        build_remote_context(
            token="bad", secret=SECRET, now=1000, secret_store=_store(), stream_factory=_stream
        )


def test_unknown_tenant_rejected():
    token = sign_hs256({"sub": "ghost", "scope": "ads:read", "exp": 2000}, SECRET)
    with pytest.raises(KeyError):
        build_remote_context(
            token=token, secret=SECRET, now=1000, secret_store=_store(), stream_factory=_stream
        )
