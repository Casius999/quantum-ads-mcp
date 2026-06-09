"""Real Display & Video 360 (Display Video API v4) SDK glue: read + mutate factories.

Live boundary — smoke-gated, not unit-tested.

Isolated at the untyped third-party boundary (``googleapiclient.*`` / ``google.oauth2.*`` are in
the mypy ``ignore_missing_imports`` list, so ``build(...)`` yields ``Any`` and the dynamic
resource objects are threaded as ``Any`` here). Imports are local so importing this module stays
cheap and credential-free.

Backends produced here match the connector contracts:
- ``ReadFn``  = (operation, params) -> rows   (operation names the DV360 resource; params carry
  the parent id, e.g. {"partner_id": "123"} or {"advertiser_id": "456"}).
- ``MutateFn`` = (advertiser_id, operations, validate_only) -> result   where advertiser_id is the
  parent advertiser and each op dict names the resource + action. The Display Video API has no
  native validate_only, so the preview pass returns the planned operations without applying.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scope for full Display & Video 360 management (read + edit line items).
DISPLAY_VIDEO_SCOPE = "https://www.googleapis.com/auth/display-video"


def _build_service(creds: dict[str, object], version: str) -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=str(creds.get("refresh_token")),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=str(creds.get("client_id")),
        client_secret=str(creds.get("client_secret")),
        scopes=[DISPLAY_VIDEO_SCOPE],
    )
    return build("displayvideo", version or "v4", credentials=credentials, cache_discovery=False)


def _rows(response: dict[str, object], key: str) -> list[dict[str, object]]:
    items = response.get(key, [])
    return [dict(item) for item in items]  # type: ignore[arg-type]


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    service: Any = _build_service(creds, version)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "advertisers.list":
            partner_id = str(params.get("partner_id", ""))
            response = service.advertisers().list(partnerId=partner_id).execute()
            return _rows(response, "advertisers")
        advertiser_id = str(params.get("advertiser_id", ""))
        if operation == "campaigns.list":
            response = service.advertisers().campaigns().list(advertiserId=advertiser_id).execute()
            return _rows(response, "campaigns")
        if operation == "insertionOrders.list":
            insertion_orders = service.advertisers().insertionOrders()
            response = insertion_orders.list(advertiserId=advertiser_id).execute()
            return _rows(response, "insertionOrders")
        if operation == "lineItems.list":
            response = service.advertisers().lineItems().list(advertiserId=advertiser_id).execute()
            return _rows(response, "lineItems")
        raise ValueError(f"unsupported dv360 read operation: {operation!r}")

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    service: Any = _build_service(creds, version)

    def _update_line_item(advertiser_id: str, op: dict[str, object]) -> dict[str, object]:
        fields = dict(op.get("fields", {}))
        update_mask = ",".join(sorted(fields.keys()))
        request = (
            service.advertisers()
            .lineItems()
            .patch(
                advertiserId=advertiser_id,
                lineItemId=str(op["line_item_id"]),
                updateMask=update_mask,
                body=fields,
            )
        )
        return dict(request.execute())

    def _set_line_item_status(advertiser_id: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {"entityStatus": op["entity_status"]}
        request = (
            service.advertisers()
            .lineItems()
            .patch(
                advertiserId=advertiser_id,
                lineItemId=str(op["line_item_id"]),
                updateMask="entityStatus",
                body=body,
            )
        )
        return dict(request.execute())

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "update_line_item": _update_line_item,
        "set_line_item_status": _set_line_item_status,
    }

    def mutate(
        advertiser_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            # Display Video API has no native validate_only; preview without applying.
            return {
                "validate_only": True,
                "operations": operations,
                "advertiser_id": advertiser_id,
            }
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("action")))
            if handler is None:
                raise ValueError(f"unsupported dv360 mutate action: {op.get('action')!r}")
            results.append(handler(advertiser_id, op))
        return {"validate_only": False, "results": results}

    return mutate
