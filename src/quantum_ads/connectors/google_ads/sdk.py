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

    from .write.operations import validate_operations
    from .write.rollback import (
        before_state_query,
        created_names,
        inverse_of_creates,
        inverse_of_update,
        mask_paths,
    )

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

        service = client.get_service("GoogleAdsService")
        mutate_type = type(client.get_type("MutateOperation"))
        request = client.get_type("MutateGoogleAdsRequest")
        request.customer_id = customer_id
        for parsed in validate_operations(list(op["operations"]), version):  # type: ignore[arg-type]
            request.mutate_operations.append(mutate_type.deserialize(parsed.SerializeToString()))
        request.partial_failure = bool(op.get("partial_failure", False))
        request.validate_only = validate_only
        request.response_content_type = client.enums.ResponseContentTypeEnum.MUTABLE_RESOURCE
        undo_updates = [] if validate_only else _before_state(customer_id, op["operations"])
        response = service.mutate(request=request)
        out = MessageToDict(response._pb, preserving_proto_field_name=True)
        if not validate_only:
            undo_creates = [
                inverse
                for kind, name in created_names(out)
                if kind in _created_kinds(op["operations"])
                for inverse in inverse_of_creates(kind, [name])
            ]
            # Undo in reverse order: removing created children before their parents.
            out["inverse_operations"] = list(reversed(undo_creates)) + undo_updates
            out["irreversible_operations"] = sum(
                1 for item in op["operations"] if "remove" in next(iter(item.values()))
            )
        return out

    def _created_kinds(operations: list[dict[str, object]]) -> set[str]:
        return {kind for item in operations for kind, body in item.items() if "create" in body}

    def _before_state(
        customer_id: str, operations: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Inverse updates restoring the current value of every field an update will change."""
        search = client.get_service("GoogleAdsService")
        inverses: list[dict[str, object]] = []
        for item in operations:
            kind, body = next(iter(item.items()))
            if "update" not in body:
                continue
            name = str(body["update"]["resource_name"])
            paths = mask_paths(body)
            rows = list(
                search.search(customer_id=customer_id, query=before_state_query(kind, name, paths))
            )
            row = MessageToDict(rows[0]._pb, preserving_proto_field_name=True) if rows else {}
            inverses.append(inverse_of_update(kind, name, paths, row))
        return inverses

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

    def _experiment(
        customer_id: str, op: dict[str, object], validate_only: bool
    ) -> dict[str, object]:
        """Schedule / promote / end an experiment (each RPC supports validate_only)."""
        service = client.get_service("ExperimentService")
        name = str(op["resource_name"])
        action = str(op["entity"]).removeprefix("experiment_")
        if action == "schedule":
            result = service.schedule_experiment(resource_name=name, validate_only=validate_only)
        elif action == "promote":
            result = service.promote_experiment(resource_name=name, validate_only=validate_only)
        else:
            service.end_experiment(experiment=name, validate_only=validate_only)
            return {"experiment": name, "action": "end", "validate_only": validate_only}
        operation = getattr(result, "operation", None) or result
        return {
            "experiment": name,
            "action": action,
            "validate_only": validate_only,
            "long_running_operation": getattr(operation, "name", None)
            if not validate_only
            else None,
        }

    def _batch_submit(
        customer_id: str, op: dict[str, object], validate_only: bool
    ) -> dict[str, object]:
        """BatchJob for large mutations; the preview validates every chunk with Mutate."""
        operations = list(op["operations"])  # type: ignore[call-overload]
        parsed = validate_operations(operations, version)
        mutate_type = type(client.get_type("MutateOperation"))
        protos = [mutate_type.deserialize(m.SerializeToString()) for m in parsed]
        if validate_only:
            service = client.get_service("GoogleAdsService")
            for start in range(0, len(protos), 5000):
                request = client.get_type("MutateGoogleAdsRequest")
                request.customer_id = customer_id
                request.mutate_operations.extend(protos[start : start + 5000])
                request.validate_only = True
                request.partial_failure = True
                service.mutate(request=request)
            return {"validate_only": True, "operations": len(protos)}
        service = client.get_service("BatchJobService")
        job_operation = client.get_type("BatchJobOperation")
        job_operation.create = client.get_type("BatchJob")
        created = service.mutate_batch_job(customer_id=customer_id, operation=job_operation)
        job = created.result.resource_name
        sequence_token = ""
        for start in range(0, len(protos), 5000):
            added = service.add_batch_job_operations(
                resource_name=job,
                sequence_token=sequence_token,
                mutate_operations=protos[start : start + 5000],
            )
            sequence_token = added.next_sequence_token
        run = service.run_batch_job(resource_name=job)
        return {
            "batch_job": job,
            "operations": len(protos),
            "long_running_operation": run.operation.name,
        }

    handlers = {
        "campaign": _campaign_update,
        "campaign_budget": _budget_update,
        "mutate": _generic,
        "experiment_schedule": _experiment,
        "experiment_promote": _experiment,
        "experiment_end": _experiment,
        "batch_submit": _batch_submit,
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
        out: dict[str, object] = {"validate_only": validate_only, "results": results}
        inverses = [inv for r in results for inv in r.pop("inverse_operations", [])]
        if inverses:
            out["inverse_operations"] = inverses
        return out

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

    def batch_status(params: dict[str, object]) -> list[dict[str, object]]:
        from google.protobuf.json_format import MessageToDict

        customer_id, job = str(params["customer_id"]), str(params["batch_job"])
        search = client.get_service("GoogleAdsService")
        rows = list(
            search.search(
                customer_id=customer_id,
                query=(
                    "SELECT batch_job.resource_name, batch_job.status, "
                    "batch_job.metadata.operation_count, batch_job.metadata.executed_operation_count "
                    f"FROM batch_job WHERE batch_job.resource_name = '{job}'"
                ),
            )
        )
        if not rows:
            return [{"batch_job": job, "status": "NOT_FOUND"}]
        info = MessageToDict(rows[0].batch_job._pb, preserving_proto_field_name=True)
        out: dict[str, object] = {"batch_job": job, **info}
        if rows[0].batch_job.status.name == "DONE":
            results = client.get_service("BatchJobService").list_batch_job_results(
                resource_name=job
            )
            items = []
            for result in results:
                item = MessageToDict(result._pb, preserving_proto_field_name=True)
                items.append(item)
                if len(items) >= int(params.get("limit") or 100):
                    break
            out["results"] = items
            out["failed"] = sum(1 for item in items if item.get("status"))
        return [out]

    def reach_locations(params: dict[str, object]) -> list[dict[str, object]]:
        response = client.get_service("ReachPlanService").list_plannable_locations()
        return [
            {
                "id": loc.id,
                "name": loc.name,
                "parent_country_id": loc.parent_country_id,
                "country_code": loc.country_code,
                "location_type": loc.location_type,
            }
            for loc in response.plannable_locations
        ]

    def reach_products(params: dict[str, object]) -> list[dict[str, object]]:
        response = client.get_service("ReachPlanService").list_plannable_products(
            plannable_location_id=str(params["location_id"])
        )
        return [
            {"code": p.plannable_product_code, "name": p.plannable_product_name}
            for p in response.product_metadata
        ]

    def reach_forecast(params: dict[str, object]) -> list[dict[str, object]]:
        from google.protobuf.json_format import MessageToDict

        request = client.get_type("GenerateReachForecastRequest")
        request.customer_id = str(params["customer_id"])
        request.currency_code = str(params["currency_code"])
        request.campaign_duration.duration_in_days = int(params["duration_days"])
        request.targeting.plannable_location_id = str(params["location_id"])
        for product in params["products"]:  # type: ignore[union-attr]
            planned = client.get_type("PlannedProduct")
            planned.plannable_product_code = str(product["code"])
            planned.budget_micros = int(product["budget_micros"])
            request.planned_products.append(planned)
        response = client.get_service("ReachPlanService").generate_reach_forecast(request=request)
        curve = MessageToDict(response._pb, preserving_proto_field_name=True)
        return [
            {
                "reach_curve": curve.get("reach_curve", {}),
                "on_target_audience_metrics": curve.get("on_target_audience_metrics", {}),
            }
        ]

    operations = {
        "keyword_ideas": keyword_ideas,
        "batch_status": batch_status,
        "reach_locations": reach_locations,
        "reach_products": reach_products,
        "reach_forecast": reach_forecast,
    }

    def call(op: str, params: dict[str, object]) -> list[dict[str, object]]:
        if op not in operations:
            raise ValueError(f"unsupported Google Ads service operation: {op!r}")
        return operations[op](params)

    return call
