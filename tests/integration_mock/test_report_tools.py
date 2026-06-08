from quantum_ads.connectors.google_ads.read import report_tools


def test_report_campaign_builds_valid_and_maps_rows():
    captured: dict[str, str] = {}

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return [{"campaign": {"name": "X"}, "metrics": {"clicks": 3}}]

    out = report_tools.report_campaign(customer_id="123", date_range="LAST_30_DAYS", stream=stream)
    assert out["row_count"] == 1
    assert "FROM campaign" in captured["query"]
    assert "LAST_30_DAYS" in captured["query"]


def test_report_pmax_injects_channel_filter():
    captured: dict[str, str] = {}

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return []

    report_tools.report_pmax_asset_groups(customer_id="1", stream=stream)
    assert "PERFORMANCE_MAX" in captured["query"]
    assert "FROM asset_group" in captured["query"]


def test_report_ai_max_uses_matched_location_interest_view():
    captured: dict[str, str] = {}

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return []

    report_tools.report_ai_max(customer_id="1", stream=stream)
    assert "FROM matched_location_interest_view" in captured["query"]


def test_report_rejects_bad_date_range():
    out = report_tools.report_campaign(
        customer_id="1", date_range="DROP TABLE", stream=lambda c, q: []
    )
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BAD_DATE_RANGE"
