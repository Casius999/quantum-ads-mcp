from quantum_ads.connectors.google_ads.write.connector import register_google_ads_write
from quantum_ads.core.query.runner import StreamFn


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def _mutate_factory(creds: dict[str, object], version: str):
    def mutate(
        customer_id: str, ops: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        return {"ok": True, "validate_only": validate_only}

    return mutate


def test_write_tools_registered():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        mutate_factory=_mutate_factory,
        connectors=[register_google_ads_write],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "ads.campaign.set_status" in names
    assert "ads.budget.update" in names


def test_write_tools_marked_not_read_only():
    from quantum_ads.server import build_server

    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        mutate_factory=_mutate_factory,
        connectors=[register_google_ads_write],
    )
    assert assembled.registry.describe_tool("ads.budget.update").read_only is False
