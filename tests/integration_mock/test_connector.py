from quantum_ads.connectors.google_ads.read.connector import register_google_ads_read
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
    }


def _factory(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def test_connector_registers_read_tools():
    assembled = build_server(
        env=_env(), stream_factory=_factory, connectors=[register_google_ads_read]
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ads.gaql.query" in names
    assert "ads.report.campaign" in names
    assert "ads.change_history" in names
    assert "ads.fields.new_views" in names


def test_default_build_mounts_google_ads():
    assembled = build_server(env=_env(), stream_factory=_factory)
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ads.gaql.query" in names  # google_ads is in DEFAULT_CONNECTORS
