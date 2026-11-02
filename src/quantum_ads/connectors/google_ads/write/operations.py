"""Google Ads mutate operations: offline validation, schema discovery, campaign builders.

``ads.mutate`` takes operations in the official ``MutateOperation`` JSON shape (snake_case, one
``*_operation`` key per item, e.g. ``{"campaign_operation": {"create": {...}}}``) and sends them
in one ``GoogleAdsService.Mutate`` request, so every one of the API's mutable resources is in
reach. Temporary resource names with negative ids (``customers/1/campaignBudgets/-1``) link
objects created in the same request. Operations are parsed against the pinned version's protos
*before* any network call: a misspelled field or wrong type is reported with its index.

The builders below compose complete structures (a Search campaign with budget, targeting,
ad group, keywords and a responsive search ad) as plain operation lists for the same path.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any

from google.protobuf import json_format

MAX_HEADLINE_CHARS = 30
MAX_DESCRIPTION_CHARS = 90


class InvalidOperation(ValueError):
    """An operation does not match the Google Ads API schema for the pinned version."""


def _mutate_operation_cls(version: str) -> Any:
    module = importlib.import_module(
        f"google.ads.googleads.{version}.services.types.google_ads_service"
    )
    return module.MutateOperation


def operation_kinds(version: str) -> list[str]:
    """Every ``*_operation`` key accepted by ``GoogleAdsService.Mutate`` in ``version``."""
    descriptor = _mutate_operation_cls(version).pb().DESCRIPTOR
    return sorted(field.name for field in descriptor.fields)


def resource_fields(version: str, operation_kind: str) -> dict[str, object]:
    """Field names and types of the resource an operation kind creates or updates."""
    descriptor = _mutate_operation_cls(version).pb().DESCRIPTOR
    field = descriptor.fields_by_name.get(operation_kind)
    if field is None:
        raise InvalidOperation(f"unknown operation kind {operation_kind!r}")
    create = field.message_type.fields_by_name.get(
        "create"
    ) or field.message_type.fields_by_name.get("update")
    if create is None or create.message_type is None:
        return {"operation": operation_kind, "fields": {}}
    resource = create.message_type
    return {
        "operation": operation_kind,
        "resource": resource.full_name,
        "fields": {
            f.name: (f.message_type.full_name if f.message_type else _TYPE_NAMES.get(f.type, "?"))
            for f in resource.fields
        },
    }


_TYPE_NAMES = {
    1: "double",
    2: "float",
    3: "int64",
    5: "int32",
    8: "bool",
    9: "string",
    12: "bytes",
    14: "enum",
}


def validate_operations(operations: Sequence[dict[str, object]], version: str) -> list[Any]:
    """Parse every operation into a ``MutateOperation`` protobuf, or raise with its index."""
    if not operations:
        raise InvalidOperation("operations is empty")
    message_cls = _mutate_operation_cls(version).pb()
    parsed = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict) or len(operation) != 1:
            raise InvalidOperation(
                f"operation {index}: expected exactly one '*_operation' key, got {operation!r:.200}"
            )
        message = message_cls()
        try:
            json_format.ParseDict(operation, message)
        except json_format.ParseError as exc:
            raise InvalidOperation(f"operation {index}: {exc}") from exc
        parsed.append(message)
    return parsed


def _text_assets(texts: Sequence[str], limit: int, label: str) -> list[dict[str, object]]:
    too_long = [t for t in texts if len(t) > limit]
    if too_long:
        raise InvalidOperation(f"{label} over {limit} characters: {too_long}")
    return [{"text": t} for t in texts]


def build_search_campaign(
    *,
    customer_id: str,
    name: str,
    daily_budget_micros: int,
    final_url: str,
    keywords: Sequence[str],
    headlines: Sequence[str],
    descriptions: Sequence[str],
    geo_target_ids: Sequence[str] = (),
    language_ids: Sequence[str] = (),
    negative_keywords: Sequence[str] = (),
    match_type: str = "PHRASE",
    bidding: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    status: str = "PAUSED",
) -> list[dict[str, object]]:
    """A complete Search campaign as one atomic list of mutate operations."""
    if not 3 <= len(headlines) <= 15:
        raise InvalidOperation("a responsive search ad needs 3 to 15 headlines")
    if not 2 <= len(descriptions) <= 4:
        raise InvalidOperation("a responsive search ad needs 2 to 4 descriptions")
    if not keywords:
        raise InvalidOperation("at least one keyword is required")
    root = f"customers/{customer_id}"
    budget, campaign, group = (
        f"{root}/campaignBudgets/-1",
        f"{root}/campaigns/-2",
        f"{root}/adGroups/-3",
    )
    bidding_field: dict[str, object]
    if bidding == "MAXIMIZE_CONVERSIONS":
        bidding_field = {
            "maximize_conversions": (
                {"target_cpa_micros": str(target_cpa_micros)} if target_cpa_micros else {}
            )
        }
    elif bidding == "MAXIMIZE_CLICKS":
        bidding_field = {"target_spend": {}}
    elif bidding == "MANUAL_CPC":
        bidding_field = {"manual_cpc": {}}
    else:
        raise InvalidOperation(
            "bidding must be MAXIMIZE_CONVERSIONS, MAXIMIZE_CLICKS or MANUAL_CPC"
        )

    ops: list[dict[str, object]] = [
        {
            "campaign_budget_operation": {
                "create": {
                    "resource_name": budget,
                    "name": f"{name} budget",
                    "amount_micros": str(int(daily_budget_micros)),
                    "delivery_method": "STANDARD",
                    "explicitly_shared": False,
                }
            }
        },
        {
            "campaign_operation": {
                "create": {
                    "resource_name": campaign,
                    "name": name,
                    "status": status,
                    "advertising_channel_type": "SEARCH",
                    "campaign_budget": budget,
                    "network_settings": {
                        "target_google_search": True,
                        "target_search_network": True,
                        "target_content_network": False,
                    },
                    "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
                    **bidding_field,
                }
            }
        },
    ]
    for geo in geo_target_ids:
        ops.append(
            {
                "campaign_criterion_operation": {
                    "create": {
                        "campaign": campaign,
                        "location": {"geo_target_constant": f"geoTargetConstants/{geo}"},
                    }
                }
            }
        )
    for language in language_ids:
        ops.append(
            {
                "campaign_criterion_operation": {
                    "create": {
                        "campaign": campaign,
                        "language": {"language_constant": f"languageConstants/{language}"},
                    }
                }
            }
        )
    for negative in negative_keywords:
        ops.append(
            {
                "campaign_criterion_operation": {
                    "create": {
                        "campaign": campaign,
                        "negative": True,
                        "keyword": {"text": negative, "match_type": "PHRASE"},
                    }
                }
            }
        )
    ops.append(
        {
            "ad_group_operation": {
                "create": {
                    "resource_name": group,
                    "name": f"{name} ad group",
                    "campaign": campaign,
                    "status": "ENABLED",
                    "type": "SEARCH_STANDARD",
                }
            }
        }
    )
    for keyword in keywords:
        ops.append(
            {
                "ad_group_criterion_operation": {
                    "create": {
                        "ad_group": group,
                        "status": "ENABLED",
                        "keyword": {"text": keyword, "match_type": match_type},
                    }
                }
            }
        )
    ops.append(
        {
            "ad_group_ad_operation": {
                "create": {
                    "ad_group": group,
                    "status": "ENABLED",
                    "ad": {
                        "final_urls": [final_url],
                        "responsive_search_ad": {
                            "headlines": _text_assets(headlines, MAX_HEADLINE_CHARS, "headlines"),
                            "descriptions": _text_assets(
                                descriptions, MAX_DESCRIPTION_CHARS, "descriptions"
                            ),
                        },
                    },
                }
            }
        }
    )
    return ops
