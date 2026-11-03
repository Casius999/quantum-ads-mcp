---
name: quantum-ads
description: Use when operating the Quantum ADS MCP server — a sovereign Google marketing-agency control plane exposing 150 tools across 21 connectors (Ads API v26, GA4, GTM, Merchant, Data Manager, Search Console, YouTube, DV360/CM360/SA360, ADH, Business Profile, Workspace, BigQuery, Looker, Vertex AI, free text-to-video, Trends, Meridian, Language, reCAPTCHA), over stdio or OAuth 2.1-protected multi-tenant HTTP. Covers env-var auth per connector, remote serving, the generated tool catalog, GAQL recipes/payloads, version discipline (Nov 2026), and the guarded write / spend / honesty guardrails.
---

# Quantum ADS — Google marketing agency control plane (MCP, November 2026)

A FastMCP 4 server (MCP Python SDK 2, protocol revision 2026-07-28) exposing the Google marketing
stack as MCP tools on one shared core. Launch: `quantum-ads-mcp` (stdio) or
`quantum-ads-mcp serve --transport http` (Streamable HTTP behind OAuth 2.1, multi-tenant).

## Architecture in one screen
- **Core (shared):** credential store (tokens never reach the LLM), version manager (default
  **Ads API v26**, official sunset table, unknown-enum tolerance), GAQL build/validate/run engine
  with quota governors, safety spine (**read-only by default**, `validate_only` preview → two-step
  confirm token → Ed25519-signed, hash-chained, persistent audit ledger), connector registry + meta-tool discovery.
- **21 connectors**, each reading its API through a named **backend** (`ctx.backend("<key>")`).
  The entrypoint builds every backend the environment can serve (`quantum_ads/backends.py`);
  backends are **lazy** — nothing authenticates until a tool is first called, so one connector's
  bad credentials never take the server down. An unwired backend answers
  `{error: BACKEND_NOT_CONFIGURED}` instead of raising.

## When to use
- Report on / operate Google Ads (GAQL, opinionated reports, change history, guarded
  status/budget edits).
- Pull GA4 / Search Console / YouTube / BigQuery / Looker data; manage GTM, Merchant Center,
  Business Profile, DV360/CM360/SA360; upload first-party data via Data Manager.
- Generate creative with Vertex AI (Gemini text, Gemini image, Veo video) or run Meridian MMM.
- Generate short videos **for free** with `video.generate` (Wan 2.2 → LTX-Video on Hugging Face
  ZeroGPU; daily GPU quota, `QUOTA_EXHAUSTED` when spent) — prefer it over paid Veo.
- Check what changed between Ads API versions (`ads.api.version_delta`) and how close the pinned
  version is to sunset (`health`).

## Critical first facts (November 2026)
- Google Ads API **v26** is current (released 2026-10-14; sunset 2027-11). Supported: v23
  (sunset 2027-02), v24 (2027-05), v25 (2027-08). Library **google-ads 35**. Releases are
  monthly-cadenced; re-check the sunset table before pinning.
- Three Google Ads planes: **Google Ads API** (campaigns, GAQL reporting) + **Data Manager API**
  (Customer Match / offline + enhanced conversions — no longer uploadable via the Ads API) +
  **Merchant API** (Shopping catalog — the Content API for Shopping is sunset).
- Vertex defaults are GA models: `gemini-3.8-flash` (text), `gemini-3.1-flash-image` (image),
  `veo-3.1-generate-001` (video, long-running — poll with `vertex.veo.status`).
- Details: `references/google-ads-2026-sota.md`.

## Setup — environment variables only
One Google OAuth user credential serves every Google connector; the Ads credential is reused when
no dedicated one is set. Pass these as process environment (the MCP client's `env` block — the
server does not read `.env` itself):
```
GOOGLE_ADS_DEVELOPER_TOKEN=...        # Google Ads only
GOOGLE_ADS_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...          # must carry the scopes of the connectors you use
GOOGLE_CLOUD_PROJECT=my-project       # unlocks BigQuery, Vertex, Language, reCAPTCHA + quota routing
QUANTUM_ADS_READ_ONLY=true            # writes refused until set to false
```
Optional: `GOOGLE_OAUTH_{CLIENT_ID,CLIENT_SECRET,REFRESH_TOKEN}` (separate non-Ads credential),
`GOOGLE_VERTEX_LOCATION` (default `global`), `LOOKERSDK_{BASE_URL,CLIENT_ID,CLIENT_SECRET}`,
`GOOGLE_ADS_API_VERSION`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `QUANTUM_ADS_CONNECTORS` (mount a
subset), `QUANTUM_ADS_AUDIT_DIR` (audit ledger location; empty = in memory), `QUANTUM_ADS_LLM_{BASE_URL,API_KEY,MODEL}` + `QUANTUM_ADS_IMAGE_MODEL` (free creative fallback, any OpenAI-compatible endpoint). Remote (HTTP) serving with "Sign in with Google" (`QUANTUM_ADS_AUTH=google`, each user acts with
their own Google token, allowlist + writers list): `docs/DEPLOY.md`. Other remote modes, tokens, scopes and tenants: see "Remote serving" in
`references/auth-and-guardrails.md`. Full matrix + secret hygiene: same file.

