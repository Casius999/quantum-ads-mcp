"""Live boundary — smoke-gated, not unit-tested.

Real Search Ads 360 SDK glue: lazy factories building the read callable (``searchAds360:search`` +
``customers:listAccessible`` on the new ``searchads360`` v0 Reporting API) and the conversion-upload
mutate callable (``conversion.insert`` on the ``doubleclicksearch`` v2 API — the Reporting API is
read-only and exposes no conversion ingest). Isolated at the untyped
third-party boundary (``googleapiclient.*`` is mypy-ignored; this module is coverage-omitted via
the live gate). Imports are local so importing this module stays cheap and credential-free; OAuth
credentials are derived from the shared Google creds dict. SDK-derived values stay implicitly
typed (``Any``).

Python package: ``google-api-python-client`` (plus ``google-auth``) — the new Search Ads 360
Reporting API is consumed through its discovery document (``searchads360`` v0), the same generic
discovery client used by the Search Console / Data Manager connectors. (The alternative
hand-written ``google-ads-searchads360`` gRPC client is *not* used here, to keep one consistent
discovery-client boundary across connectors.)

Backends produced here match the connector contracts:
- ``ReadFn``  = (operation, params) -> rows. ``"search"`` carries ``{"customer_id", "query"}``;
  ``"customers.listAccessible"`` carries no params.
- ``MutateFn`` = (account_id, operations, validate_only) -> result, where ``account_id`` is the
  SA360 ``customer_id`` and each op names the ``action``. The Reporting API conversion ingest has
  no native validate_only, so the preview pass returns the planned operations without applying.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scopes: read-only covers search + listAccessible; the full scope is required to ingest
# conversions on the mutate plane.
_READONLY_SCOPES = ["https://www.googleapis.com/auth/doubleclicksearch"]
_WRITE_SCOPES = ["https://www.googleapis.com/auth/doubleclicksearch"]


def _oauth_credentials(creds: dict[str, object], scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials

    quota = creds.get("quota_project_id")
    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=scopes,
        quota_project_id=str(quota) if quota else None,
    )


def _service(creds: dict[str, object], api: str, version: str, scopes: list[str]) -> Any:
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds, scopes)
    return build(api, version, credentials=credentials, cache_discovery=False)


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the SA360 ReadFn dispatching ``search`` + ``customers.listAccessible``."""
    service: Any = _service(creds, "searchads360", version or "v0", _READONLY_SCOPES)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "search":
            customer_id = str(params["customer_id"])
            body = {"query": str(params["query"])}
            response = (
                service.customers()
                .searchAds360()
                .search(customerId=customer_id, body=body)
                .execute()
            )
            return [dict(row) for row in response.get("results", [])]
        if operation == "customers.listAccessible":
            response = service.customers().listAccessibleCustomers().execute()
            names = response.get("resourceNames", [])
            return [{"resourceName": name} for name in names]
        raise ValueError(f"unsupported sa360 read operation: {operation!r}")

    return read


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the conversion-upload MutateFn over the SA360 ``conversions:ingest`` endpoint.

    ``validate_only`` short-circuits to a synthetic preview because the conversion ingest endpoint
    does not expose a server-side validate-only flag; the guarded preview still surfaces the exact
    op dicts that would be applied before the confirm step.
    """
    # Conversions ingest is NOT on the searchads360 v0 reporting API (read-only); it lives on the
    # Search Ads 360 doubleclicksearch v2 API as conversion.insert.
    service: Any = _service(creds, "doubleclicksearch", "v2", _WRITE_SCOPES)

    def _upload_conversions(account_id: str, op: dict[str, object]) -> dict[str, object]:
        body: dict[str, object] = {
            "kind": "doubleclicksearch#conversionList",
            "conversion": op["conversions"],
        }
        request = service.conversion().insert(body=body)
        return dict(request.execute())

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "upload_conversions": _upload_conversions,
    }

    def mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations, "account_id": account_id}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("action")))
            if handler is None:
                raise ValueError(f"unsupported sa360 mutate action: {op.get('action')!r}")
            results.append(handler(account_id, op))
        return {"validate_only": False, "results": results}

    return mutate
