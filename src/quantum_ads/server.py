"""FastMCP server assembly: build the core (auth/version/safety/registry) and mount connectors.

Pure ``*_payload`` functions hold the logic (unit-tested directly); thin FastMCP tools wrap them.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fastmcp import FastMCP

from .connectors.ga4 import register_ga4
from .connectors.google_ads.read.connector import register_google_ads_read
from .connectors.google_ads.write.connector import register_google_ads_write
from .connectors.gtm import register_gtm
from .connectors.merchant import register_merchant
from .core.auth.secret_store import EnvSecretStore
from .core.context import MutateFactory, ServerContext, StreamFactory
from .core.mcp.register import add_tool
from .core.registry.registry import Capability, ConnectorRegistry, ToolSpec
from .core.safety.audit import AuditLedger
from .core.safety.mode import SafetyMode
from .core.versioning.version_manager import VersionManager

Connector = Callable[[FastMCP, ServerContext], None]

# Connector registrars mounted by default.
DEFAULT_CONNECTORS: list[Connector] = [
    register_google_ads_read,
    register_google_ads_write,
    register_ga4,
    register_gtm,
    register_merchant,
]

_SUNSET_WARN_DAYS = 30


@dataclass
class AssembledServer:
    app: FastMCP
    registry: ConnectorRegistry


def health_payload(
    version_manager: VersionManager, safety: SafetyMode, today: dt.date | None = None
) -> dict[str, object]:
    days = version_manager.days_until_sunset(today)
    result: dict[str, object] = {
        "api_version": version_manager.version,
        "days_until_sunset": days,
        "read_only": safety.read_only,
    }
    if days is not None and days < _SUNSET_WARN_DAYS:
        result["warning"] = f"API {version_manager.version} sunsets in {days} days — bump version"
    return result


def capabilities_payload(registry: ConnectorRegistry) -> list[dict[str, object]]:
    return [
        {
            "connector": cap.connector,
            "domain": cap.domain,
            "tools": [
                {"name": t.name, "summary": t.summary, "read_only": t.read_only} for t in cap.tools
            ],
        }
        for cap in registry.list_capabilities()
    ]


def describe_tool_payload(registry: ConnectorRegistry, name: str) -> dict[str, object]:
    try:
        spec = registry.describe_tool(name)
    except KeyError:
        return {"error": {"code": "UNKNOWN_TOOL", "message": f"no tool named {name!r}"}}
    return {"name": spec.name, "summary": spec.summary, "read_only": spec.read_only}


def _register_core(app: FastMCP, ctx: ServerContext) -> None:
    registry = ctx.registry
    version_manager = ctx.version_manager
    safety = ctx.safety

    def health() -> dict[str, object]:
        return health_payload(version_manager, safety)

    def list_capabilities() -> list[dict[str, object]]:
        return capabilities_payload(registry)

    def describe_tool(name: str) -> dict[str, object]:
        return describe_tool_payload(registry, name)

    add_tool(app, "health", "Server + Google Ads API version health.", health)
    add_tool(
        app, "list_capabilities", "List connector capabilities and their tools.", list_capabilities
    )
    add_tool(app, "describe_tool", "Describe a registered tool by name.", describe_tool)
    registry.register(
        Capability(
            connector="core",
            domain="meta",
            tools=[
                ToolSpec(name="health", summary="Server + API version health."),
                ToolSpec(
                    name="list_capabilities", summary="List connector capabilities and tools."
                ),
                ToolSpec(name="describe_tool", summary="Describe a registered tool by name."),
            ],
        )
    )


def build_server(
    env: Mapping[str, str],
    stream_factory: StreamFactory,
    connectors: list[Connector] | None = None,
    mutate_factory: MutateFactory | None = None,
    backends: dict[str, object] | None = None,
) -> AssembledServer:
    creds = EnvSecretStore(env).get("default").to_google_ads_dict()
    version = env.get("GOOGLE_ADS_API_VERSION") or "v24"
    read_only = (env.get("QUANTUM_ADS_READ_ONLY") or "true").lower() != "false"

    registry = ConnectorRegistry()
    ctx = ServerContext(
        creds=creds,
        version=version,
        stream_factory=stream_factory,
        version_manager=VersionManager(version, client_factory=lambda c, v: None),
        safety=SafetyMode(read_only),
        registry=registry,
        audit=AuditLedger.ephemeral(),
        mutate_factory=mutate_factory,
        backends=backends or {},
    )

    app: FastMCP = FastMCP("quantum-ads")
    _register_core(app, ctx)
    for connector in connectors if connectors is not None else DEFAULT_CONNECTORS:
        connector(app, ctx)
    return AssembledServer(app=app, registry=registry)