## Tool catalog
- **Meta:** `health` (incl. call counters), `list_capabilities`, `describe_tool` — call
  `list_capabilities` first. **Audit:** `audit.status`, `audit.anchor` (Bitcoin via
  OpenTimestamps), `audit.anchor_status`.
- **Insights:** `insights.anomalies`, `insights.pacing`, `insights.search_terms` (returns
  ready `ads.mutate` operations), `insights.ga4_reconcile`. **Creative:** `creative.search_ads`,
  `creative.pmax_pack` (copy checked against Google Ads limits, one automatic repair round;
  images fitted to spec) — Vertex first, then the free `QUANTUM_ADS_LLM_*` endpoint, SDXL
  (`QUANTUM_ADS_IMAGE_MODEL`) and FLUX.
- **Negatives in one call:** `insights.apply_negatives` mines wasted terms and writes them as
  exact negatives (guarded, audited, undone by `ads.rollback`).
- Full generated list (163 tools, read vs guarded write): `references/tool-catalog.md`.
- GAQL recipes + payload patterns: `references/gaql-and-payloads.md`.

## Changing anything in the other Google APIs
- `google.api.*` reaches every method of 25 marketing APIs (GA4 Admin/Data, Tag Manager,
  Merchant, Content, YouTube, DV360, CM360, SA360, Business Profile, Search Console,
  Sheets/Drive/Slides/Docs, BigQuery, Ads Data Hub, Data Manager, reCAPTCHA, Language,
  Translate): 1,180 methods, 653 of them writes. `google.api.list` -> `google.api.methods`
  (filter by `resource`, `writes_only`) -> `google.api.describe` (parameters, body fields,
  scopes) -> `google.api.read` or `google.api.call`.
- Every call is checked offline against the API's Discovery contract (method, required and
  unknown parameters, path patterns, enums, body field names and JSON types). Writes then run
  the guarded flow; the preview also refuses a method the token holds no scope for, and uses
  the API's own `validateOnly` when it has one. Deletes need `allow_delete=true`; BigQuery jobs
  go through the cost-guarded `bigquery.query`.
- Updates read the resource first and creates record their `delete`/`archive`, so
  `google.api.rollback` undoes the latest reversible call. Rollbacks walk back through history
  and are never undone by the next rollback (same for `ads.rollback`).

## Creating and changing anything in Google Ads
- `ads.mutate` takes official `MutateOperation` JSON for ANY resource (`ads.mutate.schema` lists
  the 65 operation kinds and each resource's fields); negative temporary ids
  (`customers/<id>/campaigns/-2`) link objects created together; one atomic request unless
  `partial_failure`. Schema errors come back as `INVALID_OPERATION` before any API call.
- `ads.campaign.create_search` builds a full Search campaign (budget, bidding, geo/language,
  negatives, ad group, keywords, RSA) in one call; use `status=PAUSED` to stage.
- `ads.campaign.create_pmax` builds a full Performance Max campaign; images are base64 (e.g.
  from `vertex.imagen.generate`).
- `ads.campaign.create_demand_gen`; A/B tests with `ads.experiment.create` (then edit the
  treatment draft with `ads.mutate`), `.schedule`, `.promote`, `.end`; thousands of changes
  at once with `ads.batch.submit` + `ads.batch.status`; `ads.reach.*` (Reach Planner needs an
  allowlisted developer token, otherwise API_ERROR).
- `ads.rollback` undoes the latest reversible Google Ads change of this tenant (or
  `audit_index`) from the signed audit trail; update masks are derived when omitted and may be
  snake_case.
- `ads.keyword_ideas` (Keyword Planner), `ads.recommendations.list` / `.apply` / `.dismiss`.

## MCP features to use
- Read `quantum-ads://session` first (tenant, write mode, policy) and
  `quantum-ads://capabilities` instead of listing tools one by one.
- Start a job from a prompt: `weekly_account_audit`, `pmax_diagnosis`, `search_terms_mining`,
  `budget_reallocation`, `launch_search_campaign`, `merchant_feed_optimization`, `ga4_ads_reconciliation`,
  `demand_research`, `creative_studio`.
- With tool search on, call `search_tools` then `call_tool`; long-running tools may answer with
  a task handle to poll.

## Guardrails (always)
1. **Writes are guarded.** Refused while `QUANTUM_ADS_READ_ONLY=true` (default). When enabled,
   every write runs a `validate_only` preview, returns a confirm token, executes only on the
   second call with that token, and appends an Ed25519-signed, hash-chained audit record
  (persisted under `~/.quantum-ads/audit` by default; `audit.status` verifies the chain). Never
  skip the preview.
2. **Spend is real.** Vertex generation (text/image/video) and BigQuery scans bill the GCP
   project. Prefer BigQuery `dry_run`; for video use the free `video.generate` first and treat
   Veo as several USD per clip — ask before running it.
3. **Honest claims.** The defensible claim is coverage + engineering rigor + safety + version
   resilience — never "record ad performance" (budget, creative and Google's auction decide
   that). State only what tests or live calls proved.
4. **Micros + time zone:** `*_micros` ÷ 1,000,000 = account currency; dates are account-local;
   re-pull trailing windows (conversions mature).
5. **Version discipline:** never target a sunset version; `health` reports days-until-sunset.
