"""Observe every tool call: structured record + OpenTelemetry span attributes.

Installed innermost (after auth/tenancy middleware), so the request principal is known. FastMCP
opens the OpenTelemetry span for each ``tools/call``; this adds the tenant, outcome and error
code to it and stamps the trace id on the JSON record so logs and traces join up.
"""

from __future__ import annotations

import time
from typing import Any

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from opentelemetry import trace

from ..tenancy import current_principal
from .recorder import CallRecorder

OPERATOR_TENANT = "operator"


def _error_code(result: Any) -> str | None:
    """Connector tools report failures as ``{"error": {"code": ...}}`` rather than raising."""
    content = getattr(result, "structured_content", None)
    if isinstance(content, dict) and isinstance(content.get("error"), dict):
        return str(content["error"].get("code") or "ERROR")
    return None


class ObservabilityMiddleware(Middleware):
    def __init__(self, recorder: CallRecorder) -> None:
        self._recorder = recorder

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        started = time.perf_counter()
        error_code: str | None = "EXCEPTION"
        try:
            result = await call_next(context)
            error_code = _error_code(result)
            return result
        finally:
            principal = current_principal()
            tenant = principal.tenant_id if principal is not None else OPERATOR_TENANT
            span = trace.get_current_span()
            span_context = span.get_span_context()
            if span.is_recording():
                span.set_attribute("quantum_ads.tenant", tenant)
                span.set_attribute("quantum_ads.outcome", "error" if error_code else "ok")
                if error_code:
                    span.set_attribute("quantum_ads.error_code", error_code)
            self._recorder.record(
                tool=str(getattr(context.message, "name", "?")),
                tenant=tenant,
                ok=error_code is None,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error_code=error_code,
                trace_id=format(span_context.trace_id, "032x") if span_context.is_valid else None,
            )
