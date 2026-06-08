from quantum_ads.connectors.google_ads.read.gaql_tools import run_gaql


def test_run_gaql_returns_rows():
    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        return [{"campaign": {"id": 7}}]

    out = run_gaql(
        customer_id="123-456-7890",
        query="SELECT campaign.id FROM campaign WHERE segments.date DURING LAST_7_DAYS",
        stream=stream,
    )
    assert out["rows"] == [{"campaign.id": 7}]
    assert out["row_count"] == 1


def test_run_gaql_invalid_returns_error_payload():
    out = run_gaql(
        customer_id="123",
        query="SELECT a FROM x WHERE segments.device='MOBILE'",
        stream=lambda c, q: [],
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "GAQL_INVALID"
