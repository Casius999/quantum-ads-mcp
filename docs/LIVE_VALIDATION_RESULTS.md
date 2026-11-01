# Live Validation Results

Real-API conformance of every reachable connector, run against live Google endpoints with a
broad-scope OAuth token. The suite lives under `tests/live_smoke/` and runs with
`uv run pytest -m live`. It performs **reads and `validate_only` previews** — no account is
mutated. The only billable calls are one short Gemini text and one Gemini image generation
(a few cents); Veo video generation is opt-in (`VERTEX_LIVE_VEO=1`, several USD per clip).

## 2026-11-01 — Google Ads v26 live, OAuth 2.1 HTTP, free video (current)

| Check | Result |
|-------|--------|
| Live suite (`pytest -m live`) | **61 passed · 9 skipped · 0 failed** |
| Google Ads API **v26** live (`ListAccessibleCustomers`, GAQL customer + campaign reads, standard + feature reports, change history, `budget.update` validate_only) | **7 passed**, 1 skip (no campaign in the account to validate `set_status` against) |
| Google Ads through the shipped stdio server | `health` → v26 / 365 days; `ads.gaql.query` returns real customer rows |
| OAuth 2.1 HTTP transport (real uvicorn server + real MCP client) | 11/11: no token / forged / expired / wrong audience / missing scope → 401; tenant isolation; unknown tenant refused; read scope cannot write; write scope runs the guarded flow and audits `tenant:subject`; external IdP JWKS + RFC 9728 metadata; single-tenant mode |
| Free text-to-video (`video.generate`) | clips generated with the same Spaces + arguments (Wan 2.2: 832x480, 3 s in 33 s; LTX-Video: 704x512, 3 s in 12 s); live test skips when the free daily ZeroGPU quota is spent — observed today after those clips, reported by the tool as `QUOTA_EXHAUSTED` |
| Unit / integration (`-m "not live"`) | 574 passed, mypy --strict clean |

The 9 skips: Google Ads `set_status` (no campaign), 3 enterprise reads gated externally (ADH,
CM360, GBP — no account), BigQuery `tables.list` (no dataset), DV360 (no partner id), pytrends
endpoint drift, Veo (paid, opt-in), free video (daily quota spent).

What it took for Ads: the developer token's access level is bound to the Google Cloud project of
the OAuth client that first used it (`CLOUD_PROJECT_NOT_APPROVED_FOR_PRODUCTION` from any other
project). `scripts/get_refresh_token.py --ads` mints an Ads-only refresh token for that client
without touching the shared `GOOGLE_OAUTH_*` credential.

24. **remote / multi-tenant** — the 16 write connectors cached their `WriteExecutor` on first use,
    binding the first caller's backend for the process lifetime; harmless over single-operator
    stdio, a cross-tenant credential leak over HTTP. Executors are now built per call and every
    backend, the Ads client, the write guard and the audit actor resolve through the request
    principal (bug found while designing the HTTP transport, covered by the E2E isolation tests).

## 2026-11-01 refresh run

Stack: fastmcp 4.1.4 on the MCP Python SDK 2.3.0 (protocol revision 2026-07-28), Google Ads
API **v26** via google-ads 35.0.0, google-api-python-client 2.201, Vertex AI over pure REST.

| Check | Result |
|-------|--------|
| Live suite (`pytest -m live`) | **54 passed · 15 skipped · 0 failed** |
| Discovery conformance (13 API surfaces) | 13/13 |
| GAQL field conformance (offline, every queried field vs SDK protos) | v24 ✓ · v26 ✓ (27 fields) |
| Vertex catalog conformance (defaults listed + GA) | 3/3 |
| MCP protocol E2E (real client, full assembly) | 4/4 |
| Real stdio subprocess smoke | 128 tools served, `health` → v26, 365 days to sunset; non-Ads connectors served live through the entrypoint (bug 22); `audit.status` persistent (bug 23) |
| Unit / integration (`-m "not live"`) | 525 passed, mypy --strict clean |

The 15 skips: 8 Google Ads (no developer token in this environment), 3 enterprise reads that
reach the API but are gated externally (ADH, CM360, GBP — no account), BigQuery `tables.list`
(no dataset), DV360 `advertisers.list` (no partner id), pytrends endpoint drift, Veo (opt-in).

## Earlier runs

