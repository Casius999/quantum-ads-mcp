"""Real reCAPTCHA Enterprise SDK glue: read (ReadFn) + write (MutateFn) factories.

Live boundary — smoke-gated, not unit-tested. Isolated at the untyped third-party boundary
(``google.cloud.*`` is already in the mypy ignore list + this module is coverage-omitted via the
live gate). Imports are local so importing this module stays cheap and credential-free; the OAuth
credentials are derived from the shared Google creds dict. SDK-derived values stay implicitly
typed (``Any``) — they are never annotated, mirroring the Google Ads / BigQuery SDK boundary.

Targets **google-cloud-recaptcha-enterprise** (imports ``google.cloud.recaptchaenterprise_v1``).
The read plane scores a token (``create_assessment`` -> ``risk_analysis.score`` in ``[0.0, 1.0]``)
and lists site keys; the write plane feeds ``LEGITIMATE`` / ``FRAUDULENT`` ground truth back via
``annotate_assessment`` to improve the model. ``account_id`` carries the GCP project id.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]
MutateFn = Callable[[str, list[dict[str, object]], bool], dict[str, object]]

# OAuth scope for the reCAPTCHA Enterprise surface (read + annotate both ride the same scope; the
# read-only guard lives in the SafetyMode spine, not in the token).
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )


def default_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build an operation-dispatching ReadFn over the reCAPTCHA Enterprise client."""
    from google.cloud import recaptchaenterprise_v1

    client = recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient(
        credentials=_oauth_credentials(creds),
    )

    def _keys_list(params: dict[str, object]) -> list[dict[str, object]]:
        parent = f"projects/{params['project_id']}"
        return [
            {
                "name": key.name,
                "display_name": key.display_name,
            }
            for key in client.list_keys(parent=parent)
        ]

    def _assessment_create(params: dict[str, object]) -> list[dict[str, object]]:
        parent = f"projects/{params['project_id']}"
        event = recaptchaenterprise_v1.Event(
            site_key=str(params["site_key"]),
            token=str(params["token"]),
            expected_action=str(params["expected_action"]),
        )
        assessment = recaptchaenterprise_v1.Assessment(event=event)
        request = recaptchaenterprise_v1.CreateAssessmentRequest(
            parent=parent,
            assessment=assessment,
        )
        response = client.create_assessment(request)
        return [
            {
                "name": response.name,
                "score": float(response.risk_analysis.score),
                "reasons": [str(reason) for reason in response.risk_analysis.reasons],
                "valid": bool(response.token_properties.valid),
                "action": response.token_properties.action,
                "invalid_reason": str(response.token_properties.invalid_reason),
            }
        ]

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "keys.list": _keys_list,
        "assessment.create": _assessment_create,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported recaptcha read operation: {operation!r}")
        return handler(params)

    return read


def default_mutate_factory(creds: dict[str, object], version: str) -> MutateFn:
    """Build an op-dispatching MutateFn over the reCAPTCHA Enterprise client (annotate).

    ``validate_only`` short-circuits to a synthetic preview because ``annotate_assessment`` exposes
    no server-side validate-only flag; the guarded preview still surfaces the exact op dicts that
    would be applied before the confirm step. ``account_id`` carries the GCP project id.
    """
    from google.cloud import recaptchaenterprise_v1

    client = recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient(
        credentials=_oauth_credentials(creds),
    )

    def _annotate(account_id: str, op: dict[str, object]) -> dict[str, object]:
        name = f"projects/{op['project_id']}/assessments/{op['assessment_id']}"
        annotation = recaptchaenterprise_v1.AnnotateAssessmentRequest.Annotation[
            str(op["annotation"])
        ]
        request = recaptchaenterprise_v1.AnnotateAssessmentRequest(
            name=name,
            annotation=annotation,
        )
        client.annotate_assessment(request)
        return {"name": name, "annotation": str(op["annotation"])}

    handlers: dict[str, Callable[[str, dict[str, object]], dict[str, object]]] = {
        "annotation": _annotate,
    }

    def mutate(
        account_id: str, operations: list[dict[str, object]], validate_only: bool
    ) -> dict[str, object]:
        if validate_only:
            return {"validate_only": True, "preview": operations}
        results: list[dict[str, object]] = []
        for op in operations:
            handler = handlers.get(str(op["entity"]))
            if handler is None:
                raise ValueError(f"unsupported recaptcha mutate entity: {op.get('entity')!r}")
            results.append(handler(account_id, op))
        return {"validate_only": False, "results": results}

    return mutate
