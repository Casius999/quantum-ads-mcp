"""End-to-end smoke: register every connector against a recorder app and invoke each tool.

Covers the thin tool closures (backend resolution, guarded write flow, not-configured
degradation) without going through FastMCP transport or any real SDK.
"""

import inspect

from quantum_ads.connectors.bigquery import register_bigquery
from quantum_ads.connectors.cm360 import register_cm360
from quantum_ads.connectors.datamanager import register_datamanager
from quantum_ads.connectors.dv360 import register_dv360
from quantum_ads.connectors.ga4 import register_ga4
from quantum_ads.connectors.gbp import register_gbp
from quantum_ads.connectors.google_ads.read.connector import register_google_ads_read
from quantum_ads.connectors.google_ads.write.connector import register_google_ads_write
from quantum_ads.connectors.gtm import register_gtm
from quantum_ads.connectors.language import register_language
from quantum_ads.connectors.looker import register_looker
from quantum_ads.connectors.merchant import register_merchant
from quantum_ads.connectors.meridian import register_meridian
from quantum_ads.connectors.recaptcha import register_recaptcha
from quantum_ads.connectors.sa360 import register_sa360
from quantum_ads.connectors.searchconsole import register_searchconsole
from quantum_ads.connectors.trends import register_trends
from quantum_ads.connectors.vertex import register_vertex
from quantum_ads.connectors.workspace import register_workspace
from quantum_ads.connectors.youtube import register_youtube
from quantum_ads.core.context import ServerContext
from quantum_ads.core.registry.registry import ConnectorRegistry
from quantum_ads.core.safety.audit import AuditLedger
from quantum_ads.core.safety.mode import SafetyMode
from quantum_ads.core.versioning.version_manager import VersionManager

REGISTRARS = [
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
    register_trends,
    register_gbp,
    register_looker,
    register_meridian,
    register_language,
    register_workspace,
    register_recaptcha,
]


class _Recorder:
    """Duck-typed stand-in for FastMCP: captures the raw callable add_tool registers."""

    def __init__(self) -> None:
        self.fns: dict[str, object] = {}

    def tool(self, *, name: str, description: str):  # type: ignore[no-untyped-def]
        def deco(fn):  # type: ignore[no-untyped-def]
            self.fns[name] = fn
            return fn

        return deco


def _fake_read(operation, params):  # type: ignore[no-untyped-def]
    return [{"row": 1}]


def _fake_mutate(account_id, operations, validate_only):  # type: ignore[no-untyped-def]
    return {"validate_only": validate_only, "ok": True}


_BACKENDS: dict[str, object] = {
    "ga4.data": _fake_read,
    "ga4.admin": _fake_read,
    "ga4.admin.mutate": _fake_mutate,
    "gtm.api": _fake_read,
    "gtm.mutate": _fake_mutate,
    "merchant.api": _fake_read,
    "merchant.mutate": _fake_mutate,
    "datamanager.api": _fake_mutate,
    "datamanager.read": _fake_read,
    "searchconsole.api": _fake_read,
    "searchconsole.mutate": _fake_mutate,
    "youtube.data": _fake_read,
    "youtube.analytics": _fake_read,
    "youtube.mutate": _fake_mutate,
    "dv360.api": _fake_read,
    "dv360.mutate": _fake_mutate,
    "cm360.api": _fake_read,
    "cm360.mutate": _fake_mutate,
    "sa360.api": _fake_read,
    "sa360.mutate": _fake_mutate,
    "bigquery.api": _fake_read,
    "bigquery.mutate": _fake_mutate,
    "vertex.api": _fake_read,
    "trends.api": _fake_read,
    "gbp.api": _fake_read,
    "gbp.reviews": _fake_read,
    "gbp.mutate": _fake_mutate,
    "looker.api": _fake_read,
    "looker.mutate": _fake_mutate,
    "meridian.api": _fake_read,
    "language.api": _fake_read,
    "workspace.api": _fake_read,
    "workspace.mutate": _fake_mutate,
    "recaptcha.api": _fake_read,
    "recaptcha.mutate": _fake_mutate,
}


def _ctx(backends, mutate_factory):  # type: ignore[no-untyped-def]
    return ServerContext(
        creds={},
        version="v24",
        stream_factory=lambda c, v: lambda cid, q: [{"campaign": {"id": 1}}],
        version_manager=VersionManager("v24", client_factory=lambda c, v: None),
        safety=SafetyMode(read_only=False),
        registry=ConnectorRegistry(),
        audit=AuditLedger.ephemeral(),
        mutate_factory=mutate_factory,
        backends=backends,
    )


def _invoke_all(fns):  # type: ignore[no-untyped-def]
    for fn in fns.values():
        kwargs = {}
        for pname, p in inspect.signature(fn).parameters.items():
            if p.default is not inspect.Parameter.empty:
                continue
            ann = str(p.annotation)
            if "list" in ann:
                kwargs[pname] = []
            elif "dict" in ann:
                kwargs[pname] = {}
            elif "int" in ann:
                kwargs[pname] = 1
            else:
                kwargs[pname] = "1"
        result = fn(**kwargs)
        assert result is not None


def test_all_connector_tools_invoke_when_configured():
    for reg in REGISTRARS:
        rec = _Recorder()
        reg(rec, _ctx(dict(_BACKENDS), lambda c, v: _fake_mutate))
        assert rec.fns
        _invoke_all(rec.fns)


def test_all_connector_tools_invoke_when_unconfigured():
    for reg in REGISTRARS:
        rec = _Recorder()
        reg(rec, _ctx({}, None))
        _invoke_all(rec.fns)
