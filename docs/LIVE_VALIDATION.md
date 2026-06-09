# Live validation runbook

The per-connector live SDK calls (`sdk.py` modules) are **smoke-gated** — never run in CI. This is
how to verify them against real Google APIs with your own credentials.

## Safety rules (enforced by the tests)

- **Reads + `validate_only` only.** Live write checks call the API with `validate_only=True`, a dry
  run that is **never applied** — no budgets, statuses, conversions, or catalog entries change.
- **No paid calls.** Vertex generation (Imagen/Veo) and large BigQuery scans are excluded;
  BigQuery uses `dry_run` (estimate, scans nothing).
- **Credentials never touch git.** Put them in a local `.env` at the repo root — it is gitignored
  (alongside `google-ads.yaml` and `client_secret*.json`). Never commit or paste them anywhere tracked.

## 1. Provide credentials

Create `.env` at the repo root (gitignored). For the **Google Ads** connector:

```bash
GOOGLE_ADS_USE_PROTO_PLUS=True
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_LOGIN_CUSTOMER_ID=     # MCC id (digits), if applicable
# GOOGLE_ADS_TEST_CUSTOMER_ID=    # optional; otherwise the first accessible account is used
```

## 2. Install + run

```bash
uv sync --extra dev --extra connectors   # connector SDKs (skip --extra connectors for Ads-only)
uv run pytest -m live tests/live_smoke/test_google_ads_live.py -v
```

Tests `skip` automatically when their credentials are absent, so you can validate one connector at a
time. A connector that fails reveals a real `sdk.py` mismatch to fix (method name, request shape,
response parsing) — that is the point of this pass.

## Reachability — what each set of credentials covers

The leaked Google Ads credentials authorize the **`google_ads`** connector only. Every other
connector needs **its own** API enabled + OAuth scopes + account access:

| Needs its own access | Connectors |
|---|---|
| Analytics | ga4 (GA4 property) |
| Tag/measurement | gtm (container), datamanager, searchconsole (verified site) |
| Programmatic | dv360, cm360, sa360 (platform access) |
| Channels | youtube (channel), gbp (allowlisted) |
| Retail | merchant (Merchant Center) |
| Data/BI | bigquery, adh, looker (instance) |
| AI/creative | vertex (GCP project), language |
| Other | meridian, workspace, recaptcha, trends |

So a full 360° live pass requires you to supply each connector's access; the harness validates each
the moment its env vars are present.

## 3. Revoke the credentials (after validation)

The Google Ads credentials used here are compromised (they lived in a prior repo's history). Revoke
them once validation is done:

1. **Revoke the refresh token** — `curl -s -X POST "https://oauth2.googleapis.com/revoke?token=<REFRESH_TOKEN>"`, or remove the app at https://myaccount.google.com/permissions.
2. **Reset the OAuth client secret** — Google Cloud Console → APIs & Services → Credentials → the OAuth 2.0 Client → **Reset secret** (or delete the client and create a new one).
3. **Rotate the developer token** — Google Ads → Tools → API Center. If it can't be rotated in place, move to a fresh OAuth client + token.
4. Delete the local `.env`.

After rotation, the production deployment uses fresh credentials in a secret manager — never in git.
