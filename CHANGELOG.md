# Changelog

All notable changes to Quantum ADS MCP are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/);
SemVer.

## [0.6.0](https://github.com/Casius999/quantum-ads-mcp/compare/v0.5.0...v0.6.0) (2026-11-02)


### Features

* **audit:** verify Bitcoin anchors against the block merkle root ([6ce0d9f](https://github.com/Casius999/quantum-ads-mcp/commit/6ce0d9f19f08a795e855b8745fb0076b1553d98c))


### Documentation

* security policy, Bitcoin verification, 2026-11-02 live results ([33465b4](https://github.com/Casius999/quantum-ads-mcp/commit/33465b42c1378f00ac58d1bdba6bd8f3f3f1aa10))

## [0.5.0](https://github.com/Casius999/quantum-ads-mcp/compare/v0.4.0...v0.5.0) (2026-11-01)


### Features

* **audit:** anchor the audit chain head in Bitcoin via OpenTimestamps ([69fcac7](https://github.com/Casius999/quantum-ads-mcp/commit/69fcac7e9377198f1d36cadfe7ef65f6b27df38c))
* **observability:** structured call logs, health counters and OpenTelemetry tracing ([95425d2](https://github.com/Casius999/quantum-ads-mcp/commit/95425d266a433916f3e7a4e6a40c6b7ccb1785dd))
* **remote:** load the tenant credential map from Google Secret Manager ([5d13f04](https://github.com/Casius999/quantum-ads-mcp/commit/5d13f0492e2c7b52f496d5e414f634515230027d))


### Bug Fixes

* **trends:** serve trending_now from the public Trending-now RSS feed ([1fe580c](https://github.com/Casius999/quantum-ads-mcp/commit/1fe580ce882f08276e0809f280013d1e63d149fe))


### Documentation

* observability, audit anchoring, Secret Manager tenants, hardening results ([9131a3c](https://github.com/Casius999/quantum-ads-mcp/commit/9131a3c2394e2a9091cc766408cd8ac86da81e10))

## [0.4.0](https://github.com/Casius999/quantum-ads-mcp/compare/v0.3.1...v0.4.0) (2026-11-01)


### Features

* **remote:** OAuth 2.1 protected multi-tenant Streamable HTTP transport ([72822cb](https://github.com/Casius999/quantum-ads-mcp/commit/72822cb877ae70e0b78b00a32bb8a5273a9ce96e))
* **scripts:** mint an Ads-only refresh token for the approved Cloud project ([1dcc50f](https://github.com/Casius999/quantum-ads-mcp/commit/1dcc50f71576c5c71887216aa8c227e1edca6c92))
* **video:** free text-to-video connector over Hugging Face ZeroGPU Spaces ([5e7de19](https://github.com/Casius999/quantum-ads-mcp/commit/5e7de19820b78ad657933fd9ab1be76e8198150e))


### Documentation

* remote OAuth 2.1 serving, free video, Google Ads v26 live results ([ef3d5ee](https://github.com/Casius999/quantum-ads-mcp/commit/ef3d5eee9e8ccb1ccdc01e31e5eb2e3becdff77e))

## [0.3.1](https://github.com/Casius999/quantum-ads-mcp/compare/v0.3.0...v0.3.1) (2026-11-01)


### Bug Fixes

* **audit:** persist, timestamp and hash-chain the signed audit ledger ([be4360d](https://github.com/Casius999/quantum-ads-mcp/commit/be4360d153c79d0da99a9003ced334da2d8295af))
* wire every connector backend in the stdio entrypoint ([bc153ed](https://github.com/Casius999/quantum-ads-mcp/commit/bc153ed2d46f0c2f4e1171d0c875962484a96dc5))


### Documentation

* rewrite the skill and config for November 2026 and all connectors ([d1446fc](https://github.com/Casius999/quantum-ads-mcp/commit/d1446fc29055abf3334dd7c8054ab46a24d4afdb))

## [0.3.0](https://github.com/Casius999/quantum-ads-mcp/compare/v0.2.0...v0.3.0) (2026-11-01)


### Features

* **dv360,cm360,sa360,adh,gbp:** quota routing + reachability live suites ([a0b6ae3](https://github.com/Casius999/quantum-ads-mcp/commit/a0b6ae34d22e47311deb6b9d1608bdc30c29bf77))
* **google_ads:** tool-boundary error handling + exhaustive live conformance (8/8) ([0eb8808](https://github.com/Casius999/quantum-ads-mcp/commit/0eb880880e2586a8722e99dbe6e8fccf6b7169c8))
* **google-ads:** pin API v26 (latest, sunset 2027-11), GAQL field conformance, version_delta tool ([dfc8fe7](https://github.com/Casius999/quantum-ads-mcp/commit/dfc8fe778436775abc0987428980839740acea2d))
* **merchant,vertex:** wire real auth + install merchant SDK + broaden validation scopes ([b9b5a36](https://github.com/Casius999/quantum-ads-mcp/commit/b9b5a36d982ab8cc818189f3290d324a0cb997e8))
* migrate to fastmcp 4 / MCP Python SDK 2 (protocol 2026-07-28); lazy Ads client ([c38479a](https://github.com/Casius999/quantum-ads-mcp/commit/c38479aa1f46cd30650ef679bd70483794047fb9))
* **vertex:** full REST client, current GA models, Veo polling, catalog conformance; drop aiplatform ([a81e61e](https://github.com/Casius999/quantum-ads-mcp/commit/a81e61e1653c73ecd2cf15ef4d2f5678b0599ab1))
* **vertex:** migrate Gemini to REST generateContent on the global endpoint (live-green) ([64c9cb3](https://github.com/Casius999/quantum-ads-mcp/commit/64c9cb3857ff11a87716a7f776da28c48b7bb2e2))


### Bug Fixes

* **bigquery,language:** OAuth creds wiring proven by live conformance ([1876bb5](https://github.com/Casius999/quantum-ads-mcp/commit/1876bb54dccfd7802a3f352ffcf5c3a88579afaa))
* **datamanager,meridian:** correct fictional endpoints/classes (conformance + isolated-venv check) ([7352216](https://github.com/Casius999/quantum-ads-mcp/commit/7352216a1c7be138d71c6fe2f3d10feb1ea42218))
* **ga4:** lazy-import Audience on the real-create path (was undefined after removing top import) ([26348f9](https://github.com/Casius999/quantum-ads-mcp/commit/26348f9e13867b9a2ae24f59ee41d3156c0e3cfa))
* **ga4:** list_properties via request object + lazy admin type imports + quota_project_id routing ([095f15d](https://github.com/Casius999/quantum-ads-mcp/commit/095f15d345fa65c6fa2f2f31c64e4c8fcde771dd))
* **google_ads:** set validate_only on the mutate request object (google-ads 31) ([d288d30](https://github.com/Casius999/quantum-ads-mcp/commit/d288d302645854c8fef53a21765f040a4adf7317))
* **gtm,searchconsole,youtube:** quota routing + read scope, proven by live conformance ([49d12e4](https://github.com/Casius999/quantum-ads-mcp/commit/49d12e4f95f0dc0d219d72e37d0538d4ac2a28f7))
* **recaptcha:** quota_project_id routing + add live conformance (recaptcha, trends) + results doc ([a79556f](https://github.com/Casius999/quantum-ads-mcp/commit/a79556fce099f464d03b41bdd7279a6cb8f4326f))
* **vertex,adh,gbp:** live construction bugs + tolerant reachability harness ([2295419](https://github.com/Casius999/quantum-ads-mcp/commit/229541926e45103e00dedcfb8444ace0475380a2))
* **youtube:** remove non-existent videos.batchGetStats endpoint ([d206499](https://github.com/Casius999/quantum-ads-mcp/commit/d2064993c04569791b6fc4d64384a82bcd7bdacc))


### Documentation

* add SVG hero banner + centered README header with live CI/CodeQL/Scorecard badges ([c008f8b](https://github.com/Casius999/quantum-ads-mcp/commit/c008f8bf3f14141025bd0551fcb1aea9929e341a))
* merchant + vertex now live-green (programmatic unlocks) ([291fd0c](https://github.com/Casius999/quantum-ads-mcp/commit/291fd0c9d5bb87ed5eb87efcbafc470366871d53))
* Nov 2026 refresh — v26, fastmcp 4 / MCP 2026-07-28, Vertex REST, live results ([8ea5b7c](https://github.com/Casius999/quantum-ads-mcp/commit/8ea5b7ce6f651a98c22dd82004148ca75b449b7a))
* SOTA governance + community health + devex + ADRs + architecture diagram ([026a87c](https://github.com/Casius999/quantum-ads-mcp/commit/026a87cc78cb9c8950eb9ce6637147b717378d9e))

## [0.2.0] - 2026-06-09 — Full agency control plane (19 connectors)

### Added
- **Google Ads write plane** — guarded `ads.campaign.set_status`, `ads.budget.update`
  (validate_only preview → two-step confirm token → Ed25519 signed audit), real SDK mutate glue.
- **19 additional product connectors** (read + guarded write where supported): GA4, GTM
  (+ server-side / Consent Mode v2), Merchant API, Data Manager API, Search Console, YouTube
  (Data/Analytics/Reporting), DV360, CM360, SA360, BigQuery (cost-guarded), Ads Data Hub, Vertex AI
  (Gemini/Imagen/Veo), Trends, Business Profile, Looker, Meridian (MMM), Cloud Translation + NL,
  Workspace (Sheets/Drive/Slides), reCAPTCHA Enterprise.
- **Generalized core**: `WriteExecutor` moved to `core/safety` and reused by every connector;
  multi-backend `ServerContext` (`ctx.backend(name)`); env-based connector selection
  (`QUANTUM_ADS_CONNECTORS`).
- **CONNECTORS.md** — full tool catalog, backend keys, and per-connector SDK packages.

### Quality
- mypy --strict clean across 187 source files; ruff clean; test coverage 99%.
- Each connector's live SDK glue isolated in `sdk.py` (smoke-gated, mypy-ignored, coverage-omitted);
  all tool logic + the safety flow unit/mock-tested without any live SDK.

### Notes
- Read-only by default. Remaining for full production hardening: remote OAuth 2.1 transport,
  multi-tenant secret store, observability, and a live-API conformance suite.

## [0.1.0] - 2026-06-09 — SP0 (foundation + Google Ads read)

### Added
- **Sovereign core**
  - Multi-tenant auth + env secret store (`TenantCredentials` with redacted repr; tokens never logged).
  - Version manager: pinned API **v24**, sunset guard (`days_until_sunset`), unknown-enum tolerance.
  - GAQL engine: builder + validator (single-FROM, no-`OR`, segment-in-SELECT, 37-month lookback cap),
    `run_report` (validate → stream → flatten), quota token-bucket + exponential backoff.
  - Safety spine: **read-only by default**; Ed25519 signed, tamper-evident audit ledger.
  - Connector registry + meta-tool discovery (`list_capabilities`, `describe_tool`); `health`.
- **Google Ads read connector (API v24)**
  - `ads.gaql.query` (validated raw GAQL).
  - `ads.report.{campaign,search_terms,pmax_asset_groups,ai_max,conversions}`.
  - `ads.change_history` (audit=`change_event` 30d / delta=`change_status` 90d, LIMIT cap 10000).
  - `ads.fields.{deltas,new_views}` (curated v24 2026 field/view surface).
  - `date_range` allowlist (anti-injection).
- **Tooling/hardening:** uv + src-layout + pyproject; ruff + mypy(strict) + pytest; CI (lint, type,
  test, ≥90% coverage gate, gitleaks), CodeQL, OpenSSF Scorecard, Dependabot.
- **Skill:** `skill/quantum-ads/` (SKILL.md + 4 references).

### Security
- No credentials in the repo or git history (fresh repo). `.env`/`google-ads.yaml`/`client_secret*.json` gitignored.

### Notes
- Read-only release. Mutations, other connectors, and remote/OAuth 2.1 transport land in SP1+.
- Test coverage 95%+ on the core; the live-API SDK glue is exercised by a gated `live` smoke test, not unit tests.
