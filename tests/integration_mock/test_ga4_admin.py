"""GA4 Admin API read tools: pure param builders + run wrappers against a fake ReadFn."""

from quantum_ads.connectors.ga4.read import admin_tools


def _fake_read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [{"operation": operation, "params": params}]


# --- pure builders --------------------------------------------------------------------------


def test_build_list_properties_params():
    assert admin_tools.build_list_properties_params("789") == {"account_id": "789"}


def test_build_list_data_streams_params():
    assert admin_tools.build_list_data_streams_params("123456") == {"property_id": "123456"}


def test_build_list_key_events_params():
    assert admin_tools.build_list_key_events_params("123456") == {"property_id": "123456"}


# --- run wrappers ---------------------------------------------------------------------------


def test_list_properties_dispatches_listproperties():
    out = admin_tools.list_properties(account_id="789", backend=_fake_read)
    assert out["row_count"] == 1
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "listProperties"
    assert rows[0]["params"] == {"account_id": "789"}


def test_list_data_streams_dispatches_listdatastreams():
    out = admin_tools.list_data_streams(property_id="123456", backend=_fake_read)
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "listDataStreams"


def test_list_key_events_dispatches_listkeyevents():
    out = admin_tools.list_key_events(property_id="123456", backend=_fake_read)
    rows = out["rows"]
    assert isinstance(rows, list)
    assert rows[0]["operation"] == "listKeyEvents"


# --- graceful degradation when the admin backend is absent ----------------------------------


def test_list_properties_backend_not_configured():
    out = admin_tools.list_properties(account_id="789", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_list_data_streams_backend_not_configured():
    out = admin_tools.list_data_streams(property_id="123456", backend=None)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


def test_list_key_events_backend_not_configured():
    out = admin_tools.list_key_events(property_id="123456", backend=None)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"
