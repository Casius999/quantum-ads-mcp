from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import DEFAULT_CONNECTORS, build_server


def _env(connectors: str | None = None) -> dict[str, str]:
    env = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
    }
    if connectors is not None:
        env["QUANTUM_ADS_CONNECTORS"] = connectors
    return env


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def _connector_names(env: dict[str, str]) -> set[str]:
    assembled = build_server(env=env, stream_factory=_stream)
    return {cap.connector for cap in assembled.registry.list_capabilities()}


def test_default_mounts_all_connectors():
    names = _connector_names(_env())
    assert "core" in names
    assert {"google_ads", "ga4", "gtm", "merchant", "bigquery", "vertex"} <= names


def test_env_selection_limits_mounted_connectors():
    names = _connector_names(_env("ga4,gtm"))
    assert names == {"core", "ga4", "gtm"}
    assert "bigquery" not in names


def test_unknown_connector_name_is_ignored():
    names = _connector_names(_env("ga4, does_not_exist"))
    assert names == {"core", "ga4"}


def test_default_connectors_cover_nineteen_products():
    # google_ads contributes two registrars (read + write); 20 products -> 21 registrars.
    assert len(DEFAULT_CONNECTORS) == 21
