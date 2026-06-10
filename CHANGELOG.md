# Changelog

All notable changes to Quantum ADS MCP are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/);
SemVer.

## [0.3.0](https://github.com/Casius999/quantum-ads-mcp/compare/quantum-ads-mcp-v0.2.0...quantum-ads-mcp-v0.3.0) (2026-06-10)


### Features

* **connectors:** add Ads Data Hub (ADH) connector — completes SP6 ([61ff56f](https://github.com/Casius999/quantum-ads-mcp/commit/61ff56f6bef965cd59fad7d78038857669fd6d65))
* **connectors:** add Business Profile, Looker, Meridian, Language, Workspace, reCAPTCHA ([8818cce](https://github.com/Casius999/quantum-ads-mcp/commit/8818cce2976b522d5adb3bdf5e086eaed0359f56))
* **connectors:** add CM360, SA360, BigQuery, Vertex AI, Trends connectors ([b175527](https://github.com/Casius999/quantum-ads-mcp/commit/b1755273ad1adfd44aa638e33f2cf6849d1e7155))
* **connectors:** add Data Manager, Search Console, YouTube, DV360 connectors ([f0b27ee](https://github.com/Casius999/quantum-ads-mcp/commit/f0b27ee79409f454ca1fcb7edca786e3649a1a59))
* **connectors:** add GA4, GTM, Merchant API connectors (read + guarded write) ([b339632](https://github.com/Casius999/quantum-ads-mcp/commit/b33963228cd057090f9ed7d3eb034a06be63d3bd))
* **core:** env-based connector selection (QUANTUM_ADS_CONNECTORS) ([abcd921](https://github.com/Casius999/quantum-ads-mcp/commit/abcd921cedc9a2d4a7fa42a0cb461add7a330ebd))
* **core:** multi-backend ServerContext (ctx.backends/ctx.backend) for pluggable connectors ([82d614d](https://github.com/Casius999/quantum-ads-mcp/commit/82d614d3bda5a8649aa7415ae69f207e1040020d))
* **core:** SP0 Phase B — credentials, env secret store, tenant resolver ([baa0f6e](https://github.com/Casius999/quantum-ads-mcp/commit/baa0f6ec0c9bdab171ad497b89af0f8ad654ec8c))
* **core:** SP0 Phase C — version manager, sunset guard, enum tolerance ([c247604](https://github.com/Casius999/quantum-ads-mcp/commit/c247604dfffe1942d393fbe76ac8c55ec15c7096))
* **core:** SP0 Phase D — GAQL build/validate/run engine + quota governor ([443b11b](https://github.com/Casius999/quantum-ads-mcp/commit/443b11bd300407a6d6a10eb35b74255aa4177f5e))
* **core:** SP0 Phase E — safety spine (read-only mode + signed audit ledger) ([c7357ee](https://github.com/Casius999/quantum-ads-mcp/commit/c7357ee8558f3c2796a097eb4f37028f6ed0011a))
* **core:** SP0 Phase F — connector registry + FastMCP server assembly ([3a5aeef](https://github.com/Casius999/quantum-ads-mcp/commit/3a5aeefbf289764cd3afb6bf25f24f6023e341a6))
* **core:** SP8 — multi-tenant + OAuth 2.1 bearer auth + observability ([3380e14](https://github.com/Casius999/quantum-ads-mcp/commit/3380e14acebe2db4e50d7e8769dc395119836c28))
* **dv360,cm360,sa360,adh,gbp:** quota routing + reachability live suites ([a0b6ae3](https://github.com/Casius999/quantum-ads-mcp/commit/a0b6ae34d22e47311deb6b9d1608bdc30c29bf77))
* **google_ads:** SP0 Phase G — read connector (GAQL, reports, change history, fields) ([95bfdf4](https://github.com/Casius999/quantum-ads-mcp/commit/95bfdf4c8ec2bf7d89810251966d59bb5a28260f))
* **google_ads:** SP1 Phase I — write-plane primitives (confirm + executor + audit) ([1348460](https://github.com/Casius999/quantum-ads-mcp/commit/1348460f123b800f289c4fb1402c6dfbf6ca3790))
* **google_ads:** SP1 Phase J — write tools + context wiring + connector ([1c11481](https://github.com/Casius999/quantum-ads-mcp/commit/1c114811f9163c398c55501b87083bed9b538872))
* **google_ads:** tool-boundary error handling + exhaustive live conformance (8/8) ([0eb8808](https://github.com/Casius999/quantum-ads-mcp/commit/0eb880880e2586a8722e99dbe6e8fccf6b7169c8))
* **merchant,vertex:** wire real auth + install merchant SDK + broaden validation scopes ([b9b5a36](https://github.com/Casius999/quantum-ads-mcp/commit/b9b5a36d982ab8cc818189f3290d324a0cb997e8))
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
* full-platform README + CONNECTORS.md catalog + CHANGELOG 0.2.0 ([78a6162](https://github.com/Casius999/quantum-ads-mcp/commit/78a6162eac31913c5ad96be2990e86173a590454))
* merchant + vertex now live-green (programmatic unlocks) ([291fd0c](https://github.com/Casius999/quantum-ads-mcp/commit/291fd0c9d5bb87ed5eb87efcbafc470366871d53))
* reflect 20 connectors (add Ads Data Hub to README/CONNECTORS/CHANGELOG) ([0d66b4a](https://github.com/Casius999/quantum-ads-mcp/commit/0d66b4ae91966eadd9d4eb661dca6d033ce86fac))
* SOTA governance + community health + devex + ADRs + architecture diagram ([026a87c](https://github.com/Casius999/quantum-ads-mcp/commit/026a87cc78cb9c8950eb9ce6637147b717378d9e))
* SP0 Phase H — quantum-ads skill + honest README + CHANGELOG v0.1.0 ([ead9aeb](https://github.com/Casius999/quantum-ads-mcp/commit/ead9aeb2136a4804e1f24e36a68e80e38f54aae0))

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
