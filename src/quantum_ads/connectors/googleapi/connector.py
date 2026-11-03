"""Generic Google API plane: any method of any marketing Google API, contract-checked and guarded.

The curated connectors cover the common paths; this one reaches everything else, the way
``ads.mutate`` does for Google Ads. Each call is validated offline against the API's Discovery
document, then reads run directly and writes go through the shared ``WriteExecutor``
(read-only guard, policy, preview with the API's own ``validateOnly`` where it exists, confirm or
auto commit, signed audit with an inverse call for rollback). Deletes need ``allow_delete``.
"""

from __future__ import annotations

import difflib
import functools
import re
from collections.abc import Callable
from typing import Any, cast

from fastmcp import FastMCP

from ...core.context import ServerContext
from ...core.mcp.register import add_tool
from ...core.registry.registry import Capability, ToolSpec
from ...core.safety.reversal import reversible, rollback_op
from ...core.safety.write_executor import MutateFn, WriteExecutor
from ...core.tenancy import current_principal
from .discovery import InvalidCall, all_methods, describe, find_method, schema_fields, validate_call

BACKEND_READ = "google.api"
BACKEND_MUTATE = "google.api.mutate"
CALL_OP = "google.api.call"
# Marketing APIs reachable through the generic plane, with the default version.
APIS: dict[str, str] = {
    "analyticsadmin": "v1beta",
    "analyticsdata": "v1beta",
    "tagmanager": "v2",
    "merchantapi": "products_v1",
    "content": "v2.1",
    "youtube": "v3",
    "youtubeAnalytics": "v2",
    "youtubereporting": "v1",
    "displayvideo": "v4",
    "dfareporting": "v4",
    "searchads360": "v0",
    "mybusinessbusinessinformation": "v1",
    "mybusinessaccountmanagement": "v1",
    "businessprofileperformance": "v1",
    "searchconsole": "v1",
    "sheets": "v4",
    "drive": "v3",
    "slides": "v1",
    "docs": "v1",
    "bigquery": "v2",
    "adsdatahub": "v1",
    "datamanager": "v1",
    "recaptchaenterprise": "v1",
    "language": "v2",
    "translate": "v3",
}
# Routed to the curated, cost-guarded tools instead.
DENIED = {
    "bigquery.jobs.insert": "use bigquery.query (dry-run cost guard)",
    "bigquery.jobs.query": "use bigquery.query (dry-run cost guard)",
}
ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]


def _error(code: str, message: str) -> dict[str, object]:
    return {"applied": False, "error": {"code": code, "message": message}}


