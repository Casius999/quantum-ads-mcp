<!-- Conventional Commit title, e.g. "feat(ga4): add funnel report tool" -->

## What & why

<!-- Summary of the change and motivation. -->

## Checklist

- [ ] `just check` is green (`ruff format` + `ruff check` + `mypy --strict` + `pytest` ≥95%)
- [ ] No secrets added; gitleaks passes
- [ ] Mutations (if any) go through the guarded `WriteExecutor` (validate-only + confirm + audit)
- [ ] New live SDK calls live in a smoke-gated `sdk.py` and are **not** claimed as live-verified
- [ ] Docs updated (`README.md` / `CONNECTORS.md` / `CHANGELOG.md`) where relevant

## Notes

<!-- Breaking changes, follow-ups, live-verification still owed, etc. -->
