"""Load a local `.env` (repo root, gitignored) into the environment for `-m live` tests.

No dependency on python-dotenv; values already in the environment win.
"""

import os
from pathlib import Path


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
