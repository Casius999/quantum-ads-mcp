# Changelog

All notable changes to Quantum ADS MCP are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/);
SemVer.

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
