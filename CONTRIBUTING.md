# Contributing to Quantum ADS MCP

Thanks for your interest. This project is a sovereign Google marketing-agency control plane over
the Model Context Protocol.

## Ground rules

- **Read-only by default.** Anything that mutates a live account goes through the core
  `WriteExecutor` (validate-only preview → two-step confirm → signed audit). Don't bypass it.
- **No secrets, ever.** `.env`, `google-ads.yaml`, and `client_secret*.json` are gitignored and
  `gitleaks` runs in CI. Credentials load from env / a secret manager and must never reach the LLM.
- **Honest claims.** Document only what the test suite proves. Per-connector live SDK glue lives in
  `sdk.py` modules and is smoke-gated — never present it as live-verified unless it is.

## Dev setup

```bash
uv sync --extra dev
uv run pytest -m "not live"
```

Or with [`just`](https://github.com/casey/just): `just check` (format, lint, type, test).

## Quality gates (CI enforces these)

- `ruff format --check` + `ruff check`
- `mypy --strict` over `src`
- `pytest` with a **≥95% coverage gate**
- `gitleaks`, CodeQL, OpenSSF Scorecard

Run them locally before pushing: `just check`.

## Adding a connector

Copy an existing connector under `src/quantum_ads/connectors/` (e.g. `ga4/`). Each connector:
reaches its API via `ctx.backend("<key>")`; guards writes with the core `WriteExecutor`; keeps the
live SDK in a smoke-gated `sdk.py`; ships fakes-based tests (no real SDK import). Then register it in
`src/quantum_ads/server.py` (`DEFAULT_CONNECTORS` + `_CONNECTOR_BY_NAME`) and add its `sdk.py` to the
mypy `ignore_errors` + coverage `omit` lists in `pyproject.toml`. See `CONNECTORS.md`.

## Commits & PRs

- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:`).
- Keep `main` linear (the ruleset blocks force-push / deletion / non-linear history).
- Open a PR; CI must be green.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — use private vulnerability reporting, not public issues.
