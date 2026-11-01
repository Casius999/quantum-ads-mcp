"""The skill's tool catalog is generated from the registry; fail if the committed copy drifts."""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gen_tool_catalog.py"


def _generator():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("gen_tool_catalog", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_tool_catalog_matches_registry():
    gen = _generator()
    committed = gen.CATALOG_PATH.read_text(encoding="utf-8")
    assert committed == gen.render_catalog(), (
        "skill/quantum-ads/references/tool-catalog.md is stale: "
        "run `uv run python scripts/gen_tool_catalog.py`"
    )
