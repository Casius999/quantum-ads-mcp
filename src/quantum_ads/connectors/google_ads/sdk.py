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
        request = client.get_type("MutateCampaignsRequest")
        request.customer_id = customer_id
        request.operations.append(operation)
        request.validate_only = validate_only
        response = service.mutate_campaigns(request=request)
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
        request = client.get_type("MutateCampaignBudgetsRequest")
        request.customer_id = customer_id
        request.operations.append(operation)
        request.validate_only = validate_only
        response = service.mutate_campaign_budgets(request=request)
        return MessageToDict(response._pb)

    def _generic(customer_id: str, op: dict[str, object], validate_only: bool) -> dict[str, object]:
        """GoogleAdsService.Mutate over any resource, atomic unless partial_failure."""
        from .write.operations import validate_operations

        service = client.get_service("GoogleAdsService")
        mutate_type = type(client.get_type("MutateOperation"))
        request = client.get_type("MutateGoogleAdsRequest")
        request.customer_id = customer_id
        for parsed in validate_operations(list(op["operations"]), version):  # type: ignore[arg-type]
            request.mutate_operations.append(mutate_type.deserialize(parsed.SerializeToString()))
        request.partial_failure = bool(op.get("partial_failure", False))
        request.validate_only = validate_only
        request.response_content_type = client.enums.ResponseContentTypeEnum.MUTABLE_RESOURCE
        response = service.mutate(request=request)
        return MessageToDict(response._pb, preserving_proto_field_name=True)

    def _recommendations(
        customer_id: str, op: dict[str, object], validate_only: bool
    ) -> dict[str, object]:
        """Apply/dismiss recommendations; the preview checks they exist (no validate_only RPC)."""
        names = [str(n) for n in op["resource_names"]]  # type: ignore[union-attr]
        if validate_only:
            quoted = ", ".join(f"'{n}'" for n in names)
            rows = client.get_service("GoogleAdsService").search(
                customer_id=customer_id,
                query=(
                    "SELECT recommendation.resource_name, recommendation.type, "
                    "recommendation.dismissed FROM recommendation "
                    f"WHERE recommendation.resource_name IN ({quoted})"
                ),
            )
            found = {row.recommendation.resource_name: row for row in rows}
            missing = [n for n in names if n not in found]
            if missing:
                raise ValueError(f"recommendations not found or no longer active: {missing}")
            return {
                "validate_only": True,
                "recommendations": [
                    {"resource_name": n, "type": found[n].recommendation.type_.name} for n in names
                ],
            }
        service = client.get_service("RecommendationService")
        if op["entity"] == "recommendation_apply":
            operations = []
            for name in names:
                operation = client.get_type("ApplyRecommendationOperation")
                operation.resource_name = name
                operations.append(operation)
            response = service.apply_recommendation(
                customer_id=customer_id, operations=operations, partial_failure=True
            )
        else:
            request = client.get_type("DismissRecommendationRequest")
            request.customer_id = customer_id
            request.partial_failure = True
            for name in names:
                item = type(request).DismissRecommendationOperation()
                item.resource_name = name
                request.operations.append(item)
            response = service.dismiss_recommendation(request=request)
        return MessageToDict(response._pb, preserving_proto_field_name=True)

    handlers = {
        "campaign": _campaign_update,
        "campaign_budget": _budget_update,
        "mutate": _generic,
        "recommendation_apply": _recommendations,
        "recommendation_dismiss": _recommendations,
    }

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


ServicesFn = Callable[[str, dict[str, object]], list[dict[str, object]]]


def default_services_factory(creds: dict[str, object], version: str) -> ServicesFn:
    """Read-only Google Ads planning services (Keyword Planner ideas)."""
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_dict(creds, version=version)

    def keyword_ideas(params: dict[str, object]) -> list[dict[str, object]]:
        service = client.get_service("KeywordPlanIdeaService")
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = str(params["customer_id"])
        request.language = f"languageConstants/{params['language_id']}"
        request.geo_target_constants.extend(
            f"geoTargetConstants/{g}" for g in params.get("geo_target_ids") or []
        )
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
        request.page_size = int(params.get("limit") or 50)
        keywords = [str(k) for k in params.get("keywords") or []]
        url = params.get("url")
        if keywords and url:
            request.keyword_and_url_seed.url = str(url)
            request.keyword_and_url_seed.keywords.extend(keywords)
        elif keywords:
            request.keyword_seed.keywords.extend(keywords)
        else:
            request.url_seed.url = str(url)
        rows: list[dict[str, object]] = []
        for idea in service.generate_keyword_ideas(request=request):
            metrics = idea.keyword_idea_metrics
            rows.append(
                {
                    "keyword": idea.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches,
                    "competition": metrics.competition.name,
                    "competition_index": metrics.competition_index,
                    "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros,
                    "high_top_of_page_bid_micros": metrics.high_top_of_page_bid_micros,
                }
            )
            if len(rows) >= request.page_size:
                break
        return rows

    operations = {"keyword_ideas": keyword_ideas}

    def call(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op not in operations:
            raise ValueError(f"unsupported Google Ads service operation: {op!r}")
        return operations[op](params)

    return call
