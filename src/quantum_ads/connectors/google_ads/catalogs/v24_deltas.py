"""Curated Google Ads API v24 (2025-2026) deltas, so the model knows the new surface.

Sources: developers.google.com/google-ads release notes + field references (June 2026).
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
]
