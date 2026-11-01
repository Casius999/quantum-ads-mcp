"""Remote transport configuration fails closed; local issuer and CLI behave."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from quantum_ads.__main__ import main
from quantum_ads.core.remote.http import (
    RemoteConfigError,
    default_audience,
    remote_config_from_env,
)
from quantum_ads.core.remote.issuer import ALGORITHM, LOCAL_ISSUER, keygen, mint_token


def _claims(token: str) -> dict[str, object]:
    header_b64, payload_b64, _ = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(header_b64 + "=="))
    assert header["alg"] == ALGORITHM
    return json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))  # type: ignore[no-any-return]


def test_http_refuses_to_start_without_token_verification():
    with pytest.raises(RemoteConfigError, match="exactly one"):
        remote_config_from_env({})


def test_http_refuses_two_verification_sources(tmp_path: Path):
    keys = keygen(tmp_path)
    env = {
        "QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE": str(keys.public_key),
        "QUANTUM_ADS_OAUTH_JWKS_URI": "https://idp.example/jwks",
    }
    with pytest.raises(RemoteConfigError, match="exactly one"):
        remote_config_from_env(env)


def test_jwks_mode_requires_an_issuer():
    with pytest.raises(RemoteConfigError, match="ISSUER"):
        remote_config_from_env({"QUANTUM_ADS_OAUTH_JWKS_URI": "https://idp.example/jwks"})


def test_path_must_be_absolute(tmp_path: Path):
    keys = keygen(tmp_path)
    env = {
        "QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE": str(keys.public_key),
        "QUANTUM_ADS_HTTP_PATH": "mcp",
    }
    with pytest.raises(RemoteConfigError, match="start with"):
        remote_config_from_env(env)


def test_local_issuer_defaults(tmp_path: Path):
    keys = keygen(tmp_path)
    config = remote_config_from_env({"QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE": str(keys.public_key)})
    assert config.issuer == LOCAL_ISSUER
    assert config.algorithm == ALGORITHM
    assert config.audience == "http://127.0.0.1:8000/mcp" == config.resource_url
    assert config.authorization_servers == ()
    assert config.tenants_file is None


def test_idp_mode_advertises_the_issuer_and_binds_audience_to_the_public_url():
    config = remote_config_from_env(
        {
            "QUANTUM_ADS_OAUTH_JWKS_URI": "https://idp.example/jwks",
            "QUANTUM_ADS_OAUTH_ISSUER": "https://idp.example",
            "QUANTUM_ADS_PUBLIC_URL": "https://ads.agency.example",
        }
    )
    assert config.algorithm == "RS256"
    assert config.authorization_servers == ("https://idp.example",)
    assert config.audience == "https://ads.agency.example/mcp"


def test_default_audience_follows_overrides():
    assert default_audience({}) == "http://127.0.0.1:8000/mcp"
    assert default_audience({"QUANTUM_ADS_OAUTH_AUDIENCE": "api://ads"}) == "api://ads"


def test_keygen_never_overwrites_a_key(tmp_path: Path):
    keygen(tmp_path)
    with pytest.raises(FileExistsError):
        keygen(tmp_path)


def test_minted_token_carries_tenant_scopes_audience_and_expiry(tmp_path: Path):
    keys = keygen(tmp_path)
    token = mint_token(
        keys.private_key,
        tenant="acme",
        scopes=["ads:read", "ads:write"],
        audience="https://ads.example/mcp",
        ttl_seconds=600,
        now=1_000,
    )
    claims = _claims(token)
    assert claims["tenant"] == "acme" and claims["sub"] == "acme"
    assert claims["scope"] == "ads:read ads:write"
    assert claims["aud"] == "https://ads.example/mcp"
    assert claims["iss"] == LOCAL_ISSUER
    assert (claims["iat"], claims["exp"]) == (1_000, 1_600)


def test_non_positive_ttl_is_refused(tmp_path: Path):
    keys = keygen(tmp_path)
    with pytest.raises(ValueError, match="ttl"):
        mint_token(keys.private_key, tenant="t", scopes=[], audience="a", ttl_seconds=0)


def test_cli_keygen_then_token(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    main(["keygen", "--dir", str(tmp_path)])
    assert "QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE=" in capsys.readouterr().out
    main(
        [
            "token",
            "--tenant",
            "acme",
            "--scope",
            "ads:read",
            "--key",
            str(tmp_path / "issuer_ed25519.pem"),
            "--audience",
            "https://ads.example/mcp",
        ]
    )
    claims = _claims(capsys.readouterr().out.strip())
    assert claims["tenant"] == "acme" and claims["aud"] == "https://ads.example/mcp"
