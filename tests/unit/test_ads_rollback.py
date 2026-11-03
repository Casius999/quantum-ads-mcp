"""Undo for Google Ads mutations: masks, before-state queries, inverse operations."""

from __future__ import annotations

from quantum_ads.connectors.google_ads.write.operations import validate_operations
from quantum_ads.connectors.google_ads.write.rollback import (
    before_state_query,
    created_names,
    inverse_of_creates,
    inverse_of_update,
    mask_paths,
    resource_of,
    with_update_masks,
)
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION as V

_CAMPAIGN = "customers/1/campaigns/2"


def test_missing_update_masks_are_derived_from_the_update():
    ops = [
        {
            "campaign_operation": {
                "update": {
                    "resource_name": _CAMPAIGN,
                    "status": "PAUSED",
                    "network_settings": {"target_search_network": False},
                }
            }
        },
        {"campaign_operation": {"create": {"name": "x"}}},
    ]
    filled = with_update_masks(ops)
    assert (
        filled[0]["campaign_operation"]["update_mask"]
        == "status,network_settings.target_search_network"
    )
    assert filled[1] == ops[1]
    validate_operations(filled[:1], V)


def test_explicit_masks_are_kept_and_parsed():
    body = {"update": {"resource_name": _CAMPAIGN, "name": "n"}, "update_mask": "name"}
    assert with_update_masks([{"campaign_operation": body}])[0]["campaign_operation"] is body
    assert mask_paths(body) == ["name"]
    assert mask_paths({"update_mask": {"paths": ["a", "b"]}}) == ["a", "b"]


def test_before_state_query_and_inverse_update():
    assert resource_of("campaign_criterion_operation") == "campaign_criterion"
    query = before_state_query(
        "campaign_operation", _CAMPAIGN, ["status", "network_settings.target_search_network"]
    )
    assert query.startswith(
        "SELECT campaign.resource_name, campaign.status, campaign.network_settings"
    )
    assert f"WHERE campaign.resource_name = '{_CAMPAIGN}'" in query
    row = {
        "campaign": {
            "resource_name": _CAMPAIGN,
            "status": "ENABLED",
            "network_settings": {"target_search_network": True},
        }
    }
    inverse = inverse_of_update(
        "campaign_operation", _CAMPAIGN, ["status", "network_settings.target_search_network"], row
    )
    body = inverse["campaign_operation"]
    assert body["update"] == {
        "resource_name": _CAMPAIGN,
        "status": "ENABLED",
        "network_settings": {"target_search_network": True},
    }
    assert body["update_mask"] == "status,network_settings.target_search_network"
    validate_operations([inverse], V)


def test_unset_field_is_cleared_by_the_mask():
    inverse = inverse_of_update(
        "campaign_operation", _CAMPAIGN, ["tracking_url_template"], {"campaign": {}}
    )
    assert inverse["campaign_operation"]["update"] == {"resource_name": _CAMPAIGN}
    assert inverse["campaign_operation"]["update_mask"] == "tracking_url_template"


def test_creates_are_undone_by_removing_what_was_created():
    response = {
        "mutate_operation_responses": [
            {"campaign_budget_result": {"resource_name": "customers/1/campaignBudgets/7"}},
            {"campaign_criterion_result": {"resource_name": "customers/1/campaignCriteria/2~9"}},
        ]
    }
    created = created_names(response)
    assert created == [
        ("campaign_budget_operation", "customers/1/campaignBudgets/7"),
        ("campaign_criterion_operation", "customers/1/campaignCriteria/2~9"),
    ]
    removes = inverse_of_creates(
        "campaign_criterion_operation", ["customers/1/campaignCriteria/2~9"]
    )
    validate_operations(removes, V)


def test_masks_accept_snake_camel_and_lists():
    body = {
        "update": {"resource_name": _CAMPAIGN},
        "update_mask": "networkSettings.targetSearchNetwork",
    }
    assert mask_paths(body) == ["network_settings.target_search_network"]
    for mask in (
        "network_settings.target_search_network",
        ["network_settings.target_search_network"],
    ):
        op = {"campaign_operation": {"update": {"resource_name": _CAMPAIGN}, "update_mask": mask}}
        validate_operations([op], V)
