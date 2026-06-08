# Quantum ADS — tool catalog (SP0)

All tools are **read-only** in SP0 and return structured dicts.

## Meta (dynamic discovery)
- `health` → `{api_version, days_until_sunset, read_only[, warning]}`.
- `list_capabilities` → connectors + their tools (so a client need not preload everything).
- `describe_tool(name)` → one tool's spec, or `{error: UNKNOWN_TOOL}`.

## Google Ads — reads
- `ads.gaql.query(customer_id, query)` → `{rows, row_count}` or `{error: GAQL_INVALID}`. Raw GAQL,
  validated pre-flight (single FROM, no OR, segment-in-SELECT, 37-month cap), streamed, flattened
  to dotted keys (`campaign.id`, `metrics.clicks`).
- `ads.report.campaign(customer_id, date_range="LAST_7_DAYS")` → campaign perf (impr/clicks/cost/conv).
- `ads.report.search_terms(...)` → search terms incl. `segments.search_term_match_source` (AI Max).
- `ads.report.pmax_asset_groups(...)` → Performance Max asset groups (channel-type filtered).
- `ads.report.ai_max(...)` → `matched_location_interest_view` (AI Max geo-interest).
- `ads.report.conversions(...)` → conversions by conversion date.
- `ads.change_history(customer_id, mode="audit"|"delta", date_range, limit≤10000)` →
  `change_event` (field-level audit, 30d) or `change_status` (delta sync, 90d).
- `ads.fields.deltas()` → curated v24 2026 new views/metrics/segments + removed fields.
- `ads.fields.new_views()` → the new 2026 reporting view names.

`date_range` is restricted to an allowlist (TODAY, YESTERDAY, LAST_7/14/30_DAYS, THIS_MONTH,
LAST_MONTH, LAST_BUSINESS_WEEK) — anything else returns `{error: BAD_DATE_RANGE}`.
