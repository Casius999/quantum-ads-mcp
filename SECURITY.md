# Security Policy

## Reporting a vulnerability

Please use **GitHub private vulnerability reporting** (Security → Report a vulnerability) for this
repository. Do not open public issues for security problems.

## Secret hygiene

This repository contains **no credentials**. All secrets (Google Ads developer token, OAuth
client secret, refresh tokens) live in a local, gitignored `.env` / `google-ads.yaml`, or in CI
secrets / a secret manager — never in source or git history.

`.env`, `google-ads.yaml`, and `client_secret*.json` are gitignored, and `gitleaks` runs in CI.

If a credential is ever committed: rotate it immediately (regenerate the developer token in the
Google Ads API Center, reset the OAuth client secret in Google Cloud Console, revoke the refresh
token) and purge it from git history. Deleting the file does not undo exposure.

## Safety defaults

The server runs **read-only by default** (`QUANTUM_ADS_READ_ONLY=true`). Mutations (SP1+) are
gated behind an explicit opt-out plus per-operation confirmation and `validate_only` previews.