**June live run:** 32 passed · 6 skipped · 0 failed.
**Discovery conformance:** 13/13 surfaces pass (account-free, token-free API-contract check).
**Broad-token run (17 scopes granted, 8 further APIs enabled):** 0 failures. merchant, vertex, and
the dv360/cm360/sa360/adh/gbp reachability suites all ran — every `validate_only` contract passes and
every read either returns data or **skips as "reached the API, gated externally"** (no enterprise
account / a default quota of 0) — never a code failure. Two gates were then removed **programmatically**:
merchant via the Merchant API `developerRegistration:registerGcp` (registers the project with the
Merchant account), and vertex by migrating the Gemini path to the REST `global` endpoint — both are
now **live-green** (real round-trips).

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
| merchant | products/accounts + insert `validate_only` | ✅ live-green | GCP project registered with the Merchant account programmatically via the Merchant API `developerRegistration:registerGcp`; all three pass |
| vertex | Gemini text + image generation, Veo generate/poll (pure REST) | ✅ live-green | text `gemini-3.8-flash` and image `gemini-3.1-flash-image` round-trip for real; defaults verified GA in the live catalog; Veo 3.1 generate + `vertex.veo.status` polling is opt-in (cost) |
| dv360 | advertisers/campaigns/lineItems + `validate_only` | 🟢 contract-conformant · reachability-ready | method surface verified vs live discovery; no no-account list (needs a partner id) |
| cm360 | userProfiles/campaigns/placements/reports + `validate_only` | 🟢 contract-conformant · reachability-ready | `userProfiles.list` runs empty without a CM360 account |
| sa360 | search + listAccessible + conversion `validate_only` | 🟢 contract-conformant · reachability-ready | `customers.listAccessible` runs empty without an SA360 account |
| adh | customers/queries + create `validate_only` | 🟢 contract-conformant · reachability-ready | `customers.list` runs empty without an ADH account |
| gbp | accounts/locations/performance + `validate_only` | 🟢 contract-conformant · reachability-ready | `accounts.list` runs empty for a personal account with no listing |
| datamanager | audienceMembers/events ingest + request_status | 🟢 contract-conformant | method surface verified vs live discovery (caught + fixed 2 fictional methods); needs the Data Manager grant to run live |
| workspace | Admin SDK | 🚫 needs a Workspace org | a personal @gmail account cannot grant admin scopes |
| looker | Looker instance | 🚫 needs a Looker instance | paid Looker (Google Cloud core) instance + API3 creds |
| meridian | MMM library (local) | 🟢 library-surface validated | google-meridian installed in an isolated venv; the connector's imports/classes resolve (caught + fixed a fictional loader); a full MCMC fit is heavy + deferred |

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
11. **vertex** — two faults: the top-level `VideoGenerationModel` import crashed the factory (now
    lazy), and the deprecated `vertexai.generative_models` SDK could not reach Gemini 2.5 (served
    from the `global` endpoint the SDK does not target) — every model returned 404. The Gemini path
    was migrated to a direct REST `generateContent` call against the `global` endpoint (SOTA June
    2026; the vertexai SDK is removed 2026-06-24), which round-trips live.
12. **adh** — `build("adsdatahub", "v1")` raises `UnknownApiNameOrVersion` (adsdatahub is not in the
    bundled discovery set); pass `static_discovery=False` to fetch the live discovery document.
13. **gbp** — the mutate factory eagerly built the legacy `mybusiness` v4 client (dead discovery →
    `UnknownApiNameOrVersion`), breaking the v1 location-update `validate_only`. The v4 client is now
    built lazily, only when a review reply is actually issued.
14. **datamanager** — `destinations.list` is not a real datamanager v1 method (there is no
    destinations resource). The read plane now targets `requestStatus.retrieve` (tool renamed to
    `datamanager.request_status`). Found by discovery conformance.
15. **datamanager** — conversion upload called a non-existent `conversions.ingest`; datamanager v1
    ingests offline events via `events.ingest`. The mutate plane now targets that method.
16. **meridian** — the connector imported a fictional `DataFrameInputDataLoader`; the real
    `google-meridian` loader is `DataFrameDataLoader`. Found by the isolated-venv library check.
17. **core / google_ads** — the Ads read connector built the Google Ads client at registration,
    and building it authenticates: missing or invalid Ads credentials crashed the **whole server**
    at startup (every other connector with it). Found by the real stdio smoke; the client is now
    built lazily on first call and an auth failure surfaces as that tool's structured error.
18. **vertex** — model ids rotted between June and November 2026: the Gemini 2.5 text family
    (including the default `gemini-2.5-flash`) now 404s on `generateContent`, every Imagen model
    left the publisher catalog, and Veo 3.0 was replaced by 3.1. Defaults re-chosen from the live
    catalog (GA + generating) and guarded by the new catalog-conformance test.
19. **vertex** — generated images were discarded (only index + MIME type returned); they are now
    returned as base64.
20. **vertex** — Veo returned a long-running operation with no way to poll it; new
    `vertex.veo.status` tool fetches completion and the video URIs/bytes.
21. **ci** — every action ran on Node 20, removed from GitHub-hosted runners on 2026-09-16, and
    Scorecard's v2.4.0 image was no longer served from gcr.io (weekly failures since September).
22. **entrypoint** — the shipped stdio server (`quantum-ads-mcp`) wired only Google Ads: every
    other connector answered `BACKEND_NOT_CONFIGURED` even with valid credentials (the live suite
    built backends itself, so it never saw this). New `quantum_ads/backends.py` maps all 37
    backend keys to their `sdk.py` factories, builds them lazily from the environment, and a
    completeness test fails if a connector reads an unmapped key. Proven over a real stdio
    subprocess with bogus Ads credentials: Search Console, BigQuery and Vertex Gemini return data.
23. **audit** — the signed ledger was in-memory only (key regenerated per process, records lost on
    exit), every record was stamped `1970-01-01T00:00:00Z`, and records were not chained, so a
    deleted record went unnoticed. It now persists (`audit.jsonl` + `audit_ed25519.pem` under
    `QUANTUM_ADS_AUDIT_DIR`, default `~/.quantum-ads/audit`), stamps real UTC time, chains each
    record to the previous by SHA-256, and exposes `audit.status` (chain check + public key).

## API-contract conformance (no account, no token, no cost)

`tests/live_smoke/test_discovery_conformance.py` validates every discovery-based connector's method
surface against Google's actual API contract: it loads each API's discovery document — the one
google-api-python-client bundles, i.e. exactly what the connector loads at runtime — and asserts that
every method the connector calls exists. **13/13 surfaces pass** (dv360, cm360, sa360 reporting +
conversions, adh, datamanager, gtm, Search Console webmasters + URL inspection, youtube, and the
three GBP hosts). A companion isolated-venv check (`tests/live_smoke/meridian_smoke.py`) does the
same for the **meridian** library: it asserts the connector's `google-meridian` imports + classes
all resolve.

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
