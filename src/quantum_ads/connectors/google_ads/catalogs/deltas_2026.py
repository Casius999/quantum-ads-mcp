"""Curated Google Ads API 2026 deltas (v22 -> v26), so the model knows the new surface.

Sources: developers.google.com/google-ads release notes + field references (v24 notes June 2026;
v25/v26 notes read 2026-11-01). For the exhaustive, version-exact structural diff use
``catalogs.version_delta.compute_version_delta`` (computed from the installed SDK protos).
This is a hand-maintained summary; the live field metadata is fetched via GoogleAdsFieldService.
"""

from __future__ import annotations

NEW_VIEWS_2026: list[str] = [
    "per_store_view",
    "matched_location_interest_view",
    "cart_data_sales_view",
    "targeting_expansion_view",
    "expanded_landing_page_view",
    "ai_max_search_term_ad_combination_view",
    "video_enhancement",
    "app_top_combination_view",
]

NEW_METRIC_FAMILIES_2026: list[str] = [
    "experiment significance: metrics.*_point_estimate / *_margin_of_error / *_p_value",
    "reach: metrics.unique_users_two_plus ... unique_users_ten_plus",
    "profit/cross-sell: metrics.gross_profit_micros, cost_of_goods_sold_micros, cross_sell_*",
    "video (renamed): metrics.trueview_average_cpv, video_trueview_views, video_trueview_view_rate",
    "auction insights: metrics.auction_insight_search_impression_share, ...",
]

NEW_SEGMENT_FAMILIES_2026: list[str] = [
    "segments.search_term_match_source (AI_MAX_KEYWORDLESS, AI_MAX_BROAD_MATCH)",
    "segments.vertical_ads_* (Travel/hotel/event/listing)",
    "segments.mobile_device_platform (iOS/Android)",
    "segments.conversion_attribution_event_type",
    "segments.product_sold_* (cross-sell, with cart_data_sales_view)",
]

REMOVED_FIELDS_2026: list[str] = [
    "segments.ad_sub_network_type removed from campaign_budget (v24)",
    "segments.click_type removed from AdGroupAsset/CampaignAsset/CustomerAsset (v24)",
    "AssetPerformanceLabel aggregate metrics removed (PMax v22, Search/Display v23)",
    "video metrics average_cpv/video_views/video_view_rate renamed to trueview_* (v22)",
    "CustomerLifecycleGoal/CampaignLifecycleGoal resources + services removed; use Goal."
    "new_customer_acquisition_goal_settings / CampaignGoalConfig (v25)",
    "CustomerAcquisitionOptimizationModeEnum, LifecycleGoalValueSettings removed (v25)",
    "Incentive.type / IncentiveOffer.type -> standalone incentive_type / offer_type (v25)",
    "LocalServicesLead.contact_details.email removed (v25)",
    "Customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled removed; "
    "use enablement_setting (v26)",
    "AdGroupBidModifier hotel_* criteria -> vertical-agnostic user_set_dates / "
    "advance_booking_window / length_of_booking / start_day_of_week / start_date_range (v26)",
    "HotelDateSelectionType -> DateSelectionType for segments.user_set_dates (v26)",
]

# New resources/services that reached the API in v25-v26 (structural, from the SDK protos).
NEW_RESOURCES_V25_V26: list[str] = [
    "lift_measurement_config / lift_measurement_campaign / lift_measurement_flight "
    "(Brand, Conversion and Search Lift studies via the API)",
    "lift_measurement_age_range / _gender / _device / _video (lift breakdowns)",
    "search_lift_keyword_bundle",
    "customer_budget_network_setting (+ CampaignBudget.budget_network_settings: waterfall "
    "channel prioritization and secondary-tier budget caps, v26.1)",
    "LocalServicesEligibilityService",
]
