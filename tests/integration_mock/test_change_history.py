from quantum_ads.connectors.google_ads.read.change_history import change_history


def test_audit_builds_change_event_query():
    captured: dict[str, str] = {}

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return []

    change_history(customer_id="1", mode="audit", stream=stream)
    assert "FROM change_event" in captured["query"]
    assert "LIMIT" in captured["query"]


def test_delta_builds_change_status_query():
    captured: dict[str, str] = {}

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return []

    change_history(customer_id="1", mode="delta", stream=stream)
    assert "FROM change_status" in captured["query"]


def test_limit_capped_at_10000():
    captured: dict[str, str] = {}

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured["query"] = query
        return []

    change_history(customer_id="1", mode="audit", limit=999999, stream=stream)
    assert "LIMIT 10000" in captured["query"]


def test_unknown_mode_returns_error():
    out = change_history(customer_id="1", mode="weird", stream=lambda c, q: [])
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "UNKNOWN_MODE"
