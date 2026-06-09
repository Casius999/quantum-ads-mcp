"""Load a local `.env` (repo root, gitignored) into the environment for `-m live` tests.

No dependency on python-dotenv; values already in the environment win.
"""

import os
from pathlib import Path

import pytest

# Exception type names that mean "the connector REACHED Google's API but the request was gated by an
# external prerequisite" (no account, quota 0, developer registration, allowlist) — not a code bug.
_GATE_EXC = {
    "HttpError",  # googleapiclient discovery connectors
    "PermissionDenied",
    "Unauthenticated",
    "NotFound",
    "ResourceExhausted",
    "FailedPrecondition",
    "Forbidden",
}


@pytest.fixture
def reached_or_skip():  # type: ignore[no-untyped-def]
    """Run an API call; skip (not fail) when the connector reached the API but was gated externally.

    A genuine wiring bug (unresolvable discovery, bad import, ValueError) still propagates as a
    failure — only the listed service-level gate errors are treated as "reached, externally gated".
    """

    def _call(fn):  # type: ignore[no-untyped-def]
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classified by type name
            if type(exc).__name__ in _GATE_EXC:
                pytest.skip(f"connector reached the API; gated externally: {type(exc).__name__}")
            raise

    return _call


def _load_env() -> None:
    env = Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return
    for raw in env.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()
