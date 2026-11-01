"""Backend wiring for the stdio entrypoint: complete, environment-driven, and lazy."""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from quantum_ads import backends
from quantum_ads.backends import BACKENDS, LazyBackend, build_backends

_CONNECTORS = Path(backends.__file__).parent / "connectors"
# Backend keys are declared as string constants ("ga4.data") or passed literally to ctx.backend().
_KEY = re.compile(r'(?:BACKEND[A-Z_]*\s*=\s*|ctx\.backend\()"([a-z0-9_]+(?:\.[a-z0-9_]+)+)"')

_ADS_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "cid",
    "GOOGLE_ADS_CLIENT_SECRET": "sec",
    "GOOGLE_ADS_REFRESH_TOKEN": "rt",
}


def _keys_used_by_connectors() -> set[str]:
    return {
        match.group(1)
        for path in _CONNECTORS.rglob("*.py")
        if path.name != "sdk.py"
        for match in _KEY.finditer(path.read_text(encoding="utf-8"))
    }


def test_every_backend_a_connector_reads_is_wired():
    used = _keys_used_by_connectors()
    assert len(used) >= 30, sorted(used)  # guard: the scan itself must find the keys
    assert used == set(BACKENDS), {
        "unwired": sorted(used - set(BACKENDS)),
        "unused": sorted(set(BACKENDS) - used),
    }


@pytest.mark.parametrize("key", sorted(BACKENDS))
def test_every_mapped_factory_exists(key: str) -> None:
    spec = BACKENDS[key]
    sdk = importlib.import_module(f"quantum_ads.connectors.{spec.module}.sdk")
    assert callable(getattr(sdk, spec.factory)), f"{key}: {spec.module}.sdk.{spec.factory}"


def test_ads_oauth_alone_wires_oauth_backends_but_not_project_or_looker_ones():
    wired = build_backends(_ADS_ENV)
    assert {"ga4.data", "gtm.api", "youtube.data", "dv360.api", "trends.api"} <= set(wired)
    assert not {"bigquery.api", "vertex.api", "language.api", "recaptcha.api"} & set(wired)
    assert not {"looker.api", "looker.mutate"} & set(wired)


def test_cloud_project_unlocks_gcp_backends_and_dedicated_oauth_wins():
    env = {
        **_ADS_ENV,
        "GOOGLE_OAUTH_CLIENT_ID": "oauth-cid",
        "GOOGLE_OAUTH_CLIENT_SECRET": "oauth-sec",
        "GOOGLE_OAUTH_REFRESH_TOKEN": "oauth-rt",
        "GOOGLE_CLOUD_PROJECT": "proj",
        "GOOGLE_VERTEX_LOCATION": "global",
    }
    wired = build_backends(env)
    assert {"bigquery.api", "vertex.api", "language.api", "recaptcha.mutate"} <= set(wired)
    vertex = wired["vertex.api"]
    assert isinstance(vertex, LazyBackend)
    creds = vertex._creds
    assert creds["client_id"] == "oauth-cid" and creds["refresh_token"] == "oauth-rt"
    assert creds["project"] == creds["project_id"] == creds["quota_project_id"] == "proj"
    assert creds["location"] == "global"


def test_looker_needs_its_own_api3_credentials():
    env = {
        "LOOKERSDK_BASE_URL": "https://x",
        "LOOKERSDK_CLIENT_ID": "i",
        "LOOKERSDK_CLIENT_SECRET": "s",
    }
    wired = build_backends(env)
    assert {"looker.api", "looker.mutate", "trends.api", "meridian.api"} == set(wired)


def test_no_credentials_only_wires_credential_free_backends():
    assert set(build_backends({})) == {"trends.api", "meridian.api"}


def test_backend_is_built_on_first_call_then_reused(monkeypatch):
    calls: list[tuple[dict[str, object], str]] = []

    def fake_factory(creds: dict[str, object], version: str):  # type: ignore[no-untyped-def]
        calls.append((creds, version))
        return lambda op, params: [{"op": op}]

    sdk = importlib.import_module("quantum_ads.connectors.trends.sdk")
    monkeypatch.setattr(sdk, "read_factory", fake_factory)
    lazy = build_backends({})["trends.api"]
    assert calls == []  # nothing built at wiring time
    assert lazy("interest_over_time", {}) == [{"op": "interest_over_time"}]
    assert lazy("interest_over_time", {}) == [{"op": "interest_over_time"}]
    assert len(calls) == 1  # built once, reused


def test_missing_sdk_raises_with_install_hint(monkeypatch):
    def factory_needing_absent_sdk(creds: dict[str, object], version: str):  # type: ignore[no-untyped-def]
        raise ModuleNotFoundError("No module named 'pytrends'", name="pytrends")

    sdk = importlib.import_module("quantum_ads.connectors.trends.sdk")
    monkeypatch.setattr(sdk, "read_factory", factory_needing_absent_sdk)
    lazy = build_backends({})["trends.api"]
    with pytest.raises(
        RuntimeError, match=r"trends\.api: missing SDK \(pytrends\).*--extra connectors"
    ):
        lazy("interest_over_time", {})