def register_google_api(app: FastMCP, ctx: ServerContext) -> None:
    documents: dict[tuple[str, str], dict[str, Any]] = {}

    def target(api: str, version: str | None) -> tuple[str, str]:
        if api not in APIS:
            squashed = re.sub(r"[^a-z0-9]", "", api.lower()).removeprefix("google")
            by_key = {re.sub(r"[^a-z0-9]", "", a.lower()): a for a in APIS}
            guess = by_key.get(squashed) or next(
                iter(difflib.get_close_matches(squashed, list(by_key), n=1, cutoff=0.6)), None
            )
            hint = f"; did you mean {by_key.get(guess, guess)!r}?" if guess else ""
            raise InvalidCall(f"api {api!r} is not exposed{hint} Available: {sorted(APIS)}")
        return api, version or APIS[api]

    def document(api: str, version: str) -> dict[str, Any]:
        if (api, version) not in documents:
            backend = ctx.backend(BACKEND_READ)
            if backend is None:
                raise LookupError(f"{BACKEND_READ} not wired")
            rows = cast(ReadFn, backend)("discovery", {"api": api, "version": version})
            documents[(api, version)] = dict(rows[0])
        return documents[(api, version)]

    def guarded(fn: Callable[..., dict[str, object]]) -> Callable[..., dict[str, object]]:
        """Map contract and wiring failures to structured errors (keeps each tool flat)."""

        @functools.wraps(fn)
        def run(*args: Any, **kwargs: Any) -> dict[str, object]:
            try:
                return fn(*args, **kwargs)
            except InvalidCall as exc:
                return _error("INVALID_CALL", str(exc))
            except LookupError as exc:
                return _error("BACKEND_NOT_CONFIGURED", str(exc))
            except Exception as exc:  # noqa: BLE001 - the Google API's own refusal, kept verbatim
                return _error("API_ERROR", str(exc)[:1000])

        return run

    def google_api_list() -> dict[str, object]:
        return {"apis": [{"api": a, "default_version": v} for a, v in sorted(APIS.items())]}

    @guarded
    def google_api_methods(
        api: str, version: str | None = None, resource: str | None = None, writes_only: bool = False
    ) -> dict[str, object]:
        api, version = target(api, version)
        doc = document(api, version)
        prefix = f"{api}.{resource}." if resource else ""
        methods = [
            describe(m)
            for m in all_methods(doc)
            if m.id.startswith(prefix) and (m.is_write or not writes_only)
        ]
        return {"api": api, "version": version, "count": len(methods), "methods": methods}

    @guarded
    def google_api_describe(api: str, method: str, version: str | None = None) -> dict[str, object]:
        api, version = target(api, version)
        doc = document(api, version)
        found = find_method(doc, method)
        parameters = {
            name: {
                k: spec[k]
                for k in ("location", "type", "required", "pattern", "enum", "repeated")
                if k in spec
            }
            for name, spec in found.parameters.items()
        }
        return {
            **describe(found, summary_chars=600),
            "path": found.path,
            "parameters": parameters,
            "request": found.request_ref,
            "request_fields": schema_fields(doc, found.request_ref),
            "scopes": list(found.scopes),
        }

    @guarded
    def google_api_read(
        api: str, method: str, params: dict[str, Any] | None = None, version: str | None = None
    ) -> dict[str, object]:
        api, version = target(api, version)
        found = validate_call(document(api, version), method, params)
        if found.id in DENIED:
            raise InvalidCall(f"{found.id} is not available here: {DENIED[found.id]}")
        if found.is_write:
            raise InvalidCall(f"{found.id} writes ({found.http_method}); use google.api.call")
        backend = cast(ReadFn, ctx.backend(BACKEND_READ))
        rows = backend(
            "execute", {"api": api, "version": version, "method": found.id, "params": params or {}}
        )
        return {"method": found.id, "response": rows[0]}

    def run(
        op: str, api: str, version: str, operations: list[dict[str, object]], confirm: str | None
    ) -> dict[str, object]:
        backend = ctx.backend(BACKEND_MUTATE)
        if backend is None:
            raise LookupError(f"{BACKEND_MUTATE} not wired")
        executor = WriteExecutor(cast(MutateFn, backend), ctx.safety, ctx.audit)
        return executor.execute(
            op=op, customer_id=f"{api}/{version}", operations=operations, confirm=confirm
        )

    @guarded
    def google_api_call(
        api: str,
        method: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        version: str | None = None,
        allow_delete: bool = False,
        confirm: str | None = None,
    ) -> dict[str, object]:
        api, version = target(api, version)
        found = validate_call(document(api, version), method, params, body)
        if found.id in DENIED:
            raise InvalidCall(f"{found.id} is not available here: {DENIED[found.id]}")
        if not found.is_write:
            raise InvalidCall(f"{found.id} only reads; use google.api.read")
        if found.is_delete and not allow_delete:
            raise InvalidCall(f"{found.id} deletes; pass allow_delete=true to confirm the intent")
        operation: dict[str, object] = {"method": found.id, "params": params or {}, "body": body}
        return run(f"{CALL_OP}:{found.id}", api, version, [operation], confirm)

    @guarded
    def google_api_rollback(
        audit_index: int | None = None, confirm: str | None = None
    ) -> dict[str, object]:
        principal = current_principal()
        tenant = principal.tenant_id if principal is not None else None
        candidates = reversible(
            ctx.audit.records, prefix=CALL_OP + ":", tenant=tenant, audit_index=audit_index
        )
        if not candidates:
            raise InvalidCall("no reversible Google API change found in the audit")
        index, record = candidates[-1]
        inverse = [dict(op) for op in record.payload["inverse_operations"]]  # type: ignore[attr-defined]
        api, version = str(record.payload["customer_id"]).split("/", 1)
        operations = [{k: op[k] for k in ("method", "params", "body")} for op in inverse]
        result = run(rollback_op("google.api.rollback", index), api, version, operations, confirm)
        return {**result, "rolled_back": {"audit_index": index, "op": record.op, "ts": record.ts}}

    reads: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "google.api.list",
            "Google APIs reachable through the generic plane, with default versions.",
            google_api_list,
        ),
        (
            "google.api.methods",
            "Methods of a Google API from its Discovery contract (filter by resource, writes only).",
            google_api_methods,
        ),
        (
            "google.api.describe",
            "One method's parameters (location, required, pattern, enum) and request body fields.",
            google_api_describe,
        ),
        (
            "google.api.read",
            "Run a read-only method of any listed Google API, validated against its Discovery contract.",
            google_api_read,
        ),
    ]
    writes: list[tuple[str, str, Callable[..., Any]]] = [
        (
            "google.api.call",
            "Run a write method of any listed Google API (GA4 Admin, GTM, Merchant, YouTube, DV360, "
            "CM360, Business Profile, Search Console, Sheets/Drive/Slides...). `api` is the short "
            "name from google.api.list (e.g. analyticsadmin), `method` the id from "
            "google.api.methods (e.g. properties.customDimensions.create), `params` only the URL "
            "path/query parameters (e.g. parent), `body` the request object. Contract-checked, "
            "guarded, audited, reversible where the API allows; deletes need allow_delete.",
            google_api_call,
        ),
        (
            "google.api.rollback",
            "Undo the latest reversible google.api.call of this tenant (or audit_index) from the audit.",
            google_api_rollback,
        ),
    ]
    for name, description, fn in reads:
        add_tool(app, name, description, fn)
    for name, description, fn in writes:
        add_tool(app, name, description, fn)
    ctx.registry.register(
        Capability(
            connector="google_api",
            domain="read",
            tools=[ToolSpec(name=n, summary=d) for n, d, _ in reads],
        )
    )
    ctx.registry.register(
        Capability(
            connector="google_api",
            domain="write",
            tools=[ToolSpec(name=n, summary=d, read_only=False) for n, d, _ in writes],
        )
    )
