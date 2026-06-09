"""Real Merchant API SDK glue: read (ReadFn) + write (MutateFn) factories.

Live boundary — smoke-gated, not unit-tested. Isolated at the untyped third-party boundary
(mypy relaxed + coverage-omitted for this module). Imports are local so importing this module
stays cheap and credential-free.

Targets the **Merchant API** (v1). The legacy **Content API for Shopping sunsets 2026-08-18**;
this connector does not use it. Python clients:
``google-shopping-merchant-products`` and ``google-shopping-merchant-accounts``.
"""

from __future__ import annotations

from collections.abc import Callable

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build a resource-dispatching ReadFn over the Merchant API product/account clients."""
    from google.oauth2.credentials import Credentials
    from google.protobuf.json_format import MessageToDict
    from google.shopping.merchant_accounts_v1 import AccountsServiceClient
    from google.shopping.merchant_products_v1 import ProductsServiceClient

    credentials = Credentials.from_authorized_user_info(creds)
    quota = creds.get("quota_project_id")
    if quota:
        credentials = credentials.with_quota_project(str(quota))
    products = ProductsServiceClient(credentials=credentials)
    accounts = AccountsServiceClient(credentials=credentials)

    def _account_path(merchant_id: str) -> str:
        return f"accounts/{merchant_id}"

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        if operation == "products.list":
            parent = _account_path(str(params["merchant_id"]))
            return [
                MessageToDict(p._pb, preserving_proto_field_name=True)
                for p in products.list_products(parent=parent)
            ]
        if operation == "products.get":
            product = products.get_product(name=str(params["product_name"]))
            return [MessageToDict(product._pb, preserving_proto_field_name=True)]
        if operation == "productStatuses.list":
            # Item-level issues live on each Product resource (productStatus.itemLevelIssues).
            parent = _account_path(str(params["merchant_id"]))
            return [
                MessageToDict(p._pb, preserving_proto_field_name=True)
                for p in products.list_products(parent=parent)
            ]
        if operation == "accounts.get":
            account = accounts.get_account(name=_account_path(str(params["merchant_id"])))
            return [MessageToDict(account._pb, preserving_proto_field_name=True)]
        raise ValueError(f"unsupported merchant read operation: {operation!r}")

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build an op-dispatching MutateFn over the Merchant API product-input client.

    ``validate_only`` short-circuits to a synthetic preview because the Merchant API product
    endpoints do not expose a server-side validate-only flag; the guarded preview still surfaces
    the exact op dicts that would be applied before the confirm step.
    """
    from google.oauth2.credentials import Credentials
    from google.protobuf.json_format import MessageToDict
    from google.shopping.merchant_products_v1 import (
        DeleteProductInputRequest,
        InsertProductInputRequest,
        ProductInput,
        ProductInputsServiceClient,
    )

    credentials = Credentials.from_authorized_user_info(creds)
    quota = creds.get("quota_project_id")
    if quota:
        credentials = credentials.with_quota_project(str(quota))
    inputs = ProductInputsServiceClient(credentials=credentials)

    def _account_path(merchant_id: str) -> str:
        return f"accounts/{merchant_id}"

    def _insert(merchant_id: str, op: dict[str, object]) -> dict[str, object]:
        product_input = ProductInput(op["product_input"])
        request = InsertProductInputRequest(
            parent=_account_path(merchant_id), product_input=product_input
        )
        response = inputs.insert_product_input(request=request)
        return MessageToDict(response._pb, preserving_proto_field_name=True)

    def _update(merchant_id: str, op: dict[str, object]) -> dict[str, object]:
        from google.protobuf.field_mask_pb2 import FieldMask

        fields = dict(op["fields"]) if isinstance(op["fields"], dict) else {}
        product_input = ProductInput(name=str(op["product_name"]), **fields)
        update_mask = FieldMask(paths=list(fields.keys()))
        response = inputs.update_product_input(product_input=product_input, update_mask=update_mask)
        return MessageToDict(response._pb, preserving_proto_field_name=True)

    def _delete(merchant_id: str, op: dict[str, object]) -> dict[str, object]:
        request = DeleteProductInputRequest(name=str(op["product_name"]))
        inputs.delete_product_input(request=request)
        return {"deleted": str(op["product_name"])}

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "insert": _insert,
        "update": _update,
        "delete": _delete,
    }

    def mutate(
        customer_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results = []
        for op in operations:
            handler = handlers.get(str(op["action"]))
            if handler is None:
                raise ValueError(f"unsupported merchant mutate action: {op.get('action')!r}")
            results.append(handler(customer_id, op))
        return {"validate_only": False, "results": results}

    return mutate
