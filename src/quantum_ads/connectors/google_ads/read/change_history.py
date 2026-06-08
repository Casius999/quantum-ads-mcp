"""Change history: change_event (field-level audit, 30d) and change_status (delta sync, 90d)."""

from __future__ import annotations

from ....core.query.runner import StreamFn
from .gaql_tools import ALLOWED_DATE_RANGES, execute_query

_MAX_LIMIT = 10_000

_AUDIT_FIELDS = (
    "change_event.change_date_time, change_event.user_email, change_event.client_type, "
    "change_event.change_resource_type, change_event.change_resource_name, "
    "change_event.resource_change_operation"
)
_DELTA_FIELDS = (
    "change_status.resource_name, change_status.resource_type, "
    "change_status.resource_status, change_status.last_change_date_time"
)


def change_history(
    *,
    customer_id: str,
    mode: str = "audit",
    date_range: str = "LAST_7_DAYS",
    limit: int = _MAX_LIMIT,
    stream: StreamFn,
) -> dict[str, object]:
    if date_range not in ALLOWED_DATE_RANGES:
        return {
            "error": {"code": "BAD_DATE_RANGE", "message": f"unsupported date_range {date_range!r}"}
        }
    capped = min(int(limit), _MAX_LIMIT)
    if mode == "audit":
        query = (
            f"SELECT {_AUDIT_FIELDS} FROM change_event "
            f"WHERE change_event.change_date_time DURING {date_range} "
            f"ORDER BY change_event.change_date_time DESC LIMIT {capped}"
        )
    elif mode == "delta":
        query = (
            f"SELECT {_DELTA_FIELDS} FROM change_status "
            f"WHERE change_status.last_change_date_time DURING {date_range} "
            f"ORDER BY change_status.last_change_date_time ASC LIMIT {capped}"
        )
    else:
        return {
            "error": {
                "code": "UNKNOWN_MODE",
                "message": f"mode must be 'audit' or 'delta', got {mode!r}",
            }
        }
    return execute_query(customer_id, query, stream)
