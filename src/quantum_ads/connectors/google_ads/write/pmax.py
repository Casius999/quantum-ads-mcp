"""Performance Max campaign builder: one atomic list of mutate operations.

Creates the budget, the campaign (brand guidelines on, so the business name and logo are linked
at campaign level), geo/language targeting, every text and image asset, the asset group, and the
asset-group links — all in one ``GoogleAdsService.Mutate`` request with temporary ids, the way
Google requires (an asset group must reach its minimum assets in the same request it is created).
Images are base64 (for example straight from ``vertex.imagen.generate``).
"""

from __future__ import annotations

from collections.abc import Sequence

from .operations import InvalidOperation

LIMITS = {
    "headlines": (3, 15, 30),
    "long_headlines": (1, 5, 90),
    "descriptions": (2, 5, 90),
}
IMAGE_FIELDS = ("MARKETING_IMAGE", "SQUARE_MARKETING_IMAGE", "PORTRAIT_MARKETING_IMAGE")


def _check_texts(name: str, texts: Sequence[str]) -> None:
    low, high, chars = LIMITS[name]
    if not low <= len(texts) <= high:
        raise InvalidOperation(f"{name}: {low} to {high} required, got {len(texts)}")
    too_long = [t for t in texts if len(t) > chars]
    if too_long:
        raise InvalidOperation(f"{name} over {chars} characters: {too_long}")


def build_pmax_campaign(
    *,
    customer_id: str,
    name: str,
    daily_budget_micros: int,
    final_url: str,
    business_name: str,
    headlines: Sequence[str],
    long_headlines: Sequence[str],
    descriptions: Sequence[str],
    logo_base64: str,
    images: Sequence[dict[str, str]],
    geo_target_ids: Sequence[str] = (),
    language_ids: Sequence[str] = (),
    bidding: str = "MAXIMIZE_CONVERSIONS",
    target_cpa_micros: int | None = None,
    target_roas: float | None = None,
    status: str = "PAUSED",
) -> list[dict[str, object]]:
    """``images``: ``[{"field_type": "MARKETING_IMAGE"|..., "data_base64": "..."}]``."""
    for field in LIMITS:
        _check_texts(
            field,
            {
                "headlines": headlines,
                "long_headlines": long_headlines,
                "descriptions": descriptions,
            }[field],
        )
    if not any(len(d) <= 60 for d in descriptions):
        raise InvalidOperation("descriptions: at least one must be 60 characters or fewer")
    if len(business_name) > 25:
        raise InvalidOperation("business_name over 25 characters")
    kinds = {str(image.get("field_type")) for image in images}
    if not {"MARKETING_IMAGE", "SQUARE_MARKETING_IMAGE"} <= kinds:
        raise InvalidOperation(
            "images need at least one MARKETING_IMAGE and one SQUARE_MARKETING_IMAGE"
        )
    unknown = kinds - set(IMAGE_FIELDS)
    if unknown:
        raise InvalidOperation(f"unknown image field types {sorted(unknown)}; use {IMAGE_FIELDS}")

    root = f"customers/{customer_id}"
    budget, campaign, group = (
        f"{root}/campaignBudgets/-1",
        f"{root}/campaigns/-2",
        f"{root}/assetGroups/-3",
    )
    if bidding == "MAXIMIZE_CONVERSIONS":
        bid: dict[str, object] = {
            "maximize_conversions": {"target_cpa_micros": str(target_cpa_micros)}
            if target_cpa_micros
            else {}
        }
    elif bidding == "MAXIMIZE_CONVERSION_VALUE":
        bid = {"maximize_conversion_value": {"target_roas": target_roas} if target_roas else {}}
    else:
        raise InvalidOperation("bidding must be MAXIMIZE_CONVERSIONS or MAXIMIZE_CONVERSION_VALUE")

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
                    "advertising_channel_type": "PERFORMANCE_MAX",
                    "campaign_budget": budget,
                    "brand_guidelines_enabled": True,
                    "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
                    **bid,
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

    next_id = [-10]

    def asset(body: dict[str, object]) -> str:
        resource = f"{root}/assets/{next_id[0]}"
        next_id[0] -= 1
        ops.append({"asset_operation": {"create": {"resource_name": resource, **body}}})
        return resource

    brand_name = asset({"text_asset": {"text": business_name}})
    brand_logo = asset({"name": f"{name} logo", "image_asset": {"data": logo_base64}})
    linked: list[tuple[str, str]] = []
    for field, texts in (
        ("HEADLINE", headlines),
        ("LONG_HEADLINE", long_headlines),
        ("DESCRIPTION", descriptions),
    ):
        linked += [(asset({"text_asset": {"text": text}}), field) for text in texts]
    for index, image in enumerate(images):
        resource = asset(
            {"name": f"{name} image {index + 1}", "image_asset": {"data": image["data_base64"]}}
        )
        linked.append((resource, image["field_type"]))

    ops.append(
        {
            "asset_group_operation": {
                "create": {
                    "resource_name": group,
                    "campaign": campaign,
                    "name": f"{name} asset group",
                    "final_urls": [final_url],
                    "status": "ENABLED",
                }
            }
        }
    )
    ops += [
        {
            "asset_group_asset_operation": {
                "create": {"asset_group": group, "asset": resource, "field_type": field}
            }
        }
        for resource, field in linked
    ]
    ops += [
        {
            "campaign_asset_operation": {
                "create": {"campaign": campaign, "asset": brand_name, "field_type": "BUSINESS_NAME"}
            }
        },
        {
            "campaign_asset_operation": {
                "create": {"campaign": campaign, "asset": brand_logo, "field_type": "LOGO"}
            }
        },
    ]
    return ops
