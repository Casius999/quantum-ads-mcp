"""Live boundary — smoke-gated, not unit-tested.

Real Search Console SDK glue: lazy factories building the read callable (searchAnalytics.query,
sites.list, sitemaps.list, urlInspection.index.inspect) and the sitemap mutate callable
(sitemaps.submit / sitemaps.delete). Isolated at the untyped third-party boundary
(``googleapiclient.*`` is mypy-ignored; this module is coverage-omitted via the live gate).
Imports are local so importing this module stays cheap and credential-free; OAuth credentials are
derived from the shared Google creds dict. SDK-derived values stay implicitly typed (``Any``).

Two discovery surfaces, both via ``googleapiclient.discovery.build``:
  - ``webmasters`` v3 — sites / sitemaps / searchanalytics
  - ``searchconsole`` v1 — urlInspection.index.inspect (URL Inspection API)

Python package: ``google-api-python-client`` (plus ``google-auth``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# Read-only scope covers searchanalytics + sites + sitemaps reads + URL inspection; the full
# scope is required to submit/delete sitemaps on the mutate plane.
_READONLY_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_WRITE_SCOPES = ["https://www.googleapis.com/auth/webmasters"]


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


def read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Search Console ReadFn dispatching the four read operations."""
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds, _READONLY_SCOPES)
    webmasters = build("webmasters", "v3", credentials=credentials, cache_discovery=False)
    inspection = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "searchAnalytics.query":
            body = {
                "startDate": str(params["start_date"]),
                "endDate": str(params["end_date"]),
                "dimensions": list(params["dimensions"]),  # type: ignore[arg-type]
                "rowLimit": int(params["row_limit"]),  # type: ignore[arg-type]
            }
            response = (
                webmasters.searchanalytics()
                .query(siteUrl=str(params["site_url"]), body=body)
                .execute()
            )
            return [dict(row) for row in response.get("rows", [])]
        if operation == "sites.list":
            response = webmasters.sites().list().execute()
            return [dict(entry) for entry in response.get("siteEntry", [])]
        if operation == "sitemaps.list":
            response = webmasters.sitemaps().list(siteUrl=str(params["site_url"])).execute()
            return [dict(entry) for entry in response.get("sitemap", [])]
        if operation == "urlInspection.inspect":
            body = {
                "inspectionUrl": str(params["inspection_url"]),
                "siteUrl": str(params["site_url"]),
            }
            response = inspection.urlInspection().index().inspect(body=body).execute()
            return [dict(response)]
        raise ValueError(f"unsupported searchconsole read operation: {operation!r}")

    return read


def mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build the sitemap MutateFn over the webmasters sitemaps endpoint.

    ``validate_only`` short-circuits to a synthetic preview because the sitemaps endpoints do not
    expose a server-side validate-only flag; the guarded preview still surfaces the exact op dicts
    that would be applied before the confirm step. The submit/delete calls return no body, so a
    structured ``{"submitted"/"deleted": feedpath}`` acknowledgement is returned instead.
    """
    from googleapiclient.discovery import build

    credentials = _oauth_credentials(creds, _WRITE_SCOPES)
    webmasters = build("webmasters", "v3", credentials=credentials, cache_discovery=False)

    def _submit(site_url: str, op: dict[str, object]) -> dict[str, object]:
        feedpath = str(op["feedpath"])
        webmasters.sitemaps().submit(siteUrl=site_url, feedpath=feedpath).execute()
        return {"submitted": feedpath, "site_url": site_url}

    def _delete(site_url: str, op: dict[str, object]) -> dict[str, object]:
        feedpath = str(op["feedpath"])
        webmasters.sitemaps().delete(siteUrl=site_url, feedpath=feedpath).execute()
        return {"deleted": feedpath, "site_url": site_url}

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "submit": _submit,
        "delete": _delete,
    }

    def mutate(
        customer_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results = []
        for op in operations:
            handler = handlers.get(str(op["action"]))
            if handler is None:
                raise ValueError(f"unsupported searchconsole mutate action: {op.get('action')!r}")
            results.append(handler(customer_id, op))
        return {"validate_only": False, "results": results}

    return mutate
