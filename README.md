# Quantum ADS MCP

[![Google Ads API](https://img.shields.io/badge/Google%20Ads%20API-v24-blue.svg)](https://developers.google.com/google-ads/api/docs/release-notes)
[![google-ads](https://img.shields.io/badge/google--ads-31.0.0-blue.svg)](https://pypi.org/project/google-ads/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-FastMCP%203.4%20stdio-purple.svg)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

A **sovereign Google marketing agency control plane** over the Model Context Protocol: a shared
core (multi-tenant auth, version resilience, a GAQL engine, a safety spine) with pluggable
per-product connectors. Built for an AI agent to operate the Google marketing stack at full
granularity, safely.

> **Status — SP0 (foundation).** This release ships the **core** plus a **read-only Google Ads
> (API v24)** connector. It is read-only by default; write planes and the other connectors arrive
> in later sub-projects (see Roadmap). Every "most X" claim below is meant to be verifiable.

## Why this exists

Surveying June 2026: Google's official MCP is read-only (3 tools); the best open write-capable
servers are pinned to sunsetting API versions, untested, or have no safety layer; the capable
commercial ones are closed and remote-only. **No open, self-hostable server is simultaneously
complete, write-capable, safe, tested, version-resilient, and multi-product.** Quantum ADS fills
that gap — one sub-project at a time, each one independently shippable.

## What's in SP0

**Core (shared by every future connector)**
- Multi-tenant auth + secret store — credentials load from env/secret manager and **never reach the LLM**.
- Version manager — pinned **v24**, sunset guard (days-until-sunset), **unknown-enum tolerance**
  (survives Google's monthly API releases).
- GAQL engine — build / validate (single-FROM, no-`OR`, segment, 37-month cap) / stream / flatten,
  with quota token-buckets + exponential backoff.
- Safety spine — **read-only by default**, plus an Ed25519 **signed audit ledger** for future mutations.
- Connector registry + meta-tool discovery (`list_capabilities`, `describe_tool`).

**Google Ads read connector** — `ads.gaql.query`, `ads.report.{campaign,search_terms,pmax_asset_groups,ai_max,conversions}`,
`ads.change_history` (audit/delta), `ads.fields.{deltas,new_views}`, plus `health`.

## Install

```bash
git clone https://github.com/Casius999/quantum-ads-mcp.git
cd quantum-ads-mcp
uv sync --extra dev
```

## Configure (environment variables — no secrets on disk)

Copy `.env.example` to `.env` (gitignored) and fill:

```bash
GOOGLE_ADS_USE_PROTO_PLUS=True
GOOGLE_ADS_API_VERSION=v24
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_LOGIN_CUSTOMER_ID=     # MCC only
QUANTUM_ADS_READ_ONLY=true
```

> **Never commit** `.env`, `google-ads.yaml`, or `client_secret*.json` — all gitignored, and
> `gitleaks` runs in CI. See [SECURITY.md](SECURITY.md).

## Run

```bash
python -m quantum_ads        # stdio MCP server
```

Wire it into your MCP client (Claude Desktop / VS Code) as a stdio server.

## Tools (SP0, read-only)

| Tool | Purpose |
|------|---------|
| `health` | API version, days-until-sunset, read-only flag |
| `list_capabilities` / `describe_tool` | dynamic tool discovery |
| `ads.gaql.query` | raw GAQL (validated, streamed, flattened) |
| `ads.report.campaign` … `ads.report.conversions` | opinionated v24 reports |
| `ads.change_history` | `change_event` (audit) / `change_status` (delta) |
| `ads.fields.deltas` / `ads.fields.new_views` | curated v24 2026 field surface |

## Companion skill

[`skill/quantum-ads/`](skill/quantum-ads/SKILL.md) — the operating manual: June 2026 SOTA, auth,
the tool catalog, GAQL recipes/payloads, and guardrails.

## June 2026 surface

API **v24.1** · monthly releases · AI Max · Performance Max · new views (`per_store_view`,
`matched_location_interest_view`, …). Three API planes now exist — Google Ads API + **Data Manager
API** (conversions/Customer Match; Ads-API upload blocked 2026-06-15) + **Merchant API** (Content
API sunsets 2026-08-18). SP0 covers Google Ads reads; the rest are later sub-projects.

## Roadmap (sub-projects)

**SP0** core + Google Ads read · **SP1** Google Ads write (all campaign types) · **SP2** GA4 +
Data Manager + Consent Mode v2 · **SP3** GTM + Merchant API · **SP4** DV360/CM360/SA360 +
Floodlight · **SP5** Search Console / YouTube / Business Profile / Trends · **SP6** BigQuery / Ads
Data Hub / Looker / Meridian · **SP7** Vertex (Gemini/Imagen/Veo) / Translation / Workspace ·
**SP8** remote OAuth 2.1 + multi-tenant + observability.

## Security

Read-only by default; tokens never reach the model; zero secrets in the repo. CI runs lint, strict
type-check, tests (≥90% coverage gate), CodeQL, OpenSSF Scorecard, and gitleaks. See
[SECURITY.md](SECURITY.md).

## Honest claims

The defensible "most powerful" claim is **coverage + engineering rigor + safety + version
resilience**, each verifiable — *not* "record ad performance" (that depends on budget, creative,
and Google's auction, not the server). Documentation states only what the test suite proves.

## Development

```bash
uv run ruff format . && uv run ruff check . && uv run mypy src && uv run pytest -m "not live"
```

## License

MIT — see [LICENSE](LICENSE).

— **Julien Compain** · NovaQuantiX
