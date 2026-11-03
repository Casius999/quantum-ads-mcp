"""Builders for Demand Gen campaigns and A/B experiments (mutate operation lists).

Demand Gen: budget, DEMAND_GEN campaign, an ad group carrying location/language targeting (Demand
Gen targets at ad-group level), image/logo/text assets and a multi-asset ad — one atomic batch.

Experiments: an experiment plus its control arm (the base campaign) and treatment arm with a
traffic split. Google then creates the treatment's draft campaign (``in_design_campaigns``),
which the agent edits with ``ads.mutate`` before scheduling, promoting or ending the experiment.
"""

from __future__ import annotations

from collections.abc import Sequence

from .operations import InvalidOperation


def build_demand_gen_campaign(
    *,
    customer_id: str,
    name: str,
    daily_budget_micros: int,
    final_url: str,
    business_name: str,
    headlines: Sequence[str],
    descriptions: Sequence[str],
    logo_base64: str,
    marketing_images_base64: Sequence[str],
    square_images_base64: Sequence[str],
    geo_target_ids: Sequence[str] = (),
    language_ids: Sequence[str] = (),
    target_cpa_micros: int | None = None,
    status: str = "PAUSED",
) -> list[dict[str, object]]:
    if not 1 <= len(headlines) <= 5 or any(len(h) > 40 for h in headlines):
        raise InvalidOperation("headlines: 1 to 5, each 40 characters or fewer")
    if not 1 <= len(descriptions) <= 5 or any(len(d) > 90 for d in descriptions):
        raise InvalidOperation("descriptions: 1 to 5, each 90 characters or fewer")
    if not marketing_images_base64 or not square_images_base64:
        raise InvalidOperation("at least one landscape and one square image are required")
    if len(business_name) > 25:
        raise InvalidOperation("business_name over 25 characters")
    root = f"customers/{customer_id}"
    budget, campaign, group = (
        f"{root}/campaignBudgets/-1",
        f"{root}/campaigns/-2",
        f"{root}/adGroups/-3",
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
                    "advertising_channel_type": "DEMAND_GEN",
                    "campaign_budget": budget,
                    "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
                    "maximize_conversions": {"target_cpa_micros": str(target_cpa_micros)}
                    if target_cpa_micros
                    else {},
                }
            }
        },
        {
            "ad_group_operation": {
                "create": {
                    "resource_name": group,
                    "name": f"{name} ad group",
                    "campaign": campaign,
                    "status": "ENABLED",
                }
            }
        },
    ]
    for geo in geo_target_ids:
        ops.append(
            {
                "ad_group_criterion_operation": {
                    "create": {
                        "ad_group": group,
                        "location": {"geo_target_constant": f"geoTargetConstants/{geo}"},
                    }
                }
            }
        )
    for language in language_ids:
        ops.append(
            {
                "ad_group_criterion_operation": {
                    "create": {
                        "ad_group": group,
                        "language": {"language_constant": f"languageConstants/{language}"},
                    }
                }
            }
        )
    next_id = [-10]

    def image(label: str, data: str) -> str:
        resource = f"{root}/assets/{next_id[0]}"
        next_id[0] -= 1
        ops.append(
            {
                "asset_operation": {
                    "create": {
                        "resource_name": resource,
                        "name": f"{name} {label}",
                        "image_asset": {"data": data},
                    }
                }
            }
        )
        return resource

    logo = image("logo", logo_base64)
    landscape = [image(f"image {i + 1}", d) for i, d in enumerate(marketing_images_base64)]
    square = [image(f"square {i + 1}", d) for i, d in enumerate(square_images_base64)]
    ops.append(
        {
            "ad_group_ad_operation": {
                "create": {
                    "ad_group": group,
                    "status": "ENABLED",
                    "ad": {
                        "name": f"{name} ad",
                        "final_urls": [final_url],
                        "demand_gen_multi_asset_ad": {
                            "business_name": business_name,
                            "headlines": [{"text": h} for h in headlines],
                            "descriptions": [{"text": d} for d in descriptions],
                            "logo_images": [{"asset": logo}],
                            "marketing_images": [{"asset": a} for a in landscape],
                            "square_marketing_images": [{"asset": a} for a in square],
                        },
                    },
                }
            }
        }
    )
    return ops


def build_experiment(
    *,
    customer_id: str,
    name: str,
    base_campaign_id: str,
    treatment_traffic_percent: int = 50,
    suffix: str = "[experiment]",
    experiment_type: str = "SEARCH_CUSTOM",
) -> list[dict[str, object]]:
    if not 1 <= treatment_traffic_percent <= 99:
        raise InvalidOperation("treatment_traffic_percent must be between 1 and 99")
    root = f"customers/{customer_id}"
    experiment = f"{root}/experiments/-1"
    return [
        {
            "experiment_operation": {
                "create": {
                    "resource_name": experiment,
                    "name": name,
                    "suffix": suffix,
                    "type_": experiment_type,
                    "status": "SETUP",
                }
            }
        },
        {
            "experiment_arm_operation": {
                "create": {
                    "experiment": experiment,
                    "name": f"{name} control",
                    "control": True,
                    "traffic_split": 100 - treatment_traffic_percent,
                    "campaigns": [f"{root}/campaigns/{base_campaign_id}"],
                }
            }
        },
        {
            "experiment_arm_operation": {
                "create": {
                    "experiment": experiment,
                    "name": f"{name} treatment",
                    "control": False,
                    "traffic_split": treatment_traffic_percent,
                }
            }
        },
    ]
