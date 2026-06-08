import pytest

from quantum_ads.core.query.gaql_validator import GaqlError
from quantum_ads.core.query.runner import run_report


def test_invalid_query_short_circuits():
    called = False

    def fake_stream(customer_id: str, query: str) -> list[dict[str, object]]:
        nonlocal called
        called = True
        return []

    with pytest.raises(GaqlError):
        run_report("123", "SELECT a FROM x WHERE segments.device='MOBILE'", stream=fake_stream)
    assert called is False


def test_valid_query_delegates_and_maps_rows():
    def fake_stream(customer_id: str, query: str) -> list[dict[str, object]]:
        return [{"campaign": {"id": 1, "name": "n"}, "metrics": {"clicks": 5}}]

    rows = run_report(
        "123",
        "SELECT campaign.id, campaign.name, metrics.clicks FROM campaign "
        "WHERE segments.date DURING LAST_7_DAYS",
        stream=fake_stream,
    )
    assert rows == [{"campaign.id": 1, "campaign.name": "n", "metrics.clicks": 5}]
