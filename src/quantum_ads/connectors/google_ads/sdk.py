"""Real Google Ads SDK glue: read stream + write mutate factories.

Isolated at the untyped third-party boundary (mypy relaxed + coverage-omitted for this module).
The mutate translation is exercised by the gated ``live`` smoke test, not unit tests.
Imports are local so importing this module stays cheap and credential-free.
"""

from __future__ import annotations

from collections.abc import Callable

StreamFn = Callable[[str, str], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]


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


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    from google.ads.googleads.client import GoogleAdsClient
    from google.api_core.protobuf_helpers import field_mask
    from google.protobuf.json_format import MessageToDict

    client = GoogleAdsClient.load_from_dict(creds, version=version)

    def _campaign_update(
        customer_id: str, op: dict[str, object], validate_only: bool
    ) -> dict[str, object]:
        service = client.get_service("CampaignService")
        operation = client.get_type("CampaignOperation")
        campaign = operation.update
        campaign.resource_name = service.campaign_path(customer_id, str(op["campaign_id"]))
        campaign.status = client.enums.CampaignStatusEnum[str(op["status"])]
        client.copy_from(operation.update_mask, field_mask(None, campaign._pb))
        response = service.mutate_campaigns(
            customer_id=customer_id, operations=[operation], validate_only=validate_only
        )
        return MessageToDict(response._pb)

    def _budget_update(
        customer_id: str, op: dict[str, object], validate_only: bool
    ) -> dict[str, object]:
        service = client.get_service("CampaignBudgetService")
        operation = client.get_type("CampaignBudgetOperation")
        budget = operation.update
        budget.resource_name = service.campaign_budget_path(customer_id, str(op["budget_id"]))
        budget.amount_micros = int(str(op["amount_micros"]))
        client.copy_from(operation.update_mask, field_mask(None, budget._pb))
        response = service.mutate_campaign_budgets(
            customer_id=customer_id, operations=[operation], validate_only=validate_only
        )
        return MessageToDict(response._pb)

    handlers = {"campaign": _campaign_update, "campaign_budget": _budget_update}

    def mutate(
        customer_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        results = []
        for op in operations:
            handler = handlers.get(str(op["entity"]))
            if handler is None:
                raise ValueError(f"unsupported mutate entity: {op.get('entity')!r}")
            results.append(handler(customer_id, op, validate_only))
        return {"validate_only": validate_only, "results": results}

    return mutate
