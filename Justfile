# Quantum ADS MCP — task runner (https://github.com/casey/just)
set shell := ["bash", "-uc"]

# Full local gate: format, lint, type-check, test.
default: check

check: fmt lint type test

fmt:
    uv run ruff format .

lint:
    uv run ruff check .

type:
    uv run mypy src

test:
    uv run pytest --cov=quantum_ads --cov-report=term-missing --cov-fail-under=95 -m "not live"

# Install git hooks (pre-commit + commit-msg).
hooks:
    uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

# Run the MCP server over stdio.
run:
    uv run python -m quantum_ads
