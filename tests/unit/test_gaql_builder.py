from quantum_ads.core.query.gaql_builder import build_gaql
from quantum_ads.core.query.gaql_validator import validate_gaql


def test_builds_valid_query():
    query = build_gaql(
        resource="campaign",
        fields=["campaign.id", "campaign.name", "metrics.clicks"],
        where=["segments.date DURING LAST_7_DAYS"],
        order_by="metrics.clicks DESC",
        limit=50,
    )
    assert query.startswith("SELECT campaign.id, campaign.name, metrics.clicks\nFROM campaign")
    validate_gaql(query)  # builder output must be valid


def test_in_clause_helper():
    query = build_gaql(
        resource="campaign",
        fields=["campaign.id"],
        where=["campaign.status IN ('ENABLED','PAUSED')"],
    )
    validate_gaql(query)
