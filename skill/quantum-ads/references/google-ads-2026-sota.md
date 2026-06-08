# Google Ads API — SOTA state, June 2026

> Releases are monthly since Jan 2026 — cross-check live:
> https://developers.google.com/google-ads/api/docs/release-notes ·
> https://developers.google.com/google-ads/api/docs/sunset-dates

## Versions
| Version | Status (June 2026) |
|---|---|
| v24 (.1 = current) | newest — server default |
| v23 / v22 | supported |
| v21 and earlier | deprecated/sunset |
| **v19** | sunset 2026-02-11 |
| **v20** | sunset 2026-06-10 |

Library: **google-ads 31.0.0** (Python ≥ 3.9). ~4 majors live; ~12-month support each.

## Three API planes (an agency control plane needs all three)
1. **Google Ads API v24** — campaigns, config, reporting (GAQL). *(SP0 = reads.)*
2. **Data Manager API** (`datamanager.googleapis.com`) — Customer Match + offline/enhanced
   conversions. Ads-API upload blocked (Customer Match 2026-04-01; conversions **2026-06-15**). *(SP2.)*
3. **Merchant API** (`merchantapi.googleapis.com` v1) — Shopping catalog; **Content API sunsets 2026-08-18**. *(SP3.)*

## New v24 surface (curated)
- **AI Max for Search** (DSA auto-upgrade from Sept 2026); views `matched_location_interest_view`,
  `targeting_expansion_view`, `expanded_landing_page_view`, `ai_max_search_term_ad_combination_view`;
  `segments.search_term_match_source` (AI_MAX_KEYWORDLESS / AI_MAX_BROAD_MATCH).
- **Performance Max** — engagement metrics on asset_group; steering/reporting 2026.
- **Reporting views** — `per_store_view`, `cart_data_sales_view`, `video_enhancement`, `app_top_combination_view`.
- **Metrics/segments** — experiment significance (`*_point_estimate/_margin_of_error/_p_value`),
  reach `unique_users_*_plus`, profit/cross-sell, `mobile_device_platform`, `conversion_attribution_event_type`.
- **Removed** — `segments.ad_sub_network_type` (from campaign_budget), `segments.click_type` (from
  *Asset), AssetPerformanceLabel aggregates, old video metrics (renamed to `trueview_*`).

## Excluded from the platform (verified)
Privacy Sandbox (retired Oct 2025) · Google Ads Editor (no API) · Google Partners (portal).
