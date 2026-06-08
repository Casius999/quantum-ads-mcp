# GAQL recipes & payload patterns

## Raw query
```
ads.gaql.query(customer_id="1234567890",
               query="SELECT campaign.name, metrics.clicks, metrics.cost_micros "
                     "FROM campaign WHERE segments.date DURING LAST_7_DAYS "
                     "ORDER BY metrics.cost_micros DESC")
```
- `customer_id`: any format (dashes stripped server-side).
- Rows come back flattened: `{"campaign.name": ..., "metrics.cost_micros": ...}`.

## Validator rules (enforced before any API call)
- Exactly one FROM resource (no JOINs).
- No `OR` — use `IN(...)`.
- A non-date segment in WHERE must also be in SELECT; date segments (date/week/month/quarter/year) are exempt.
- Date literals can't exceed the **37-month** lookback cap (effective 2026-06-01).

## High-value queries
Search terms isolating AI Max:
```
SELECT search_term_view.search_term, segments.search_term_match_source,
       metrics.clicks, metrics.conversions, metrics.cost_micros
FROM search_term_view WHERE segments.date DURING LAST_14_DAYS
```
PMax asset groups:
```
SELECT campaign.name, asset_group.name, metrics.conversions_value
FROM asset_group
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND segments.date DURING LAST_14_DAYS
```
Change audit (change_event):
```
SELECT change_event.change_date_time, change_event.user_email,
       change_event.change_resource_type, change_event.resource_change_operation
FROM change_event WHERE change_event.change_date_time DURING LAST_7_DAYS
ORDER BY change_event.change_date_time DESC LIMIT 10000
```

## Units / freshness
- `*_micros` ÷ 1,000,000 = account currency (keep as int until display).
- Dates/`segments.hour` are in the **account** time zone, not UTC.
- Recent days keep changing as conversions mature (click-through up to 30d) — re-pull trailing
  30-90 day windows; prefer `*_by_conversion_date` for true period ROAS.
