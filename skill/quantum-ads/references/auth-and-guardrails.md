# Auth & guardrails

## Credential matrix
The entrypoint (`quantum_ads/backends.py`) registers every backend whose credentials resolve from
the environment; the rest answer `BACKEND_NOT_CONFIGURED`. Backends are lazy: imports, client
construction and token refresh happen on the first tool call, not at startup.

| Needs | Environment | Connectors |
|---|---|---|
| Google Ads | `GOOGLE_ADS_DEVELOPER_TOKEN` + client id/secret + refresh token | google_ads |
| Google OAuth | `GOOGLE_OAUTH_{CLIENT_ID,CLIENT_SECRET,REFRESH_TOKEN}`, else the `GOOGLE_ADS_*` client + refresh token | ga4, gtm, merchant, datamanager, searchconsole, youtube, dv360, cm360, sa360, adh, gbp, workspace |
| OAuth + GCP project | the above + `GOOGLE_CLOUD_PROJECT` | bigquery, vertex, language, recaptcha |
| Looker API3 | `LOOKERSDK_{BASE_URL,CLIENT_ID,CLIENT_SECRET}` | looker |
| none | — | trends, meridian (local library) |

When `GOOGLE_CLOUD_PROJECT` is set it is also sent as the quota/billing project
(`x-goog-user-project`) by the OAuth connectors. `GOOGLE_VERTEX_LOCATION` overrides the Vertex
endpoint (default `global`; Imagen `:predict` and Veo, which are regional-only, fall back to
`us-central1` while the location is `global`).

## Getting the credentials
1. Google Cloud Console → enable the APIs you need → OAuth client (**Desktop**) → client id + secret.
2. Google Ads API Center → developer token (Google Ads only).
3. `uv run python scripts/get_refresh_token.py` → consent once for the scopes of the connectors
   you will use. A refresh token only reaches the APIs whose scopes it was granted.
4. Pass the values as process environment — the `env` block of your MCP client's server entry, or
   exported in the shell that launches it. The server reads `os.environ` only; it does not load
   `.env` itself (the gitignored `.env`, templated by `.env.example`, is what the live-smoke
   tests read). Install SDKs: `uv sync --extra connectors` (a missing SDK surfaces as an error
   naming that command).

Multi-tenant (per-client tokens + a secret manager) is on the roadmap; today the server is
single-tenant from the environment.

### Secret hygiene
- `.env`, `google-ads.yaml` and `client_secret*.json` are gitignored; `gitleaks` runs in CI and
  pre-commit.
- Tokens never reach the LLM and are never logged (credential objects have a redacted repr).
- If a credential is ever committed, rotate it (developer token, OAuth client secret, refresh
  token) and purge history — deletion alone does not undo exposure.

## Guardrails
- **Read-only by default:** `QUANTUM_ADS_READ_ONLY=true` refuses every write tool.
- **Guarded writes:** with read-only off, a write returns a `validate_only` preview and a confirm
  token; only a second call carrying that token executes, and it appends an Ed25519-signed audit
  record chained to the previous one by SHA-256 (`prev_hash`), so an edited, deleted or reordered
  record is detected — not only a forged one.
- **Persistent audit:** the stdio server writes `audit.jsonl` + its signing key
  `audit_ed25519.pem` (created once, mode 0600) under `QUANTUM_ADS_AUDIT_DIR`, default
  `~/.quantum-ads/audit`; set it empty to keep the ledger in memory. `audit.status` returns the
  path, record count, chain verification (first bad index) and the public key for external checks.
- **Cost:** Vertex generation and BigQuery scans bill the project — use BigQuery `dry_run`, keep
  Gemini calls small, ask before Veo (several USD per clip).
- **Version discipline:** `health` reports the pinned Ads version and days until its sunset and
  warns inside 30 days; `ads.api.version_delta` shows what changes before you move.
- **Honest reporting:** the defensible "most powerful" claim is coverage + engineering rigor +
  safety, each verifiable — never "record ad performance". State only what tests prove.
