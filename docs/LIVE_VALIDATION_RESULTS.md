# Live Validation Results

Real-API conformance of every reachable connector, run against live Google endpoints with a
broad-scope OAuth token (since revoked). The suite lives under `tests/live_smoke/` and runs with
`uv run pytest -m live`. It performs **reads and `validate_only` previews only** — no account is
mutated, no billable generation is invoked.

**Last live run:** 32 passed · 6 skipped · 0 failed.
**Discovery conformance:** 12/12 surfaces pass (account-free, token-free API-contract check).
**Wired, runs on the next re-consent:** merchant, vertex, and the dv360/cm360/sa360/adh/gbp
reachability suites.

Legend: ✅ live-green (real round-trip) · 🟢 contract-conformant + reachability-ready · 🟡 wired,
pending a re-consent token · 🚫 blocked by an external prerequisite · ⚪ code-complete only.

> Every "skipped" below is an honest gap (a missing owned resource, an un-granted scope, or a
> non-existent endpoint) — never a silenced failure. Each `validate_only` mutate short-circuits to a
> server-side-free preview before any write call.

## Per-connector status

| Connector | Surface | Status | Notes |
|-----------|---------|--------|-------|
| google_ads | GAQL reads, 5 reports, change history, budget/campaign `validate_only` | ✅ live-green | |
| ga4 | Data API (runReport), Admin API (properties/streams/key events), `validate_only` create | ✅ live-green | |
| bigquery | datasets.list, query.dry_run, query.run, dataset `validate_only` | ✅ live-green | tables.list skipped (no dataset in project) |
| language | translate, detect, sentiment, entities, batch_translate | ✅ live-green | Cloud Translation + Natural Language |
| gtm | list_accounts, list_containers, tag `validate_only` | ✅ live-green | reads on `tagmanager.readonly` |
| youtube | Data API: videos.list (bulk via comma-separated ids), channels.get, update `validate_only` | ✅ live-green | analytics surface needs `yt-analytics.readonly` (not in token) |
| searchconsole | sites.list, sitemap submit `validate_only` | ✅ live-green | searchAnalytics + sitemaps.list skipped (token owns no Search Console property) |
| trends | interest_over_time | ✅ live-green | pytrends is unofficial + rate-limited; trending_now skipped on endpoint drift |
| recaptcha | keys.list, annotate `validate_only` | ✅ live-green | assessment.create needs a real site key + frontend token |
| merchant | Merchant API products/accounts + insert `validate_only` | 🟡 wired, runs on re-consent | SDK now installed (clean resolve) + `quota_project_id` routed; owner holds the account. Needs `merchantapi` enabled. |
| vertex | Gemini micro-generation (Imagen/Veo excluded) | 🟡 wired, runs on re-consent | OAuth + quota auth wired (was a broken implicit ADC). One **billable** Gemini Flash call (opt-in). |
| dv360 | advertisers/campaigns/lineItems + `validate_only` | 🟢 contract-conformant · reachability-ready | method surface verified vs live discovery; no no-account list (needs a partner id) |
| cm360 | userProfiles/campaigns/placements/reports + `validate_only` | 🟢 contract-conformant · reachability-ready | `userProfiles.list` runs empty without a CM360 account |
| sa360 | search + listAccessible + conversion `validate_only` | 🟢 contract-conformant · reachability-ready | `customers.listAccessible` runs empty without an SA360 account |
| adh | customers/queries + create `validate_only` | 🟢 contract-conformant · reachability-ready | `customers.list` runs empty without an ADH account |
| gbp | accounts/locations/performance + `validate_only` | 🟢 contract-conformant · reachability-ready | `accounts.list` runs empty for a personal account with no listing |
| datamanager | audience/conversion uploads | ⚪ code-complete | needs the Data Manager grant + an Ads data partner |
| workspace | Admin SDK | 🚫 needs a Workspace org | a personal @gmail account cannot grant admin scopes |
| looker | Looker instance | 🚫 needs a Looker instance | paid Looker (Google Cloud core) instance + API3 creds |
| meridian | MMM library (local) | 🟡 isolated-venv validation | heavy TensorFlow/tfp-nightly stack; validate in a throwaway venv (not a shared extra) |

## Bugs found by live testing (and fixed)

Each connector's SDK glue is the one layer unit tests can't prove — these only surfaced against the
real APIs:

1. **google_ads** — `mutate_campaigns` / `mutate_campaign_budgets` reject a flattened
   `validate_only=` kwarg; must set it on the `Mutate*Request` object.
2. **google_ads** — `execute_query` only caught `GaqlError`; a live API/transport error would crash
   the tool. Now returns a structured error (tool boundary never throws).
3. **ga4** — `list_properties` takes a `ListPropertiesRequest`, not a `filter=` kwarg.
4. **ga4** — `Audience` / `KeyEvent` are not under `admin_v1beta.types`; lazy-import on the
   real-create path (which `validate_only` skips).
5. **quota routing (ga4, bigquery, language, gtm, searchconsole, youtube, recaptcha)** — GCP API
   calls made with user-OAuth creds bill quota to the **OAuth client's** project by default, where
   the target APIs aren't enabled (`SERVICE_DISABLED` / `accessNotConfigured`). Now every connector
   threads `quota_project_id` so the call bills the project where the APIs are enabled.
6. **bigquery** — requesting the narrow `.../auth/bigquery` scope fails `invalid_scope` when the
   token was granted the `cloud-platform` umbrella; switched to `cloud-platform`. Also guarded
   `project=` against the `str(None) -> "None"` pitfall.
7. **language** — both clients were built with **no credentials** (implicit ADC) while the connector
   passes an OAuth user-creds dict → `DefaultCredentialsError`. Now build and pass
   `google.oauth2.credentials.Credentials`.
8. **gtm** — the read plane pinned `tagmanager.edit.containers` and failed `invalid_scope` for a
   read-only token; reads now ride `tagmanager.readonly`, edit/publish ride the edit scope.
9. **youtube** — `videos.batchGetStats` was a non-existent Data API v3 method; **removed**. The
   bulk-statistics path is `videos.list` with a comma-separated id list (1 unit for up to 50 ids).
10. **sa360** — `conversions.ingest` does not exist on the `searchads360` v0 Reporting API (it is
    read-only). SA360 conversion upload lives on the `doubleclicksearch` v2 API as
    `conversion.insert`; the mutate plane now targets that API. Found by discovery conformance.

## API-contract conformance (no account, no token, no cost)

`tests/live_smoke/test_discovery_conformance.py` validates every discovery-based connector's method
surface against Google's actual API contract: it loads each API's discovery document — the one
google-api-python-client bundles, i.e. exactly what the connector loads at runtime — and asserts that
every method the connector calls exists. **12/12 surfaces pass** (dv360, cm360, sa360 reporting +
conversions, adh, gtm, Search Console webmasters + URL inspection, youtube, and the three GBP hosts).

This is the layer that needs no enterprise account, token, or spend: it proves a connector targets
real endpoints even where we cannot own the data. It is what caught both non-existent-endpoint bugs
(youtube `videos.batchGetStats` and sa360 `conversions.ingest`).

## Reproducing

```bash
# 1. Mint a broad-scope OAuth token (one human consent click) into the gitignored .env
uv run python scripts/get_refresh_token.py
# 2. Enable the required APIs in the quota project (Service Usage batchEnable)
# 3. Run the live suite
uv run pytest -m live tests/live_smoke -q
```

Credentials live only in the gitignored `.env`; the validation token used to produce this report
was revoked afterward.
