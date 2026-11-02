# Security Policy

## Supported versions

Security fixes land on the latest released minor version
([releases](https://github.com/Casius999/quantum-ads-mcp/releases)); upgrade to it to receive them.

| Version | Supported |
|---------|-----------|
| latest `0.x` release | yes |
| older releases | no |

## Reporting a vulnerability

Report privately through **GitHub private vulnerability reporting**:
<https://github.com/Casius999/quantum-ads-mcp/security/advisories/new>.
Do not open public issues, discussions or pull requests for security problems.

Please include the affected version, a description of the impact, and steps or a proof of
concept to reproduce. Expect an acknowledgement within **3 business days** and an assessment
within **10 business days**. Fixes are released as a new version with a GitHub Security
Advisory crediting the reporter (unless you prefer otherwise); please keep the issue
confidential until that advisory is published (coordinated disclosure, 90 days at most).

Out of scope: vulnerabilities in Google APIs or third-party services themselves (report those
to the vendor, e.g. <https://bughunters.google.com>), and findings that require an attacker to
already control the operator's machine or credentials.

## Secret hygiene

This repository contains **no credentials**. All secrets (Google Ads developer token, OAuth
client secret, refresh tokens) live in a local, gitignored `.env` / `google-ads.yaml`, or in CI
secrets / a secret manager — never in source or git history.

`.env`, `google-ads.yaml`, and `client_secret*.json` are gitignored, and `gitleaks` runs in CI.

If a credential is ever committed: rotate it immediately (regenerate the developer token in the
Google Ads API Center, reset the OAuth client secret in Google Cloud Console, revoke the refresh
token) and purge it from git history. Deleting the file does not undo exposure.

## Safety defaults

The server runs **read-only by default** (`QUANTUM_ADS_READ_ONLY=true`). Writes require an
explicit opt-out, then run a `validate_only` preview, a two-step confirmation and an Ed25519-signed,
hash-chained audit record (optionally anchored in Bitcoin). Over HTTP every request needs an
OAuth 2.1 bearer token (`ads:read`; `ads:write` for writes) and runs with its own tenant's
credentials only — see [docs](skill/quantum-ads/references/auth-and-guardrails.md).
