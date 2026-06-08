import pytest

from quantum_ads.core.registry.registry import Capability, ConnectorRegistry, ToolSpec


def test_register_and_list():
    registry = ConnectorRegistry()
    registry.register(
        Capability(
            connector="google_ads",
            domain="read",
            tools=[ToolSpec(name="ads.gaql.query", summary="Run GAQL", read_only=True)],
        )
    )
    caps = registry.list_capabilities()
    assert caps[0].connector == "google_ads"
    assert registry.describe_tool("ads.gaql.query").read_only is True
    assert {t.name for t in registry.all_tools()} == {"ads.gaql.query"}


def test_describe_unknown_raises():
    with pytest.raises(KeyError):
        ConnectorRegistry().describe_tool("nope")
