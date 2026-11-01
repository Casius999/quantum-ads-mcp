"""Parser for the public Google Trends "Trending now" RSS feed (replaces pytrends' dead endpoint)."""

from __future__ import annotations

import pytest

from quantum_ads.connectors.trends.read.rss import parse_trending_rss, trending_rss_url

_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<title>Daily Search Trends</title>
<item>
  <title>first query</title>
  <ht:approx_traffic>2000+</ht:approx_traffic>
  <pubDate>Sun, 1 Nov 2026 00:50:00 -0700</pubDate>
  <ht:news_item>
    <ht:news_item_title>Headline A</ht:news_item_title>
    <ht:news_item_url>https://news.example/a</ht:news_item_url>
    <ht:news_item_source>Example News</ht:news_item_source>
  </ht:news_item>
  <ht:news_item>
    <ht:news_item_title>Headline B</ht:news_item_title>
    <ht:news_item_url>https://news.example/b</ht:news_item_url>
    <ht:news_item_source>Other</ht:news_item_source>
  </ht:news_item>
</item>
<item><title>second query</title><ht:approx_traffic>100+</ht:approx_traffic></item>
</channel></rss>"""


def test_items_become_ranked_rows_with_traffic_and_news():
    rows = parse_trending_rss(_FEED)
    assert [r["query"] for r in rows] == ["first query", "second query"]
    assert [r["rank"] for r in rows] == [0, 1]
    assert rows[0]["approx_traffic"] == "2000+"
    assert rows[0]["pub_date"] == "Sun, 1 Nov 2026 00:50:00 -0700"
    assert rows[0]["news"] == [
        {"title": "Headline A", "url": "https://news.example/a", "source": "Example News"},
        {"title": "Headline B", "url": "https://news.example/b", "source": "Other"},
    ]
    assert rows[1]["news"] == [] and rows[1]["pub_date"] is None


def test_empty_feed_has_no_rows():
    assert parse_trending_rss('<rss version="2.0"><channel/></rss>') == []


def test_malformed_feed_raises():
    with pytest.raises(ValueError, match="RSS"):
        parse_trending_rss("<html>not a feed")


def test_url_uses_the_iso_country_code():
    assert trending_rss_url("fr") == "https://trends.google.com/trending/rss?geo=FR"
    with pytest.raises(ValueError, match="geo"):
        trending_rss_url("France")
