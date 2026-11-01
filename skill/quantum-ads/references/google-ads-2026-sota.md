# Google Ads API — SOTA state, November 2026

> Cross-check live before pinning:
> https://developers.google.com/google-ads/api/docs/release-notes ·
> https://developers.google.com/google-ads/api/docs/sunset-dates

## Versions
| Version | Released | Sunset |
|---|---|---|
| **v26** (server default) | 2026-10-14 | 2027-11 |
| v25 | 2026-07-22 | 2027-08 |
| v24 | 2026-04-22 | 2027-05 |
| v23 | — | 2027-02 |
| v22 and earlier | — | sunset |

Library: **google-ads 35.0.0** (bundles v23–v26). Override with `GOOGLE_ADS_API_VERSION`.
`ads.api.version_delta(from_version, to_version)` diffs resources, enums, common types and services
between any two bundled versions, computed from the installed SDK — use it before migrating.

## Three API planes (an agency control plane needs all three)
1. **Google Ads API v26** — campaigns, config, reporting (GAQL). Connector `google_ads`.
2. **Data Manager API** (`datamanager.googleapis.com` v1) — Customer Match + offline/enhanced
   conversions; uploads through the Ads API are blocked (Customer Match 2026-04-01, conversions
   2026-06-15). Connector `datamanager`.
3. **Merchant API** (`merchantapi.googleapis.com` v1) — Shopping catalog; the Content API for
   Shopping sunset on 2026-08-18. Connector `merchant`.

## v25 / v26 changes that bite
- **Lifecycle goals removed (v25):** `CustomerLifecycleGoal` / `CampaignLifecycleGoal` and their
  services are gone — use `Goal.new_customer_acquisition_goal_settings` / `CampaignGoalConfig`.
- **Incentives (v25):** `Incentive.type` / `IncentiveOffer.type` → `incentive_type` / `offer_type`;
  `LocalServicesLead.contact_details.email` removed.
- **Enhanced conversions for leads (v26):** the boolean on `conversion_tracking_setting` is
  removed — use `enablement_setting`.
- **Travel bid modifiers (v26):** hotel-only `AdGroupBidModifier` criteria become
  vertical-agnostic (`user_set_dates`, `advance_booking_window`, `length_of_booking`,
  `start_day_of_week`, `start_date_range`); `HotelDateSelectionType` → `DateSelectionType`.
- **New (v25–v26):** lift measurement (`lift_measurement_config/_campaign/_flight` + age, gender,
  device and video breakdowns), `search_lift_keyword_bundle`, `customer_budget_network_setting`
  (+ `CampaignBudget.budget_network_settings`: waterfall channel prioritization, v26.1),
  `LocalServicesEligibilityService`.

## 2026 surface still current from v24
- **AI Max for Search** — views `matched_location_interest_view`, `targeting_expansion_view`,
  `expanded_landing_page_view`, `ai_max_search_term_ad_combination_view`;
  `segments.search_term_match_source` (AI_MAX_KEYWORDLESS / AI_MAX_BROAD_MATCH).
- **Reporting views** — `per_store_view`, `cart_data_sales_view`, `video_enhancement`,
  `app_top_combination_view`.
- **Metrics/segments** — experiment significance (`*_point_estimate/_margin_of_error/_p_value`),
  reach `unique_users_*_plus`, profit/cross-sell, `mobile_device_platform`,
  `conversion_attribution_event_type`; video metrics renamed `trueview_*`.
- `ads.fields.deltas` / `ads.fields.new_views` return this curated list; the GAQL fields the
  server generates are checked against the v24 and v26 protos in CI.

## Excluded from the platform (verified)
Privacy Sandbox (retired Oct 2025) · Google Ads Editor (no API) · Google Partners (portal).
