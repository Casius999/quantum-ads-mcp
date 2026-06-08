from quantum_ads.core.versioning.enums import safe_enum_name


def test_known_value_passthrough():
    assert safe_enum_name("ENABLED", {"ENABLED", "PAUSED"}) == "ENABLED"


def test_unknown_value_becomes_unknown():
    assert safe_enum_name("SOME_NEW_2026_VALUE", {"ENABLED", "PAUSED"}) == "UNKNOWN"
