"""FastMCP server assembly: build the core (auth/version/safety/registry) and mount connectors.

Pure ``*_payload`` functions hold the logic (unit-tested directly); thin FastMCP tools wrap them.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.middleware import Middleware
from fastmcp.server.transforms.search.bm25 import BM25SearchTransform

from .connectors.adh import register_adh
from .connectors.bigquery import register_bigquery
from .connectors.cm360 import register_cm360
from .connectors.datamanager import register_datamanager
from .connectors.dv360 import register_dv360
from .connectors.ga4 import register_ga4
from .connectors.gbp import register_gbp
from .connectors.google_ads.read.connector import register_google_ads_read
from .connectors.google_ads.write.connector import register_google_ads_write
from .connectors.gtm import register_gtm
from .connectors.language import register_language
from .connectors.looker import register_looker
from .connectors.merchant import register_merchant
from .connectors.meridian import register_meridian
from .connectors.recaptcha import register_recaptcha
from .connectors.sa360 import register_sa360
from .connectors.searchconsole import register_searchconsole
from .connectors.trends import register_trends
from .connectors.vertex import register_vertex
from .connectors.video import register_video
from .connectors.workspace import register_workspace
from .connectors.youtube import register_youtube
from .core.auth.secret_store import EnvSecretStore
from .core.context import MutateFactory, ServerContext, StreamFactory
from .core.mcp.annotations import RegistryAnnotations
from .core.mcp.guides import register_guides
from .core.mcp.register import add_tool, enable_tasks
from .core.observability.middleware import ObservabilityMiddleware
from .core.observability.recorder import CallRecorder
from .core.registry.registry import Capability, ConnectorRegistry, ToolSpec
from .core.safety.audit import AuditLedger
from .core.safety.audit_tools import register_audit_tools
from .core.safety.mode import SafetyMode
from .core.safety.policy import load_policy
from .core.tenancy import TenantDirectory
from .core.versioning.version_manager import DEFAULT_API_VERSION, VersionManager

Connector = Callable[[FastMCP, ServerContext], None]

# Connector registrars mounted by default.
DEFAULT_CONNECTORS: list[Connector] = [
    register_google_ads_read,
    register_google_ads_write,
    register_ga4,
    register_gtm,
    register_merchant,
    register_datamanager,
    register_searchconsole,
    register_youtube,
    register_dv360,
    register_cm360,
    register_sa360,
    register_bigquery,
    register_vertex,
    register_video,
    register_trends,
    register_gbp,
    register_looker,
    register_meridian,
    register_language,
    register_workspace,
    register_recaptcha,
    register_adh,
]

# Stable connector name -> its registrar(s), for env-based selection
# (QUANTUM_ADS_CONNECTORS="google_ads,ga4"). Lets an operator mount a focused subset so the
# AI client's tool list stays manageable instead of loading every connector at once.
_CONNECTOR_BY_NAME: dict[str, list[Connector]] = {
    "google_ads": [register_google_ads_read, register_google_ads_write],
    "adh": [register_adh],
    "ga4": [register_ga4],
    "gtm": [register_gtm],
    "merchant": [register_merchant],
    "datamanager": [register_datamanager],
    "searchconsole": [register_searchconsole],
    "youtube": [register_youtube],
    "dv360": [register_dv360],
    "cm360": [register_cm360],
    "sa360": [register_sa360],
    "bigquery": [register_bigquery],
    "vertex": [register_vertex],
    "video": [register_video],
    "trends": [register_trends],
    "gbp": [register_gbp],
    "looker": [register_looker],
    "meridian": [register_meridian],
    "language": [register_language],
    "workspace": [register_workspace],
    "recaptcha": [register_recaptcha],
}


def _selected_connectors(env: Mapping[str, str]) -> list[Connector]:
    """Connectors to mount: all by default, or the QUANTUM_ADS_CONNECTORS comma-list subset."""
    names = (env.get("QUANTUM_ADS_CONNECTORS") or "").strip()
    if not names:
        return DEFAULT_CONNECTORS
    selected: list[Connector] = []
    for name in (n.strip() for n in names.split(",")):
        selected.extend(_CONNECTOR_BY_NAME.get(name, []))
    return selected


_SUNSET_WARN_DAYS = 30


@dataclass
class AssembledServer:
    app: FastMCP
    registry: ConnectorRegistry


def health_payload(
    version_manager: VersionManager,
    safety: SafetyMode,
    today: dt.date | None = None,
    recorder: CallRecorder | None = None,
) -> dict[str, object]:
    days = version_manager.days_until_sunset(today)
    result: dict[str, object] = {
        "api_version": version_manager.version,
        "days_until_sunset": days,
        "read_only": safety.read_only,
    }
    if recorder is not None:
        result["calls"] = recorder.summary()
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


def _register_core(app: FastMCP, ctx: ServerContext, recorder: CallRecorder) -> None:
    registry = ctx.registry
    version_manager = ctx.version_manager
    safety = ctx.safety

    def health() -> dict[str, object]:
        return health_payload(version_manager, safety, recorder=recorder)

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
    register_audit_tools(app, ctx)


def _operator_ads_creds(env: Mapping[str, str]) -> dict[str, object]:
    """The operator's Google Ads client dict, or {} when the environment has none.

    The server still starts without Ads credentials (other connectors, or per-tenant credentials
    over HTTP); Ads tools then answer with an explicit error instead of crashing startup.
    """
    try:
        return EnvSecretStore(env).get("default").to_google_ads_dict()
    except KeyError:
        return {}


def _audit_ledger(env: Mapping[str, str]) -> AuditLedger:
    """Persistent ledger under QUANTUM_ADS_AUDIT_DIR when set, else an in-memory one."""
    directory = (env.get("QUANTUM_ADS_AUDIT_DIR") or "").strip()
    return AuditLedger.open(Path(directory).expanduser()) if directory else AuditLedger.ephemeral()


def build_server(
    env: Mapping[str, str],
    stream_factory: StreamFactory,
    connectors: list[Connector] | None = None,
    mutate_factory: MutateFactory | None = None,
    backends: dict[str, object] | None = None,
    *,
    auth: AuthProvider | None = None,
    middleware: list[Middleware] | None = None,
    tenants: TenantDirectory | None = None,
    recorder: CallRecorder | None = None,
) -> AssembledServer:
    creds = _operator_ads_creds(env)
    version = env.get("GOOGLE_ADS_API_VERSION") or DEFAULT_API_VERSION
    read_only = (env.get("QUANTUM_ADS_READ_ONLY") or "true").lower() != "false"

    registry = ConnectorRegistry()
    ctx = ServerContext(
        creds=creds,
        version=version,
        stream_factory=stream_factory,
        version_manager=VersionManager(version, client_factory=lambda c, v: None),
        safety=SafetyMode(
            read_only,
            write_mode=(env.get("QUANTUM_ADS_WRITE_MODE") or "confirm").strip().lower(),
            policy=load_policy(env),
        ),
        registry=registry,
        audit=_audit_ledger(env),
        mutate_factory=mutate_factory,
        backends=backends or {},
        tenants=tenants,
    )

    # Observability runs innermost, after auth/tenancy middleware has bound the principal.
    recorder = recorder or CallRecorder()
    stack = [*(middleware or []), ObservabilityMiddleware(recorder)]
    app: FastMCP = FastMCP("quantum-ads", auth=auth, middleware=stack)
    if (env.get("QUANTUM_ADS_TASKS") or "").lower() == "true" and not enable_tasks(app):
        raise RuntimeError("QUANTUM_ADS_TASKS=true needs the tasks extra: uv sync --extra tasks")
    _register_core(app, ctx, recorder)
    for connector in connectors if connectors is not None else _selected_connectors(env):
        connector(app, ctx)
    register_guides(app, ctx)
    app.add_transform(RegistryAnnotations(registry))
    if (env.get("QUANTUM_ADS_TOOL_SEARCH") or "").lower() == "true":
        # Progressive disclosure: list only the meta tools plus search/call proxies, so an agent
        # loads the few tools a task needs instead of the whole catalog into its context.
        app.add_transform(
            BM25SearchTransform(
                max_results=int(env.get("QUANTUM_ADS_TOOL_SEARCH_RESULTS") or "8"),
                always_visible=["health", "list_capabilities", "describe_tool"],
            )
        )
    return AssembledServer(app=app, registry=registry)
