"""Tenant resolution + customer-id normalization.

SP0 is single-tenant: every customer id resolves to ``"default"``. SP8 replaces this
with a customer_id -> tenant map for agency multi-tenancy.
"""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"[^0-9]")


def normalize_customer_id(customer_id: str) -> str:
    """Strip dashes/spaces from a customer id (``123-456-7890`` -> ``1234567890``)."""
    return _NON_DIGITS.sub("", customer_id)


class TenantResolver:
    """Single-tenant resolver for SP0."""

    def resolve(self, customer_id: str) -> str:
        return "default"
