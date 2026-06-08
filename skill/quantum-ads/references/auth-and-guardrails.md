# Auth & guardrails

## Auth (env-var path)
1. Google Cloud Console → OAuth client (Desktop) → `client_id` + `client_secret`.
2. Google Ads API Center → developer token.
3. Generate a refresh token via the OAuth desktop flow.
4. Export the `GOOGLE_ADS_*` env vars (or a gitignored `.env`); the server calls
   `GoogleAdsClient.load_from_env(version="v24")`.

Multi-tenant (an agency with N clients) lands in SP8 (per-client tokens + Secret Manager). SP0 is
single-tenant from the environment.

### Secret hygiene
- `.env`, `google-ads.yaml`, and `client_secret*.json` are gitignored; `gitleaks` runs in CI.
- Tokens never reach the LLM and are never logged (`TenantCredentials` has a redacted repr).
- If a credential is ever committed, rotate it (developer token, OAuth client secret, refresh
  token) and purge history — deletion alone does not undo exposure.

## Guardrails
- **Read-only (SP0):** `guard_mutation` refuses writes; `QUANTUM_ADS_READ_ONLY=true` by default.
  SP1+ write tools gate behind explicit opt-out + draft→preview→confirm + `validate_only`.
- **Signed audit:** every (future) mutation appends an Ed25519-signed, tamper-evident record.
- **Version discipline:** `health` warns when the pinned version is within 30 days of sunset.
- **Honest reporting:** the defensible "most powerful" claim is coverage + engineering rigor +
  safety, each verifiable — never "record ad performance" (that depends on budget/creative and
  Google's auction, not the server). State only what tests prove.
