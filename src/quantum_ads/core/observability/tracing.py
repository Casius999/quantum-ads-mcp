"""Opt-in OpenTelemetry tracing driven by the standard ``OTEL_*`` environment variables.

FastMCP already creates a span per MCP request through the OpenTelemetry API; nothing is
exported until an SDK tracer provider is installed. ``configure_tracing`` installs one when
``OTEL_EXPORTER_OTLP_ENDPOINT`` / ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`` is set (OTLP over HTTP,
configured by the usual OTLP variables) or ``OTEL_TRACES_EXPORTER=console``. Requires the
``observability`` extra (``opentelemetry-sdk`` + ``opentelemetry-exporter-otlp-proto-http``).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping

SERVICE_NAME = "quantum-ads-mcp"


def configure_tracing(env: Mapping[str, str], *, install: bool = True) -> bool:
    """Install an SDK tracer provider if the environment asks for tracing; return whether it did."""
    exporter_kind = (env.get("OTEL_TRACES_EXPORTER") or "").lower()
    endpoint = env.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or env.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if exporter_kind == "none" or (not endpoint and exporter_kind != "console"):
        return False
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SpanExporter,
    )

    exporter: SpanExporter
    if exporter_kind == "console":
        exporter = ConsoleSpanExporter(out=sys.stderr)  # stdout carries the stdio protocol
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter()  # endpoint, headers, timeout from OTEL_EXPORTER_OTLP_*
    resource = Resource.create({"service.name": env.get("OTEL_SERVICE_NAME") or SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    if install:
        trace.set_tracer_provider(provider)
    return True
