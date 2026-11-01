"""Google Trends "Trending now" via the public RSS feed.

pytrends' ``trending_searches`` targets an endpoint Google removed (HTTP 404, observed
2026-11-01). The public feed ``https://trends.google.com/trending/rss?geo=<ISO-2>`` is the
supported replacement: each ``<item>`` is a trending query with approximate search traffic,
its start time and the news articles driving it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_HT = "{https://trends.google.com/trending/rss}"
_FEED_URL = "https://trends.google.com/trending/rss?geo={geo}"


def trending_rss_url(geo: str) -> str:
    code = geo.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}(-[A-Z0-9]{1,3})?", code):
        raise ValueError(f"geo must be an ISO-3166 country code like 'US', got {geo!r}")
    return _FEED_URL.format(geo=code)


def _text(node: ET.Element, tag: str) -> str | None:
    child = node.find(tag)
    return child.text.strip() if child is not None and child.text else None


def parse_trending_rss(xml_text: str) -> list[dict[str, object]]:
    """Rows ``{rank, query, approx_traffic, pub_date, news[]}`` in feed order."""
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 - Google's own feed; expat refuses external entities
    except ET.ParseError as exc:
        raise ValueError(f"not a valid Trends RSS feed: {exc}") from exc
    rows: list[dict[str, object]] = []
    for rank, item in enumerate(root.findall("./channel/item")):
        news = [
            {
                "title": _text(entry, f"{_HT}news_item_title"),
                "url": _text(entry, f"{_HT}news_item_url"),
                "source": _text(entry, f"{_HT}news_item_source"),
            }
            for entry in item.findall(f"{_HT}news_item")
        ]
        rows.append(
            {
                "rank": rank,
                "query": _text(item, "title"),
                "approx_traffic": _text(item, f"{_HT}approx_traffic"),
                "pub_date": _text(item, "pubDate"),
                "news": news,
            }
        )
    return rows
