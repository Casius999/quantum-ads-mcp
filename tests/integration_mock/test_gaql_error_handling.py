from quantum_ads.connectors.google_ads.read.gaql_tools import run_gaql


def _raising_stream(customer_id, query):  # type: ignore[no-untyped-def]
    raise RuntimeError("simulated Google Ads API error: request_id=abc123")


def test_api_error_becomes_structured_error_not_a_crash():
    out = run_gaql(
        customer_id="123",
        query="SELECT customer.id FROM customer",
        stream=_raising_stream,
    )
    assert "rows" not in out
    assert out["error"]["code"] == "RuntimeError"
    assert "request_id=abc123" in out["error"]["message"]
