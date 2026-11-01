"""Per-call structured logs, health counters and OpenTelemetry spans carrying the tenant."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import Client, FastMCP
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from quantum_ads.core.context import ServerContext
from quantum_ads.core.observability.recorder import CallRecorder
from quantum_ads.core.observability.tracing import configure_tracing
from quantum_ads.core.query.runner import StreamFn
from quantum_ads.server import build_server

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
}

_EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="module", autouse=True)
def _tracer_provider() -> None:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    trace.set_tracer_provider(provider)


def _stream(creds: dict[str, object], version: str) -> StreamFn:
    return lambda customer_id, query: []


def _register_probe(app: FastMCP, ctx: ServerContext) -> None:
    def ok_tool() -> dict[str, object]:
        return {"rows": []}

    def failing_tool() -> dict[str, object]:
        return {"error": {"code": "BACKEND_NOT_CONFIGURED", "message": "x"}}

    def raising_tool() -> dict[str, object]:
        raise RuntimeError("boom")

    for name, fn in (
        ("probe.ok", ok_tool),
        ("probe.fail", failing_tool),
        ("probe.raise", raising_tool),
    ):
        app.tool(name=name)(fn)


def _server(lines: list[str]) -> tuple[FastMCP, CallRecorder]:
    recorder = CallRecorder(sink=lines.append)
    app = build_server(
        env=_ENV, stream_factory=_stream, connectors=[_register_probe], recorder=recorder
    ).app
    return app, recorder


def _run(app: FastMCP, *calls: str) -> dict[str, object]:
    async def scenario() -> dict[str, object]:
        async with Client(app) as client:
            for name in calls:
                await client.call_tool(name, {}, raise_on_error=False)
            health = await client.call_tool("health", {})
            assert isinstance(health.structured_content, dict)
            return health.structured_content

    return asyncio.run(scenario())


def test_each_call_emits_one_json_line_without_arguments():
    lines: list[str] = []
    app, _ = _server(lines)
    _run(app, "probe.ok", "probe.fail", "probe.raise")
    records = [json.loads(line) for line in lines]
    assert [(r["tool"], r["ok"], r["error_code"]) for r in records[:3]] == [
        ("probe.ok", True, None),
        ("probe.fail", False, "BACKEND_NOT_CONFIGURED"),
        ("probe.raise", False, "EXCEPTION"),
    ]
    assert all(r["tenant"] == "operator" and r["duration_ms"] >= 0 for r in records)
    assert set(records[0]) == {"tool", "tenant", "ok", "duration_ms", "error_code", "trace_id"}


def test_health_reports_call_counters():
    app, _ = _server([])
    health = _run(app, "probe.ok", "probe.fail")
    assert health["calls"] == {"total": 2, "ok": 1, "failed": 1}


def test_tool_spans_carry_the_tenant_and_outcome():
    _EXPORTER.clear()
    lines: list[str] = []
    app, _ = _server(lines)

    async def scenario() -> None:
        async with Client(app) as client:
            await client.call_tool("probe.fail", {}, raise_on_error=False)

    asyncio.run(scenario())
    tool_spans = [s for s in _EXPORTER.get_finished_spans() if "probe.fail" in s.name]
    assert tool_spans, [s.name for s in _EXPORTER.get_finished_spans()]
    attributes = dict(tool_spans[0].attributes or {})
    assert attributes["quantum_ads.tenant"] == "operator"
    assert attributes["quantum_ads.outcome"] == "error"
    assert attributes["quantum_ads.error_code"] == "BACKEND_NOT_CONFIGURED"
    record = json.loads(lines[0])
    assert record["trace_id"] == format(tool_spans[0].context.trace_id, "032x")


def test_tracing_is_off_without_otel_configuration():
    assert configure_tracing({}) is False


def test_console_exporter_can_be_selected():
    assert configure_tracing({"OTEL_TRACES_EXPORTER": "console"}, install=False) is True


def test_otlp_endpoint_enables_export():
    env = {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318"}
    assert configure_tracing(env, install=False) is True
    assert configure_tracing({**env, "OTEL_TRACES_EXPORTER": "none"}, install=False) is False
