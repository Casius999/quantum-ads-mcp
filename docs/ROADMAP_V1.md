# Quantum ADS MCP — v1 program (from 2026-11-03)

Goal: an agent-operated marketing control plane that **creates, manages and monitors** campaigns
end to end across the Google stack, with the AI as the decision-maker (it holds the data) and
optional guardrails. Baseline (v0.6.0, verified from the live registry): 131 tools, 98 read /
33 write; Google Ads has 2 writes; Vertex, video, Trends, Meridian and Language have none.

Principles: AI decides and applies (preview-then-commit is a self-check, never a human gate);
guardrails are opt-in policy, off by default; every write keeps `validate_only`, the signed
audit trail and, where the API allows, an inverse operation for rollback; one PR per wave.

## Wave 1 — MCP-native foundation (done, v0.7.0)
- Tool annotations on every tool (`readOnlyHint`, `destructiveHint`, `idempotentHint`,
  `openWorldHint`) derived from the registry.
- Write mode `QUANTUM_ADS_WRITE_MODE=auto`: validate then apply in one call (agent autonomy);
  `confirm` (two-step) stays available.
- Optional policy engine (`QUANTUM_ADS_POLICY_FILE`): per-tenant spend caps, max budget change,
  forbidden operations, allowed hours — evaluated before apply; absent = no limits.
- MCP tasks for long-running tools (video, Veo, BigQuery runs, Meridian fit, ADH queries) with
  progress; per-tool timeouts.
- Progressive disclosure: BM25 tool search transform (`QUANTUM_ADS_TOOL_SEARCH=true`).
- Resources (capabilities, Ads sunset table, field deltas, tenant/account context) and prompts
  (weekly audit, PMax diagnosis, Search launch, budget reallocation, feed optimisation).

## Wave 2 — Google Ads, complete
- `ads.mutate`: generic `GoogleAdsService.Mutate` over every resource (partial failure,
  validate_only, response content), so nothing in the API is out of reach.
- Curated builders: Search, Performance Max, Demand Gen, AI Max campaigns end to end (budget,
  bidding, ad groups, keywords/negatives, RSA, assets, asset groups, audience signals).
- Recommendations (list / apply / dismiss), Keyword Planner ideas + forecasts, Reach Planner,
  Experiments, BatchJob bulk mutations, conversion actions, audiences, shared negative lists.
- Rollback: before-state captured for updates, inverse operation recorded in the audit.
- Simulations and auction insights in reports.

## Wave 3 — Creative studio + campaign intelligence
- Creative pipeline: Gemini copy (RSA headlines/descriptions, policy pre-check via
  validate_only) → Gemini image / free video → asset upload → asset groups.
- Monitoring: anomaly detection on spend/conversions, budget pacing, conversion-lag aware
  reporting, search-term mining with negative proposals, PMax asset insights.
- Measurement: GA4 ↔ Ads reconciliation, offline/enhanced conversions via Data Manager,
  Consent Mode diagnostics, paid/organic overlap (Search Console × Ads).
- Merchant feed optimisation (titles/descriptions rewritten, product issues fixed).
- Client reporting: Sheets/Slides decks generated from live data.

## Wave 4 — Write breadth across every other connector
- GA4 (custom dimensions/metrics, conversions, data streams, audiences), GTM (triggers,
  variables, server-side), Merchant (data sources, promotions, regional inventory),
  YouTube (uploads, thumbnails, captions), DV360/CM360/SA360 (campaign objects),
  Business Profile (posts, hours, media), BigQuery (scheduled queries, views), Looker,
  Search Console (URL inspection), Workspace (Docs, Drive organisation).

## Wave 5 — Access and distribution
- "Sign in with Google" (OAuthProxy): each user's Google token is their credential — per-user
  multi-tenancy without a tenants file; Dynamic Client Registration / CIMD.
- PyPI trusted publishing (`uvx quantum-ads-mcp`), official MCP Registry `server.json`, `.mcpb`
  one-click bundle, signed container image, Cloud Run deployment, shared rate limits.

## Wave 6 — Engineering assurance
- Agent eval harness (task suite measuring an LLM operating the server), mutation testing,
  record/replay cassettes of live calls for credential-free CI, async I/O for HTTP scale,
  typed output schemas.
