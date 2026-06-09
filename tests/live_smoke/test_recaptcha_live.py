"""Live conformance for the reCAPTCHA Enterprise connector (run with `pytest -m live`).

keys.list over the project (read) + a validate_only annotate preview. assessment.create is NOT
exercised live — it needs a real site key + a freshly minted frontend token, which a headless test
cannot produce. Needs a broad-scope OAuth token (cloud-platform) in GOOGLE_OAUTH_* and
GOOGLE_CLOUD_PROJECT.
"""

import os

import pytest

pytestmark = pytest.mark.live

_REQ = ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN")


def _project() -> str:
    proj = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if any(not os.environ.get(k) for k in _REQ) or not proj:
        pytest.skip("broad OAuth creds or GOOGLE_CLOUD_PROJECT missing")
    return proj


def _creds() -> dict[str, object]:
    proj = _project()
    return {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "project_id": proj,
        "quota_project_id": proj,
    }


def test_recaptcha_keys_list_live():
    from quantum_ads.connectors.recaptcha.sdk import default_read_factory

    rows = default_read_factory(_creds(), "v1")("keys.list", {"project_id": _project()})
    assert isinstance(rows, list)


def test_recaptcha_annotate_validate_only_live():
    from quantum_ads.connectors.recaptcha.sdk import default_mutate_factory

    proj = _project()
    ops: list[dict[str, object]] = [
        {
            "entity": "annotation",
            "project_id": proj,
            "assessment_id": "noop",
            "annotation": "LEGITIMATE",
        }
    ]
    out = default_mutate_factory(_creds(), "v1")(proj, ops, True)  # preview only
    assert out["validate_only"] is True
