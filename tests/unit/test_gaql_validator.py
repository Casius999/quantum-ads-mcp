import datetime as dt

import pytest

from quantum_ads.core.query.gaql_validator import GaqlError, validate_gaql


def test_rejects_non_date_segment_missing_from_select():
    query = "SELECT campaign.id FROM campaign WHERE segments.device = 'MOBILE'"
    with pytest.raises(GaqlError, match="segments.device"):
        validate_gaql(query)


def test_allows_date_segment_in_where_without_select():
    query = "SELECT campaign.id FROM campaign WHERE segments.date DURING LAST_7_DAYS"
    validate_gaql(query)  # no raise


def test_rejects_or_keyword():
    query = (
        "SELECT campaign.id FROM campaign "
        "WHERE campaign.status = 'ENABLED' OR campaign.status = 'PAUSED'"
    )
    with pytest.raises(GaqlError, match="OR"):
        validate_gaql(query)


def test_rejects_multiple_from():
    with pytest.raises(GaqlError, match="single FROM"):
        validate_gaql("SELECT a FROM campaign, ad_group")


def test_rejects_lookback_beyond_37_months():
    query = (
        "SELECT campaign.id FROM campaign WHERE segments.date BETWEEN '2022-01-01' AND '2022-02-01'"
    )
    with pytest.raises(GaqlError, match="37"):
        validate_gaql(query, today=dt.date(2026, 6, 8))


def test_order_by_does_not_false_trigger_or():
    query = (
        "SELECT campaign.id, metrics.clicks FROM campaign "
        "WHERE segments.date DURING LAST_7_DAYS ORDER BY metrics.clicks DESC"
    )
    validate_gaql(query)  # 'ORDER' must not match the OR rule
