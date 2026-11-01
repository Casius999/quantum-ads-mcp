"""Live: the HTTP server's tenant map read from Google Secret Manager.

Needs the operator OAuth credential (cloud-platform scope) and a secret holding a tenant map;
set QUANTUM_ADS_LIVE_TENANTS_SECRET (default: quantum-ads-tenants-smoke, a synthetic map with
one tenant "smoke" and no real credentials).
"""

from __future__ import annotations

import os

import pytest

from quantum_ads.core.remote.secrets import load_tenants

pytestmark = pytest.mark.live


def test_tenants_load_from_secret_manager_live() -> None:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        pytest.skip("GOOGLE_CLOUD_PROJECT not set")
    secret = os.environ.get("QUANTUM_ADS_LIVE_TENANTS_SECRET", "quantum-ads-tenants-smoke")
    env = {**os.environ, "QUANTUM_ADS_TENANTS_SECRET": secret}
    env.pop("QUANTUM_ADS_TENANTS_FILE", None)
    directory = load_tenants(
        env, lambda tenant_env: {"project": tenant_env["GOOGLE_CLOUD_PROJECT"]}
    )
    assert directory is not None
    assert directory.tenants()
    first = directory.tenants()[0]
    assert "project" in directory.backends(first)
