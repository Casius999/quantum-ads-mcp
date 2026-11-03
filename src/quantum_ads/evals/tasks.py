"""The eval task suite: realistic agency requests over scripted backends."""

from __future__ import annotations

import json
from collections.abc import Callable

from fastmcp import FastMCP

from ..connectors.google_ads.read.connector import register_google_ads_read
from ..connectors.google_ads.write.connector import register_google_ads_write
from ..connectors.googleapi import register_google_api
from ..connectors.insights import register_insights
from ..server import Connector, build_server
from .harness import Record, Task

_ENV = {
    "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
    "GOOGLE_ADS_CLIENT_ID": "c",
    "GOOGLE_ADS_CLIENT_SECRET": "s",
    "GOOGLE_ADS_REFRESH_TOKEN": "r",
    "QUANTUM_ADS_WRITE_MODE": "auto",
    "QUANTUM_ADS_AUDIT_DIR": "",
}
_CAMPAIGNS = [
    {"campaign.id": "41", "campaign.name": "Brand", "metrics.cost_micros": 12_000_000},
    {"campaign.id": "42", "campaign.name": "Running Shoes", "metrics.cost_micros": 87_000_000},
    {"campaign.id": "43", "campaign.name": "Trail", "metrics.cost_micros": 5_000_000},
]
_TERMS = [
    {
        "search_term_view.search_term": "free running shoes",
        "campaign.id": "42",
        "ad_group.id": "7",
        "metrics.cost_micros": 31_000_000,
        "metrics.clicks": 40,
        "metrics.conversions": 0,
    },
    {
        "search_term_view.search_term": "running shoes men",
        "campaign.id": "42",
        "ad_group.id": "7",
        "metrics.cost_micros": 20_000_000,
        "metrics.clicks": 30,
        "metrics.conversions": 6,
    },
]
_GA4_DOC: dict[str, object] = {
    "name": "analyticsadmin",
    "version": "v1beta",
    "schemas": {
        "CustomDimension": {
            "type": "object",
            "properties": {
                "parameterName": {"type": "string"},
                "displayName": {"type": "string"},
                "scope": {"type": "string", "enum": ["EVENT", "USER", "ITEM"]},
            },
        }
    },
    "resources": {
        "properties": {
            "resources": {
                "customDimensions": {
                    "methods": {
                        "create": {
                            "id": "analyticsadmin.properties.customDimensions.create",
                            "httpMethod": "POST",
                            "description": "Creates a CustomDimension.",
                            "parameters": {
                                "parent": {
                                    "type": "string",
                                    "location": "path",
                                    "required": True,
                                    "pattern": "^properties/[^/]+$",
                                }
                            },
                            "request": {"$ref": "CustomDimension"},
                        },
                        "list": {
                            "id": "analyticsadmin.properties.customDimensions.list",
                            "httpMethod": "GET",
                            "parameters": {
                                "parent": {"type": "string", "location": "path", "required": True}
                            },
                        },
                    }
                }
            }
        }
    },
}


def _stream(
    record: Record,
) -> Callable[[dict[str, object], str], Callable[[str, str], list[dict[str, object]]]]:
    def factory(
        creds: dict[str, object], version: str
    ) -> Callable[[str, str], list[dict[str, object]]]:
        def stream(customer_id: str, query: str) -> list[dict[str, object]]:
            record.queries.append(query)
            if "search_term_view" in query:
                return list(_TERMS)
            if "ad_group_criterion" in query:
                return [{"ad_group_criterion.keyword.text": "running shoes"}]
            if "FROM campaign" in query:
                return list(_CAMPAIGNS)
            return []

        return stream

    return factory


def _mutate(record: Record) -> Callable[[dict[str, object], str], Callable[..., dict[str, object]]]:
    def factory(creds: dict[str, object], version: str) -> Callable[..., dict[str, object]]:
        def mutate(
            target: str, operations: list[dict[str, object]], validate_only: bool
        ) -> dict[str, object]:
            record.mutations.append((target, operations, validate_only))
            return {"results": [{"resource_name": f"customers/{target}/x/1"}]}

        return mutate

    return factory


def _google_api(op: str, params: dict[str, object]) -> list[dict[str, object]]:
    return [_GA4_DOC] if op == "discovery" else [{"customDimensions": []}]


def _server(record: Record, connectors: list[Connector], **env: str) -> FastMCP:
    def google_api_mutate(
        target: str, operations: list[dict[str, object]], preview: bool
    ) -> dict[str, object]:
        record.mutations.append((target, operations, preview))
        return {"results": [{"name": "properties/123/customDimensions/1"}]}

    backends: dict[str, object] = {
        "google.api": _google_api,
        "google.api.mutate": google_api_mutate,
    }
    return build_server(
        env={**_ENV, "QUANTUM_ADS_READ_ONLY": "false", **env},
        stream_factory=_stream(record),
        mutate_factory=_mutate(record),
        connectors=connectors,
        backends=backends,
    ).app


_ADS: list[Connector] = [register_google_ads_read, register_google_ads_write]


def _applied_text(record: Record) -> str:
    return json.dumps(record.applied, default=str)


TASKS: list[Task] = [
    Task(
        name="pause_campaign",
        prompt="Pause campaign 42 in Google Ads customer 7750839245.",
        build=lambda r: _server(r, _ADS),
        check=lambda r: "42" in _applied_text(r) and "PAUSED" in _applied_text(r),
    ),
    Task(
        name="top_spender",
        prompt="Which campaign of customer 7750839245 spent the most in the last 7 days? Name it.",
        build=lambda r: _server(r, _ADS),
        check=lambda r: (
            any("cost_micros" in q for q in r.queries) and "running shoes" in r.answer.lower()
        ),
    ),
    Task(
        name="negative_wasted_terms",
        prompt=(
            "Find the search terms of customer 7750839245 that cost money without converting "
            "and add them as negative keywords."
        ),
        build=lambda r: _server(r, [*_ADS, register_insights]),
        check=lambda r: (
            "free running shoes" in _applied_text(r) and "running shoes men" not in _applied_text(r)
        ),
    ),
    Task(
        name="ga4_custom_dimension",
        prompt=(
            "In GA4 property 123, create an event-scoped custom dimension for the event "
            "parameter 'plan_tier' displayed as 'Plan tier'."
        ),
        build=lambda r: _server(r, [register_google_api]),
        check=lambda r: "plan_tier" in _applied_text(r) and "EVENT" in _applied_text(r),
    ),
    Task(
        name="read_only_is_respected",
        prompt="Pause campaign 42 in Google Ads customer 7750839245.",
        build=lambda r: _server(r, _ADS, QUANTUM_ADS_READ_ONLY="true"),
        check=lambda r: not r.applied and bool(r.answer),
    ),
]
