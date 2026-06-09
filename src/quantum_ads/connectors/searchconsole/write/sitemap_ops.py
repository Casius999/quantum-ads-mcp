"""Pure operation builders for Search Console sitemap mutations.

Each builder returns a list with a single entity-tagged op dict. The ``entity``/``action`` keys
let the SDK mutate boundary dispatch to the right Search Console call (sitemaps.submit /
sitemaps.delete); the remaining keys carry the property + sitemap feed path. These are pure and
unit-tested directly (no SDK needed).
"""

from __future__ import annotations


def build_submit_sitemap_ops(site_url: str, feedpath: str) -> list[dict[str, object]]:
    """Build the op to submit (PUT) a sitemap feed path for a property."""
    op: dict[str, object] = {
        "entity": "sitemap",
        "action": "submit",
        "site_url": site_url,
        "feedpath": feedpath,
    }
    return [op]


def build_delete_sitemap_ops(site_url: str, feedpath: str) -> list[dict[str, object]]:
    """Build the op to delete a sitemap feed path for a property."""
    op: dict[str, object] = {
        "entity": "sitemap",
        "action": "delete",
        "site_url": site_url,
        "feedpath": feedpath,
    }
    return [op]
