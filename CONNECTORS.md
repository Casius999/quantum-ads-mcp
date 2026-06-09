# Connectors

19 product connectors on the shared core. Each exposes **read** tools and (where the product
supports mutation) **guarded write** tools — write tools take a `confirm` arg and run
`validate_only` preview → two-step confirm → signed audit via the core `WriteExecutor`.

Each connector reaches its API through a named **backend** (`ctx.backend("<key>")`). Backends are
wired at server assembly; until wired, a tool degrades to `{"error": {"code":
"BACKEND_NOT_CONFIGURED", ...}}`. The live SDK glue lives in each connector's `sdk.py`
(smoke-gated, not unit-tested). Enable a subset with `QUANTUM_ADS_CONNECTORS`.

| Connector | Key tools | Backend keys | Live SDK package |
|-----------|-----------|--------------|------------------|
| **google_ads** | `ads.gaql.query`, `ads.report.{campaign,search_terms,pmax_asset_groups,ai_max,conversions}`, `ads.change_history`, `ads.fields.*`, `ads.campaign.set_status`, `ads.budget.update` | `stream_factory`, `mutate_factory` | `google-ads` (31) |
| **ga4** | `ga4.report`, `ga4.realtime`, `ga4.admin.list_properties/list_data_streams/list_key_events`, `ga4.admin.create_key_event/create_audience` | `ga4.data`, `ga4.admin`, `ga4.admin.mutate` | `google-analytics-data`, `google-analytics-admin` |
| **gtm** | `gtm.list_{accounts,containers,workspaces,tags,triggers,variables,versions}`, `gtm.create_tag`, `gtm.update_tag`, `gtm.create_version`, `gtm.publish_version` | `gtm.api`, `gtm.mutate` | `google-api-python-client` (tagmanager v2) |
| **merchant** | `merchant.products.list`, `merchant.product.get`, `merchant.product_statuses.list`, `merchant.accounts.get`, `merchant.product.insert/update/delete` | `merchant.api`, `merchant.mutate` | `google-shopping-merchant-products/-accounts` |
| **datamanager** | `datamanager.audience.upload_members/remove_members`, `datamanager.conversions.upload`, `datamanager.status` | `datamanager.api`, `datamanager.read` | `google-api-python-client` (datamanager v1) |
| **searchconsole** | `searchconsole.search_analytics`, `searchconsole.sites.list`, `searchconsole.sitemaps.list`, `searchconsole.url_inspect`, `searchconsole.sitemaps.submit/delete` | `searchconsole.api`, `searchconsole.mutate` | `google-api-python-client` (webmasters v3 + searchconsole v1) |
| **youtube** | `youtube.channel.get`, `youtube.videos.list`, `youtube.video.batch_stats`, `youtube.playlist_items.list`, `youtube.analytics.query`, `youtube.reporting.ensure_jobs`, `youtube.video.update`, `youtube.playlist.add_item` | `youtube.data`, `youtube.analytics`, `youtube.mutate` | `google-api-python-client` (youtube v3 / youtubeAnalytics v2 / youtubereporting v1) |
| **dv360** | `dv360.advertisers.list`, `dv360.campaigns.list`, `dv360.insertion_orders.list`, `dv360.line_items.list`, `dv360.line_item.update/set_status` | `dv360.api`, `dv360.mutate` | `google-api-python-client` (displayvideo v4) |
| **cm360** | `cm360.user_profiles.list`, `cm360.campaigns.list`, `cm360.placements.list`, `cm360.reports.list`, `cm360.report.run`, `cm360.floodlight_activities.list`, `cm360.placement.update`, `cm360.report.insert` | `cm360.api`, `cm360.mutate` | `google-api-python-client` (dfareporting v4) |
| **sa360** | `sa360.search`, `sa360.customers.list_accessible`, `sa360.report.campaign/ad_group`, `sa360.conversion.upload` | `sa360.api`, `sa360.mutate` | `google-api-python-client` (searchads360 v0) |
| **bigquery** | `bigquery.datasets.list`, `bigquery.tables.list`, `bigquery.query.dry_run` (cost estimate), `bigquery.query.run` (max_bytes_billed ceiling), `bigquery.dataset.create`, `bigquery.table.create` | `bigquery.api`, `bigquery.mutate` | `google-cloud-bigquery` |
| **vertex** | `vertex.gemini.generate`, `vertex.imagen.generate`, `vertex.veo.generate`, `vertex.gemini.generate_ad_copy` | `vertex.api` | `google-cloud-aiplatform` (`vertexai`) |
| **trends** | `trends.interest_over_time`, `trends.related_queries`, `trends.trending_now`, `trends.interest_by_region` | `trends.api` | `pytrends` (unofficial) |
| **gbp** | `gbp.accounts.list`, `gbp.locations.list`, `gbp.location.get`, `gbp.performance.fetch`, `gbp.reviews.list` (allowlist), `gbp.review.reply`, `gbp.location.update` | `gbp.api`, `gbp.reviews`, `gbp.mutate` | `google-api-python-client` (mybusiness v1 + v4 reviews) |
| **looker** | `looker.dashboards.list`, `looker.looks.list`, `looker.look.run`, `looker.query.run`, `looker.dashboard.create` | `looker.api`, `looker.mutate` | `looker_sdk` |
| **meridian** | `meridian.model.summary`, `meridian.roi.by_channel`, `meridian.budget.optimize`, `meridian.fit` | `meridian.api` | `google-meridian` |
| **language** | `language.translate`, `language.detect_language`, `language.analyze_sentiment`, `language.analyze_entities`, `language.batch_translate` | `language.api` | `google-cloud-translate`, `google-cloud-language` |
| **workspace** | `workspace.drive.list_files`, `workspace.sheets.read_range`, `workspace.sheets.get_metadata`, `workspace.sheets.write_range`, `workspace.sheets.create`, `workspace.slides.create_deck` | `workspace.api`, `workspace.mutate` | `google-api-python-client` (sheets v4 / drive v3 / slides v1) |
| **recaptcha** | `recaptcha.keys.list`, `recaptcha.assessment.create` (lead-quality risk score), `recaptcha.assessment.annotate` | `recaptcha.api`, `recaptcha.mutate` | `google-cloud-recaptcha-enterprise` |

## Excluded (verified, June 2026)

- **Privacy Sandbox** (Topics / Attribution Reporting / Protected Audience) — retired October 2025.
- **Google Ads Editor** — desktop app, no API.
- **Google Partners** — portal, no API.

## Dated migration notes

- Google Ads conversion upload via the Ads API is **blocked since 2026-06-15** → use the **Data Manager** connector.
- **Content API for Shopping sunsets 2026-08-18** → the Merchant connector targets the **Merchant API**.
- DV360 v4 added Demand Gen on **2026-06-10** → the DV360 connector applies unknown-enum tolerance.
