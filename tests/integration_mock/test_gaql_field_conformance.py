"""GAQL field conformance: every field our tools query exists in the pinned Google Ads API version.

Captures the exact GAQL each Google Ads read tool generates (through a recording stream), then
resolves every ``resource.field``, ``metrics.*`` and ``segments.*`` path against the protobuf
descriptors shipped in the installed ``google-ads`` SDK for that API version. Offline and
deterministic — no developer token, no network — so it runs in CI and catches a field removed or
renamed by a new API version before any live call does.
"""

from __future__ import annotations

import importlib
import re

import pytest

from quantum_ads.connectors.google_ads.read import report_tools
from quantum_ads.connectors.google_ads.read.change_history import change_history
from quantum_ads.connectors.google_ads.read.planning import build_recommendations_query
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION

# Versions checked: the pinned default plus the previous one still in support (migration window).
_VERSIONS = sorted({DEFAULT_API_VERSION, "v24"})

_FIELD = re.compile(r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)\b")


def _generated_queries() -> list[str]:
    captured: list[str] = []

    def recording_stream(customer_id: str, query: str) -> list[dict[str, object]]:
        captured.append(query)
        return []

    for report in (
        report_tools.report_campaign,
        report_tools.report_search_terms,
        report_tools.report_pmax_asset_groups,
        report_tools.report_ai_max,
        report_tools.report_conversions,
    ):
        report(customer_id="1", stream=recording_stream)
    for mode in ("audit", "delta"):
        change_history(customer_id="1", mode=mode, stream=recording_stream)
    captured.append(build_recommendations_query(["KEYWORD"]))
    return captured


def _referenced_fields(query: str) -> set[str]:
    # Drop string literals so quoted values are never mistaken for field paths.
    stripped = re.sub(r"'[^']*'", "''", query)
    return {m.group(1) for m in _FIELD.finditer(stripped)}


def _message_descriptor(version: str, root: str):  # type: ignore[no-untyped-def]
    if root in ("metrics", "segments"):
        module = importlib.import_module(f"google.ads.googleads.{version}.common.types.{root}")
        cls = getattr(module, root.capitalize())
    else:
        module = importlib.import_module(f"google.ads.googleads.{version}.resources.types.{root}")
        cls = getattr(module, "".join(part.capitalize() for part in root.split("_")))
    return cls.pb().DESCRIPTOR


def _resolve(version: str, path: str) -> str | None:
    """Return None when ``path`` exists in ``version``, else a reason string."""
    root, *rest = path.split(".")
    try:
        descriptor = _message_descriptor(version, root)
    except (ModuleNotFoundError, AttributeError):
        return f"resource {root!r} does not exist in {version}"
    for name in rest:
        # proto-plus renames Python keywords (GAQL `type` is the `type_` field).
        field = descriptor.fields_by_name.get(name) or descriptor.fields_by_name.get(name + "_")
        if field is None:
            return f"{path}: field {name!r} absent from {descriptor.name} in {version}"
        descriptor = field.message_type
        if descriptor is None:
            break
    return None


def test_queries_were_captured():
    queries = _generated_queries()
    assert len(queries) == 8, queries


@pytest.mark.parametrize("version", _VERSIONS)
def test_every_gaql_field_exists_in_api_version(version: str) -> None:
    problems = sorted(
        {
            reason
            for query in _generated_queries()
            for path in _referenced_fields(query)
            if (reason := _resolve(version, path)) is not None
        }
    )
    assert not problems, problems
