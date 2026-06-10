"""Read-side Data Manager tools: plane status + optional destinations listing.

``status`` is dependency-free — it always reports that this connector is the Data Manager upload
plane (and why: the Google Ads API upload path is blocked since 2026-06-15). ``request_status``
talks to the optional ``datamanager.read`` ReadFn backend and degrades gracefully (structured
``BACKEND_NOT_CONFIGURED`` error) when that backend is not wired.

The backend ReadFn signature is ``(operation, params) -> rows`` where operation is
``"requestStatus.retrieve"``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

# (operation, params) -> rows.
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

OP_REQUEST_STATUS = "requestStatus.retrieve"

_PLANE_NOTE = (
    "First-party data ingestion via the Google Data Manager API (Customer Match audience members "
    "+ offline/enhanced conversions). This is the SOTA upload plane: the Google Ads API upload "
    "path is blocked since 2026-06-15. Member identifiers must be SHA-256 hashed/normalized and "
    "consent (ad_user_data/ad_personalization) is required for EEA traffic (Consent Mode v2)."
)

_BACKEND_NOT_CONFIGURED: dict[str, object] = {
    "error": {"code": "BACKEND_NOT_CONFIGURED", "message": "datamanager.read not wired"}
}


def status() -> dict[str, object]:
    """Tool: report the Data Manager plane identity + operator contract (no backend needed)."""
    return {"plane": "data-manager", "note": _PLANE_NOTE}


def get_request_status(*, request_id: str, backend: object | None) -> dict[str, object]:
    """Tool: retrieve a Data Manager ingestion request's status (optional read backend)."""
    if backend is None:
        return dict(_BACKEND_NOT_CONFIGURED)
    read = cast(ReadFn, backend)
    params: dict[str, object] = {"request_id": request_id}
    rows = read(OP_REQUEST_STATUS, params)
    return {"rows": rows, "row_count": len(rows)}
