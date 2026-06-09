import pytest

from quantum_ads.core.remote.token import TokenError, sign_hs256, verify_hs256

SECRET = "test-secret"


def test_valid_token_extracts_tenant_and_write_scope():
    token = sign_hs256({"sub": "acme", "scope": "ads:read ads:write", "exp": 2000}, SECRET)
    claims = verify_hs256(token, SECRET, now=1000)
    assert claims.tenant_id == "acme"
    assert claims.allows_write() is True


def test_read_only_scope_disallows_write():
    token = sign_hs256({"sub": "acme", "scope": "ads:read", "exp": 2000}, SECRET)
    assert verify_hs256(token, SECRET, now=1000).allows_write() is False


def test_bad_signature_rejected():
    token = sign_hs256({"sub": "acme", "exp": 2000}, SECRET)
    with pytest.raises(TokenError):
        verify_hs256(token, "wrong-secret", now=1000)


def test_expired_token_rejected():
    token = sign_hs256({"sub": "acme", "exp": 1000}, SECRET)
    with pytest.raises(TokenError):
        verify_hs256(token, SECRET, now=1000)


def test_malformed_token_rejected():
    with pytest.raises(TokenError):
        verify_hs256("not-a-jwt", SECRET, now=1000)


def test_missing_sub_rejected():
    token = sign_hs256({"scope": "ads:read", "exp": 2000}, SECRET)
    with pytest.raises(TokenError):
        verify_hs256(token, SECRET, now=1000)
