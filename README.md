# Quantum ADS MCP

[![Google Ads API](https://img.shields.io/badge/Google%20Ads%20API-v24-blue.svg)](https://developers.google.com/google-ads/api/docs/release-notes)
[![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-FastMCP%203.4%20stdio-purple.svg)](https://modelcontextprotocol.io/)
[![connectors](https://img.shields.io/badge/connectors-19-orange.svg)](CONNECTORS.md)
[![type-checked](https://img.shields.io/badge/mypy-strict-blue.svg)](pyproject.toml)
[![coverage](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

A **sovereign Google marketing-agency control plane** over the Model Context Protocol: a shared
core (multi-tenant auth, version resilience, a GAQL/query engine, a safety spine with a signed
audit ledger) and **19 pluggable per-product connectors** spanning the entire Google marketing
stack. Built for an AI agent to operate that stack at full granularity, safely.

> **Status.** The full connector surface is built and tested at the logic layer: **read + guarded
> write across 19 products**, every tool exercised by mocked tests (no live SDK needed). The
> per-product **live SDK glue is isolated in `sdk.py` modules and smoke-gated** (verified against
> real APIs with your own credentials, not in CI). Remaining for full production hardening: remote
> OAuth 2.1 transport + multi-tenant secret store + observability (see Roadmap). Read-only by
> default. Every "most X" claim here is meant to be verifiable.

## Why this exists

Surveying June 2026: Google's official MCP is read-only (3 tools); the best open write-capable
servers are pinned to sunsetting API versions, untested, single-product, or have no safety layer;
the capable commercial ones are closed and remote-only. **No open, self-hostable server is
simultaneously complete across the stack, write-capable, safe, tested, version-resilient, and
multi-product.** Quantum ADS fills that gap.

## The 19 connectors

| Domain | Connectors |
|--------|-----------|
| **Paid media** | Google Ads (v24), DV360, CM360, SA360 |
| **Measurement** | GA4 (Data + Admin), Data Manager API (Customer Match + conversions), Search Console |
| **Catalog / tagging** | Merchant API, Google Tag Manager (+ server-side, Consent Mode v2) |
| **Channels** | YouTube (Data + Analytics + Reporting), Business Profile, Trends |
| **Warehouse / BI / MMM** | BigQuery (cost-guarded), Looker, Meridian (Bayesian MMM) |
| **Creative / ops** | Vertex AI (Gemini / Imagen 4 / Veo 3), Cloud Translation + NL, Workspace (Sheets/Drive/Slides), reCAPTCHA Enterprise |

Full tool catalog, backend keys, and required SDK packages: **[CONNECTORS.md](CONNECTORS.md)**.

## Core (shared by every connector)

- **Multi-tenant auth + secret store** — credentials load from env / secret manager and **never reach the LLM**.
- **Version resilience** — pinned **v24**, sunset guard (days-until-sunset), **unknown-enum tolerance** (survives Google's monthly API releases and the 2026-06-10 DV360 Demand Gen rollout).
- **Query engine** — GAQL build / validate (single-FROM, no-`OR`, segment rules, 37-month cap) / stream / flatten, with quota token-buckets + exponential backoff. SA360 uses the same query shape.
- **Safety spine** — **read-only by default**; every mutation is guarded: `validate_only` preview → **two-step confirm token** → **Ed25519 signed audit ledger**. Consent-aware (Data Manager / Consent Mode v2) and cost-aware (BigQuery dry-run, $6.25/TiB).
- **Connector registry + meta-tool discovery** (`list_capabilities`, `describe_tool`) and **env-based connector selection** (`QUANTUM_ADS_CONNECTORS`) so the tool list stays focused.

## Install

```bash
git clone https://github.com/Casius999/quantum-ads-mcp.git
cd quantum-ads-mcp
uv sync --extra dev
uv run pytest -m "not live"      # 250+ tests, no credentials needed
```

Per-connector live SDKs (e.g. `google-analytics-data`, `google-api-python-client`,
`google-cloud-bigquery`) are installed only when you wire a connector's live backend — see
[CONNECTORS.md](CONNECTORS.md). The core + mocked test suite need none of them.

## Configure

Credentials load from environment variables (no secrets on disk):

```bash
GOOGLE_ADS_USE_PROTO_PLUS=True
GOOGLE_ADS_API_VERSION=v24
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
QUANTUM_ADS_READ_ONLY=true                 # writes refused until set to false
QUANTUM_ADS_CONNECTORS=google_ads,ga4,gtm  # optional: mount a subset (default: all 19)
```

> **Never commit** `.env`, `google-ads.yaml`, or `client_secret*.json` — all gitignored, and
> `gitleaks` runs in CI. See [SECURITY.md](SECURITY.md).

## Run

```bash
python -m quantum_ads        # stdio MCP server
```

Wire it into your MCP client (Claude Desktop / VS Code) as a stdio server.

## Safety & honest claims

Read-only by default; tokens never reach the model; zero secrets in the repo. CI runs lint, strict
type-check, the full test suite (≥90% coverage gate), CodeQL, OpenSSF Scorecard, and gitleaks.

The defensible "most powerful" claim is **coverage breadth + engineering rigor + safety + version
resilience**, each verifiable — *not* "record ad performance" (that depends on budget, creative,
and Google's auction, not the server). Documentation states only what the test suite proves; the
per-product live SDK calls are smoke-gated and labelled as such.

## Roadmap (remaining for full production hardening)

Remote **Streamable HTTP + OAuth 2.1/PKCE** transport · multi-tenant secret store (per-client
OAuth) · observability (structured logging + tracing) · live-API conformance suite · optional
anchoring of the signed audit ledger.

## License

MIT — see [LICENSE](LICENSE).

— **Julien Compain** · NovaQuantiX
