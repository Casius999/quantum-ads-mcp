from quantum_ads.core.auth.tenant import TenantResolver, normalize_customer_id


def test_normalize_customer_id_strips_dashes():
    assert normalize_customer_id("123-456-7890") == "1234567890"


def test_normalize_customer_id_strips_spaces():
    assert normalize_customer_id("123 456 7890") == "1234567890"


def test_default_resolver_maps_to_default():
    assert TenantResolver().resolve("123-456-7890") == "default"
