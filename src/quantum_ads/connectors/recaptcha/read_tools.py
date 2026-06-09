"""Raw reCAPTCHA Enterprise read execution + result wrapping for the read connector.

Each tool calls the injected ``ReadFn`` with an operation name and a params dict, then wraps the
rows in the shared ``{"rows", "row_count"}`` envelope, matching the other read connectors.

The two operations:

* ``list_keys`` — enumerate the reCAPTCHA site keys configured under a project (so the caller can
  discover which key guards which surface).
* ``create_assessment`` — the core lead-quality signal: score a user-response token and return the
  risk score in ``[0.0, 1.0]`` (1.0 = very likely legitimate) plus reason codes. The score is
  surfaced as a top-level ``risk_score`` for convenience, derived from the backend's first row.
"""

from __future__ import annotations

from .builders import build_assessment_request
from .types import ReadFn

# Operation names passed as the first ReadFn argument.
OP_KEYS_LIST = "keys.list"
OP_ASSESSMENT_CREATE = "assessment.create"


def _wrap(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap rows in the shared read envelope."""
    return {"rows": rows, "row_count": len(rows)}


def list_keys(*, project_id: str, read: ReadFn) -> dict[str, object]:
    """Tool: list the reCAPTCHA site keys configured under a project."""
    params: dict[str, object] = {"project_id": project_id}
    return _wrap(read(OP_KEYS_LIST, params))


def create_assessment(
    *, project_id: str, site_key: str, token: str, expected_action: str, read: ReadFn
) -> dict[str, object]:
    """Tool: create an assessment for a token — the core lead-quality / fraud signal.

    Returns the standard ``{"rows", "row_count"}`` envelope plus a top-level ``risk_score`` (the
    backend's ``score`` for the first row, defaulting to ``0.0`` when absent) so a caller can
    threshold lead quality without digging into the row payload.
    """
    params = build_assessment_request(
        project_id=project_id,
        site_key=site_key,
        token=token,
        expected_action=expected_action,
    )
    rows = read(OP_ASSESSMENT_CREATE, params)
    out = _wrap(rows)
    out["risk_score"] = _risk_score(rows)
    return out


def _risk_score(rows: list[dict[str, object]]) -> float:
    """Pull ``score`` from the first assessment row; 0.0 if absent/malformed."""
    if not rows:
        return 0.0
    raw = rows[0].get("score", 0.0)
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
