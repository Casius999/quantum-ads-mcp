"""Live boundary — smoke-gated, not unit-tested.

Real Ads Data Hub (ADH) SDK glue: lazy factories building the read callable (``customers.list`` +
``customers.analysisQueries.list`` + ``customers.analysisQueries.start`` + ``operations.get``) and
the stored-query mutate callable (``customers.analysisQueries.create``). Isolated at the untyped
third-party boundary (``googleapiclient.*`` is mypy-ignored; this module is coverage-omitted via
the live gate). Imports are local so importing this module stays cheap and credential-free; OAuth
credentials are derived from the shared Google creds dict. SDK-derived values stay implicitly typed
(``Any``).

Python package: ``google-api-python-client`` (plus ``google-auth``) — the Ads Data Hub API is
consumed through its discovery document (``adsdatahub`` v1), the same generic discovery client used
by the Search Console / SA360 connectors.

ADH enforces privacy checks (aggregation thresholds + difference checks) on the server: query runs
are asynchronous and every result is privacy-filtered and never row-level. This glue only submits /
lists / polls; it does not and cannot relax ADH's privacy layer.

Backends produced here match the connector contracts:
- ``ReadFn``  = (operation, params) -> rows.
  ``"customers.list"`` carries no params; ``"queries.list"`` carries ``{"customer_id"}``;
  ``"query.start"`` carries ``{"customer_id", "query_id", "start_date", "end_date"}`` and returns a
  single-row operation/job reference; ``"jobs.get"`` carries ``{"operation_name"}`` and returns a
  single-row job status snapshot.
- ``MutateFn`` = (account_id, operations, validate_only) -> result, where ``account_id`` is the ADH
  ``customer_id`` and each op names the ``entity`` (``"analysis_query"``). The analysis-query
  create endpoint has no native validate_only, so the preview pass returns the planned operations
  without applying.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scope for the Ads Data Hub surface (list/start/poll reads and analysis-query creation both
# ride the same scope; the read-only guard lives in the SafetyMode spine, not in the token).
_SCOPES = ["https://www.googleapis.com/auth/adsdatahub"]


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )


def _service(creds: dict[str, object], version: str) -> Any:
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds)
    return build("adsdatahub", version or "v1", credentials=credentials, cache_discovery=False)


def _date(value: str) -> dict[str, object]:
    """Split a ``YYYY-MM-DD`` literal into the google.type.Date shape ADH expects."""
    year, month, day = (int(part) for part in value.split("-"))
    return {"year": year, "month": month, "day": day}


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the ADH ReadFn dispatching customers/queries listing + query start + job poll."""
    service: Any = _service(creds, version)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "customers.list":
            response = service.customers().list().execute()
            return [dict(c) for c in response.get("customers", [])]
        if operation == "queries.list":
            parent = f"customers/{params['customer_id']}"
            response = service.customers().analysisQueries().list(parent=parent).execute()
            return [dict(q) for q in response.get("queries", [])]
        if operation == "query.start":
            name = f"customers/{params['customer_id']}/analysisQueries/{params['query_id']}"
            body: dict[str, object] = {
                "spec": {
                    "startDate": _date(str(params["start_date"])),
                    "endDate": _date(str(params["end_date"])),
                }
            }
            operation_resource = (
                service.customers().analysisQueries().start(name=name, body=body).execute()
            )
            return [dict(operation_resource)]
        if operation == "jobs.get":
            job = service.operations().get(name=str(params["operation_name"])).execute()
            return [dict(job)]
        raise ValueError(f"unsupported adh read operation: {operation!r}")

    return read


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the stored-query-create MutateFn over the ADH ``analysisQueries.create`` endpoint.

    ``validate_only`` short-circuits to a synthetic preview because the analysis-query create
    endpoint does not expose a server-side validate-only flag; the guarded preview still surfaces
    the exact op dicts that would be applied before the confirm step. Creating a query never runs
    it, so no data is read and no privacy check is triggered at create time.
    """
    service: Any = _service(creds, version)

    def _create_analysis_query(account_id: str, op: dict[str, object]) -> dict[str, object]:
        parent = f"customers/{account_id}"
        body: dict[str, object] = {
            "title": str(op["title"]),
            "queryText": str(op["query_text"]),
        }
        request = service.customers().analysisQueries().create(parent=parent, body=body)
        return dict(request.execute())

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "analysis_query": _create_analysis_query,
    }

    def mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations, "account_id": account_id}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op.get("entity")))
            if handler is None:
                raise ValueError(f"unsupported adh mutate entity: {op.get('entity')!r}")
            results.append(handler(account_id, op))
        return {"validate_only": False, "results": results}

    return mutate
