"""Tenant credentials loaded from Google Secret Manager instead of a plaintext file."""

from __future__ import annotations

import base64
import json

import pytest

from quantum_ads.core.remote.secrets import (
    SecretSourceError,
    load_tenants,
    secret_version_name,
)

_TENANTS = {"tenants": {"acme": {"GOOGLE_CLOUD_PROJECT": "acme-project"}}}
_OPERATOR = {
    "GOOGLE_OAUTH_CLIENT_ID": "cid",
    "GOOGLE_OAUTH_CLIENT_SECRET": "sec",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "rt",
    "GOOGLE_CLOUD_PROJECT": "ops-project",
}


def test_secret_names_are_normalized():
    assert secret_version_name("tenants", "p") == "projects/p/secrets/tenants/versions/latest"
    assert (
        secret_version_name("projects/x/secrets/t", "p") == "projects/x/secrets/t/versions/latest"
    )
    full = "projects/x/secrets/t/versions/3"
    assert secret_version_name(full, None) == full
    with pytest.raises(SecretSourceError, match="GOOGLE_CLOUD_PROJECT"):
        secret_version_name("tenants", None)


def test_tenants_are_read_from_the_secret_with_operator_credentials():
    calls: list[tuple[str, str]] = []

    def access(name: str, access_token: str, quota_project: str | None) -> str:
        calls.append((name, quota_project or ""))
        return json.dumps(_TENANTS)

    env = {**_OPERATOR, "QUANTUM_ADS_TENANTS_SECRET": "tenants"}
    directory = load_tenants(
        env, lambda e: {"k": e["GOOGLE_CLOUD_PROJECT"]}, access=access, token=lambda e: "at"
    )
    assert directory is not None
    assert directory.backends("acme") == {"k": "acme-project"}
    assert calls == [("projects/ops-project/secrets/tenants/versions/latest", "ops-project")]


def test_file_source_still_works(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "tenants.json"
    path.write_text(json.dumps(_TENANTS), encoding="utf-8")
    directory = load_tenants({"QUANTUM_ADS_TENANTS_FILE": str(path)}, lambda e: {})
    assert directory is not None and directory.tenants() == ["acme"]


def test_no_source_means_single_tenant():
    assert load_tenants({}, lambda e: {}) is None


def test_both_sources_are_refused(tmp_path):  # type: ignore[no-untyped-def]
    env = {"QUANTUM_ADS_TENANTS_FILE": "x.json", "QUANTUM_ADS_TENANTS_SECRET": "t"}
    with pytest.raises(SecretSourceError, match="one of"):
        load_tenants(env, lambda e: {})


def test_secret_with_invalid_json_is_refused():
    env = {**_OPERATOR, "QUANTUM_ADS_TENANTS_SECRET": "tenants"}
    with pytest.raises(ValueError, match="tenants"):
        load_tenants(env, lambda e: {}, access=lambda *a: "[]", token=lambda e: "at")


def test_secret_payload_decoding():
    from quantum_ads.core.remote.secrets import decode_payload

    encoded = base64.b64encode(b'{"tenants": {}}').decode()
    assert decode_payload({"payload": {"data": encoded}}) == '{"tenants": {}}'
    with pytest.raises(SecretSourceError, match="payload"):
        decode_payload({})
