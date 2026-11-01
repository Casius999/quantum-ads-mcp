"""Where the per-tenant credential map comes from: a local file or Google Secret Manager.

``QUANTUM_ADS_TENANTS_FILE`` keeps the map in a file (convenient, but plaintext on disk);
``QUANTUM_ADS_TENANTS_SECRET`` keeps it in Secret Manager — encrypted at rest, IAM-controlled,
versioned and access-logged — and reads it once at startup with the operator's Google OAuth
credential (``GOOGLE_OAUTH_*`` / ``GOOGLE_ADS_*`` client + refresh token; the token needs the
``cloud-platform`` scope and the secret ``roles/secretmanager.secretAccessor``). The value is the
same JSON as the file: ``{"tenants": {"<id>": {"GOOGLE_...": "..."}}}``. Neither set: the server
is single-tenant on the operator environment.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..tenancy import BackendBuilder, TenantDirectory

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_ACCESS_URL = "https://secretmanager.googleapis.com/v1/{name}:access"
_TIMEOUT_S = 20

# (secret version name, access token, quota project) -> secret payload text.
AccessFn = Callable[[str, str, str | None], str]
TokenFn = Callable[[Mapping[str, str]], str]


class SecretSourceError(ValueError):
    """The tenant credential source is misconfigured or unreadable."""


def secret_version_name(ref: str, project: str | None) -> str:
    """Accept ``name``, ``projects/p/secrets/name`` or a full version name."""
    ref = ref.strip()
    if ref.startswith("projects/"):
        return ref if "/versions/" in ref else f"{ref}/versions/latest"
    if not project:
        raise SecretSourceError(
            "a bare QUANTUM_ADS_TENANTS_SECRET name needs GOOGLE_CLOUD_PROJECT (or use "
            "projects/<project>/secrets/<name>)"
        )
    return f"projects/{project}/secrets/{ref}/versions/latest"


def decode_payload(response: Mapping[str, Any]) -> str:
    data = (response.get("payload") or {}).get("data")
    if not isinstance(data, str):
        raise SecretSourceError("Secret Manager response has no payload data")
    return base64.b64decode(data).decode("utf-8")


def _post_json(url: str, form: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(form).encode()
    with urllib.request.urlopen(url, body, timeout=_TIMEOUT_S) as response:  # noqa: S310
        return json.loads(response.read())  # type: ignore[no-any-return]


def operator_access_token(env: Mapping[str, str]) -> str:
    """Exchange the operator's refresh token for an access token."""
    client_id = env.get("GOOGLE_OAUTH_CLIENT_ID") or env.get("GOOGLE_ADS_CLIENT_ID")
    secret = env.get("GOOGLE_OAUTH_CLIENT_SECRET") or env.get("GOOGLE_ADS_CLIENT_SECRET")
    refresh = env.get("GOOGLE_OAUTH_REFRESH_TOKEN") or env.get("GOOGLE_ADS_REFRESH_TOKEN")
    if not (client_id and secret and refresh):
        raise SecretSourceError("reading tenants from Secret Manager needs GOOGLE_OAUTH_* creds")
    reply = _post_json(
        _TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
    )
    return str(reply["access_token"])


def access_secret(name: str, access_token: str, quota_project: str | None) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    if quota_project:
        headers["x-goog-user-project"] = quota_project
    request = urllib.request.Request(_ACCESS_URL.format(name=name), headers=headers)
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:  # noqa: S310
        return decode_payload(json.loads(response.read()))


def load_tenants(
    env: Mapping[str, str],
    builder: BackendBuilder,
    *,
    access: AccessFn = access_secret,
    token: TokenFn = operator_access_token,
) -> TenantDirectory | None:
    """The tenant directory from the configured source, or None (single-tenant)."""
    file_ref = env.get("QUANTUM_ADS_TENANTS_FILE") or ""
    secret_ref = env.get("QUANTUM_ADS_TENANTS_SECRET") or ""
    if file_ref and secret_ref:
        raise SecretSourceError(
            "set one of QUANTUM_ADS_TENANTS_FILE or QUANTUM_ADS_TENANTS_SECRET, not both"
        )
    if file_ref:
        return TenantDirectory.from_file(Path(file_ref).expanduser(), builder)
    if not secret_ref:
        return None
    project = env.get("GOOGLE_CLOUD_PROJECT") or None
    name = secret_version_name(secret_ref, project)
    payload = access(name, token(env), project)
    return TenantDirectory.from_json(payload, builder, source=name)
