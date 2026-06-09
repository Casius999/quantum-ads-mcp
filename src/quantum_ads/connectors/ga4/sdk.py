"""Live boundary — smoke-gated, not unit-tested.

Real GA4 SDK glue: lazy factories building the Data API read callable, the Admin API read
callable, and the Admin API mutate callable. Isolated at the untyped third-party boundary
(``google.analytics.*`` is mypy-ignored; this module is coverage-omitted via the live gate).
Imports are local so importing this module stays cheap and credential-free; the OAuth
credentials are derived from the shared Google creds dict. SDK-derived values stay implicitly
typed (``Any``) — they are never annotated, mirroring the Google Ads SDK boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scopes for the two GA4 surfaces (read-only data; admin edit for the guarded mutate plane).
_DATA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
_ADMIN_READ_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
_ADMIN_EDIT_SCOPES = ["https://www.googleapis.com/auth/analytics.edit"]


def _oauth_credentials(creds: dict[str, object], scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials

    quota_project = creds.get("quota_project_id")
    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes,
        quota_project_id=str(quota_project) if quota_project else None,
    )


def _property_path(property_id: str) -> str:
    return property_id if property_id.startswith("properties/") else f"properties/{property_id}"


def data_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Data API ReadFn dispatching runReport / runRealtimeReport."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunRealtimeReportRequest,
        RunReportRequest,
    )
    from google.protobuf.json_format import MessageToDict

    client = BetaAnalyticsDataClient(credentials=_oauth_credentials(creds, _DATA_SCOPES))

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        prop = _property_path(str(params["property_id"]))
        dim_names = cast(Sequence[object], params["dimensions"])
        metric_names = cast(Sequence[object], params["metrics"])
        dimensions = [Dimension(name=str(d)) for d in dim_names]
        metrics = [Metric(name=str(m)) for m in metric_names]
        if operation == "runReport":
            request = RunReportRequest(
                property=prop,
                dimensions=dimensions,
                metrics=metrics,
                date_ranges=[
                    DateRange(
                        start_date=str(params["start_date"]),
                        end_date=str(params["end_date"]),
                    )
                ],
            )
            response = client.run_report(request)
        elif operation == "runRealtimeReport":
            request = RunRealtimeReportRequest(
                property=prop, dimensions=dimensions, metrics=metrics
            )
            response = client.run_realtime_report(request)
        else:
            raise ValueError(f"unsupported ga4.data operation: {operation!r}")
        payload = MessageToDict(response._pb)
        rows = payload.get("rows", [])
        return [dict(row) for row in rows]

    return read


def admin_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Admin API ReadFn dispatching listProperties / listDataStreams / listKeyEvents."""
    from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
    from google.protobuf.json_format import MessageToDict

    client = AnalyticsAdminServiceClient(credentials=_oauth_credentials(creds, _ADMIN_READ_SCOPES))

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "listProperties":
            from google.analytics.admin_v1beta.types import ListPropertiesRequest

            account = str(params["account_id"])
            account = account if account.startswith("accounts/") else f"accounts/{account}"
            items = client.list_properties(
                request=ListPropertiesRequest(filter=f"parent:{account}")
            )
        elif operation == "listDataStreams":
            items = client.list_data_streams(parent=_property_path(str(params["property_id"])))
        elif operation == "listKeyEvents":
            items = client.list_key_events(parent=_property_path(str(params["property_id"])))
        else:
            raise ValueError(f"unsupported ga4.admin operation: {operation!r}")
        return [MessageToDict(item._pb) for item in items]

    return read


def admin_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the Admin API MutateFn handling create key event / create audience (entity dicts)."""
    from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
    from google.protobuf.json_format import MessageToDict

    client = AnalyticsAdminServiceClient(credentials=_oauth_credentials(creds, _ADMIN_EDIT_SCOPES))

    def _create_key_event(op: dict[str, object], validate_only: bool) -> dict[str, object]:
        parent = _property_path(str(op["property_id"]))
        if validate_only:
            return {"validate_only": True, "parent": parent, "event_name": str(op["event_name"])}
        from google.analytics.admin_v1beta import KeyEvent

        key_event = KeyEvent(event_name=str(op["event_name"]))
        response = client.create_key_event(parent=parent, key_event=key_event)
        result: dict[str, object] = MessageToDict(response._pb)
        return result

    def _create_audience(op: dict[str, object], validate_only: bool) -> dict[str, object]:
        parent = _property_path(str(op["property_id"]))
        if validate_only:
            return {
                "validate_only": True,
                "parent": parent,
                "display_name": str(op["display_name"]),
            }
        clauses = cast(Sequence[object], op["filter_clauses"])
        audience = Audience(
            display_name=str(op["display_name"]),
            filter_clauses=list(clauses),
        )
        response = client.create_audience(parent=parent, audience=audience)
        result: dict[str, object] = MessageToDict(response._pb)
        return result

    handlers: dict[str, Callable[[dict[str, object], bool], dict[str, object]]] = {
        "key_event": _create_key_event,
        "audience": _create_audience,
    }

    def mutate(
        property_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op["entity"]))
            if handler is None:
                raise ValueError(f"unsupported ga4 mutate entity: {op.get('entity')!r}")
            results.append(handler(op, validate_only))
        return {"validate_only": validate_only, "results": results}

    return mutate
