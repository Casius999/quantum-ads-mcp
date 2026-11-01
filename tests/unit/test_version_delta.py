"""compute_version_delta reads the installed google-ads SDK protos (offline, no token)."""

from quantum_ads.connectors.google_ads.catalogs.version_delta import (
    compute_version_delta,
    supported_versions,
)
from quantum_ads.core.versioning.version_manager import DEFAULT_API_VERSION, SUNSET_SCHEDULE


def test_pinned_default_is_supported_by_sdk_and_has_a_sunset_date():
    assert DEFAULT_API_VERSION in supported_versions()
    assert DEFAULT_API_VERSION in SUNSET_SCHEDULE


def test_v24_to_v26_delta_matches_official_breaking_changes():
    delta = compute_version_delta("v24", "v26")
    resources = delta["resources"]
    services = delta["services"]
    assert isinstance(resources, dict) and isinstance(services, dict)
    # v25 removed the legacy lifecycle goal resources + services (official upgrade guide).
    assert {"campaign_lifecycle_goal", "customer_lifecycle_goal"} <= set(resources["removed"])
    assert "customer_lifecycle_goal_service" in services["removed"]
    # v25/v26 added the lift-measurement family and the budget network settings.
    assert {"lift_measurement_config", "customer_budget_network_setting"} <= set(resources["added"])


def test_identity_delta_is_empty():
    delta = compute_version_delta(DEFAULT_API_VERSION, DEFAULT_API_VERSION)
    for kind in ("resources", "enums", "common", "services"):
        assert delta[kind] == {"added": [], "removed": []}


def test_unknown_version_returns_structured_error():
    out = compute_version_delta("v24", "v99")
    assert out["error"]["code"] == "UNSUPPORTED_VERSION"
