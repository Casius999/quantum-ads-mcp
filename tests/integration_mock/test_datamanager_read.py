"""Read-plane tests for the Data Manager connector: status tool + destinations + degradation.

Uses a fake ``ReadFn`` (no SDK). Verifies the dependency-free ``status`` tool, the
``{"rows", "row_count"}`` envelope for request_status, that the right operation name + params
reach the backend, and that a missing read backend yields a structured ``BACKEND_NOT_CONFIGURED``
error instead of raising.
"""

from quantum_ads.connectors.datamanager import register_datamanager
from quantum_ads.connectors.datamanager.read import status_tools
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server


def _env() -> dict[str, str]:
    return {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "c",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
        "QUANTUM_ADS_READ_ONLY": "false",
    }


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda cid, q: []


# --- pure tool helpers (unit) -------------------------------------------------


def test_status_reports_data_manager_plane():
    out = status_tools.status()
    assert out["plane"] == "data-manager"
    assert isinstance(out["note"], str)
    assert "Data Manager" in out["note"]


def test_request_status_wraps_rows_and_passes_request_id():
    seen: dict[str, object] = {}

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        seen["operation"] = operation
        seen["params"] = params
        return [{"name": "requestStatuses/123", "state": "SUCCEEDED"}]

    out = status_tools.get_request_status(request_id="req-1", backend=read)
    assert out["rows"] == [{"name": "requestStatuses/123", "state": "SUCCEEDED"}]
    assert out["row_count"] == 1
    assert seen["operation"] == "requestStatus.retrieve"
    assert seen["params"] == {"request_id": "req-1"}


def test_request_status_degrades_when_backend_missing():
    out = status_tools.get_request_status(request_id="req-1", backend=None)
    assert isinstance(out["error"], dict)
    assert out["error"]["code"] == "BACKEND_NOT_CONFIGURED"


# --- registration / degradation (integration) ---------------------------------


def test_read_tools_register_without_backend():
    # No backends wired -> request_status degrades, but both tools still register; status works.
    assembled = build_server(
        env=_env(),
        stream_factory=_stream,
        connectors=[register_datamanager],
    )
    names = {t.name for t in assembled.registry.all_tools()}
    assert "datamanager.status" in names
    assert "datamanager.request_status" in names
