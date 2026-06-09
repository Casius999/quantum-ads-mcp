"""Pure request/operation builders for the reCAPTCHA Enterprise connector.

Two kinds of builders, both pure and unit-tested directly (no SDK):

* :func:`build_assessment_request` — the params dict for ``recaptcha.assessment.create`` (read).
  Models the ``Event`` of an Assessment: the site key, the user-response token, and the action
  name the token was minted for (``expected_action``) so a mismatch can be flagged downstream.
* :func:`build_annotate_ops` — the single entity-tagged op for ``recaptcha.assessment.annotate``
  (guarded write): the ``LEGITIMATE`` / ``FRAUDULENT`` ground-truth label fed back on a prior
  assessment to improve the model.
"""

from __future__ import annotations

# Accepted annotation labels (the ground-truth verdict fed back on a prior assessment).
VALID_ANNOTATIONS = ("LEGITIMATE", "FRAUDULENT")


def build_assessment_request(
    *, project_id: str, site_key: str, token: str, expected_action: str
) -> dict[str, object]:
    """Build the params dict for creating an assessment (the core lead-quality scoring call).

    ``expected_action`` is the action name the front-end minted the token for (e.g. ``"submit"``);
    surfacing it lets the caller confirm the assessment's action matches before trusting the score.
    """
    return {
        "project_id": project_id,
        "site_key": site_key,
        "token": token,
        "expected_action": expected_action,
    }


def build_annotate_ops(
    project_id: str, assessment_id: str, annotation: str
) -> list[dict[str, object]]:
    """Build the op for annotating a prior assessment with a ground-truth label.

    ``annotation`` should be one of :data:`VALID_ANNOTATIONS` (``LEGITIMATE`` / ``FRAUDULENT``);
    it is upper-cased so callers may pass it in any case. The op is entity-tagged so the SDK
    mutate boundary can dispatch it.
    """
    op: dict[str, object] = {
        "entity": "annotation",
        "action": "annotate",
        "project_id": project_id,
        "assessment_id": assessment_id,
        "annotation": annotation.upper(),
    }
    return [op]
