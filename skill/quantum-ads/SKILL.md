---
name: quantum-ads
description: Use when operating the Quantum ADS MCP server — a sovereign Google marketing agency control plane. SP0 ships the shared core (multi-tenant auth, version resilience, GAQL engine, safety spine) plus a read-only Google Ads (API v24, June 2026) connector. Covers env-var auth, the tool catalog, GAQL recipes/payloads, and mutate/spend/honesty guardrails.
---

# Quantum ADS — Google marketing agency control plane (MCP, June 2026)

A FastMCP (stdio) server exposing the Google marketing stack as MCP tools, on a shared sovereign
core. **SP0** (this release) ships the core + a **read-only Google Ads v24** connector. Write
planes and other connectors (GA4, GTM, Merchant, Data Manager, DV360/CM360/SA360, …) land in
later sub-projects.

## Architecture in one screen
- **Transport:** FastMCP over stdio (`mcp.server` / FastMCP 3.4), launched by `python -m quantum_ads`.
- **Core (shared):** multi-tenant auth + secret store (tokens never reach the LLM), version
  manager (pinned **v24**, sunset guard, unknown-enum tolerance), GAQL build/validate/run engine
  with quota governors, safety spine (**read-only by default**, signed audit ledger), connector
  registry + meta-tool discovery.
- **Connector (SP0):** Google Ads read — GAQL passthrough, opinionated reports, change history,
  field catalogs.

## When to use
- Pull metrics/reports from a Google Ads account (GAQL).
- Inspect campaigns/search terms/PMax/AI Max/conversions, change history, or the v24 field surface.
- Know the current (June 2026) API reality and what is sunset.

## Critical first facts (June 2026)
- Google Ads API **v24.1** is current; library **google-ads 31**; **monthly** releases. **v19
  sunset 2026-02-11; v20 sunset 2026-06-10.** This server targets **v24**.
- Three API planes exist now: Google Ads API (v24) + **Data Manager API** (1st-party data —
  Ads-API conversion upload blocked 2026-06-15) + **Merchant API** (Content API sunsets 2026-08-18).
  SP0 covers Google Ads reads only; the others are later sub-projects.
- Details: `references/google-ads-2026-sota.md`.

## Setup (auth) — env vars, no secrets on disk
Set environment variables (or a gitignored `.env`); the client loads via `load_from_env`:
```
GOOGLE_ADS_USE_PROTO_PLUS=True
GOOGLE_ADS_API_VERSION=v24
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_LOGIN_CUSTOMER_ID=     # MCC only
QUANTUM_ADS_READ_ONLY=true        # SP0 is read-only
```
Full flow + secret hygiene: `references/auth-and-guardrails.md`.

## Tool catalog (SP0)
- **Meta:** `health`, `list_capabilities`, `describe_tool` (dynamic discovery).
- **Google Ads read:** `ads.gaql.query`, `ads.report.campaign|search_terms|pmax_asset_groups|ai_max|conversions`,
  `ads.change_history` (audit/delta), `ads.fields.deltas|new_views`.
- Full descriptions + GAQL recipes + payload patterns: `references/tool-catalog.md`, `references/gaql-and-payloads.md`.

## Guardrails (always)
1. **Read-only in SP0.** Mutations are refused (`QUANTUM_ADS_READ_ONLY=true`); write planes arrive in SP1+ behind two-step confirm + `validate_only`.
2. **Honest claims.** "Most complete/safe/version-resilient open Google Ads MCP" is the defensible
   claim (coverage + engineering + rigor) — not "record ad performance" (that's budget/creative/Google's
   auction, not the server). State only what tests prove.
3. **Micros + time zone:** `*_micros` ÷ 1,000,000 = account currency; dates are account-local; re-pull
   trailing windows (conversions mature). See `references/gaql-and-payloads.md`.
4. **Version discipline:** never target a sunset version; `health` reports days-until-sunset.

Rationale: `references/auth-and-guardrails.md`.
