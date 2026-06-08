"""Real Google Ads SDK glue: build a GoogleAdsClient and a search_stream function.

Isolated at the untyped third-party boundary (mypy relaxed for this module in pyproject).
Imports are local so importing this module stays cheap and credential-free.
"""

from __future__ import annotations

from collections.abc import Callable

StreamFn = Callable[[str, str], list[dict[str, object]]]


def default_stream_factory(creds: dict[str, object], version: str) -> StreamFn:
    from google.ads.googleads.client import GoogleAdsClient
    from google.protobuf.json_format import MessageToDict

    client = GoogleAdsClient.load_from_dict(creds, version=version)
    service = client.get_service("GoogleAdsService")

    def stream(customer_id: str, query: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for batch in service.search_stream(customer_id=customer_id, query=query):
            for row in batch.results:
                rows.append(MessageToDict(row._pb, preserving_proto_field_name=True))
        return rows

    return stream
