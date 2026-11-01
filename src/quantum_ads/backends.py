"""Wire every connector's live backend from the environment for the stdio entrypoint.

Each connector reads its data-access object from ``ctx.backend(key)`` and answers
``BACKEND_NOT_CONFIGURED`` when the key is absent. This module maps every backend key to the
connector's ``sdk.py`` factory and builds the set the environment can actually serve:

- Google connectors share one OAuth user credential (``GOOGLE_OAUTH_*``, falling back to the
  ``GOOGLE_ADS_*`` client + refresh token) and, where the API is a GCP one, ``GOOGLE_CLOUD_PROJECT``
  (billing / quota project).
- Looker uses its own API3 credentials (``LOOKERSDK_*``); Trends and Meridian need none; free
  video (Hugging Face Spaces) needs none but uses ``HF_TOKEN`` when set for a larger quota.

Backends are **lazy**: nothing is imported, built or authenticated at startup (an auth failure in
one connector must not take the whole server down). The real backend is built on first call and
reused; a missing SDK surfaces as an error naming the install command.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

# What a backend needs from the environment before it is registered.
_OAUTH = "oauth"  # Google OAuth user credential
_PROJECT = "project"  # Google OAuth + a GCP project
_LOOKER = "looker"  # Looker API3 credentials
_NONE = "none"  # no credentials (public / local library)
_HF = "huggingface"  # public Spaces; an optional free HF_TOKEN raises the quota


@dataclass(frozen=True)
class BackendSpec:
    """One backend key -> the connector sdk factory that builds it."""

    module: str
    factory: str
    needs: str
    version: str = ""  # "" lets each sdk use its own default API version


BACKENDS: dict[str, BackendSpec] = {
    "ga4.data": BackendSpec("ga4", "data_read_factory", _OAUTH),
    "ga4.admin": BackendSpec("ga4", "admin_read_factory", _OAUTH),
    "ga4.admin.mutate": BackendSpec("ga4", "admin_mutate_factory", _OAUTH),
    "gtm.api": BackendSpec("gtm", "default_read_factory", _OAUTH),
    "gtm.mutate": BackendSpec("gtm", "default_mutate_factory", _OAUTH),
    "merchant.api": BackendSpec("merchant", "default_read_factory", _OAUTH),
    "merchant.mutate": BackendSpec("merchant", "default_mutate_factory", _OAUTH),
    "datamanager.read": BackendSpec("datamanager", "default_read_factory", _OAUTH, "v1"),
    "datamanager.api": BackendSpec("datamanager", "default_mutate_factory", _OAUTH, "v1"),
    "searchconsole.api": BackendSpec("searchconsole", "read_factory", _OAUTH),
    "searchconsole.mutate": BackendSpec("searchconsole", "mutate_factory", _OAUTH),
    "youtube.data": BackendSpec("youtube", "data_read_factory", _OAUTH),
    "youtube.analytics": BackendSpec("youtube", "analytics_read_factory", _OAUTH),
    "youtube.mutate": BackendSpec("youtube", "mutate_factory", _OAUTH),
    "dv360.api": BackendSpec("dv360", "default_read_factory", _OAUTH),
    "dv360.mutate": BackendSpec("dv360", "default_mutate_factory", _OAUTH),
    "cm360.api": BackendSpec("cm360", "default_read_factory", _OAUTH),
    "cm360.mutate": BackendSpec("cm360", "default_mutate_factory", _OAUTH),
    "sa360.api": BackendSpec("sa360", "read_factory", _OAUTH),
    "sa360.mutate": BackendSpec("sa360", "mutate_factory", _OAUTH),
    "adh.api": BackendSpec("adh", "read_factory", _OAUTH),
    "adh.mutate": BackendSpec("adh", "mutate_factory", _OAUTH),
    "gbp.api": BackendSpec("gbp", "read_factory", _OAUTH),
    "gbp.reviews": BackendSpec("gbp", "reviews_read_factory", _OAUTH),
    "gbp.mutate": BackendSpec("gbp", "mutate_factory", _OAUTH),
    "workspace.api": BackendSpec("workspace", "read_factory", _OAUTH),
    "workspace.mutate": BackendSpec("workspace", "mutate_factory", _OAUTH),
    "bigquery.api": BackendSpec("bigquery", "default_read_factory", _PROJECT),
    "bigquery.mutate": BackendSpec("bigquery", "default_mutate_factory", _PROJECT),
    "recaptcha.api": BackendSpec("recaptcha", "default_read_factory", _PROJECT),
    "recaptcha.mutate": BackendSpec("recaptcha", "default_mutate_factory", _PROJECT),
    "language.api": BackendSpec("language", "language_read_factory", _PROJECT),
    "vertex.api": BackendSpec("vertex", "generative_read_factory", _PROJECT),
    "looker.api": BackendSpec("looker", "read_factory", _LOOKER),
    "looker.mutate": BackendSpec("looker", "mutate_factory", _LOOKER),
    "trends.api": BackendSpec("trends", "read_factory", _NONE),
    "meridian.api": BackendSpec("meridian", "mmm_read_factory", _NONE),
    "video.free": BackendSpec("video", "free_video_factory", _HF),
}

_INSTALL_HINT = "install the connector SDKs: `uv sync --extra connectors`"


class LazyBackend:
    """A backend built on first call (import + factory + auth happen then, not at startup)."""

    def __init__(self, key: str, spec: BackendSpec, creds: dict[str, object]) -> None:
        self.key = key
        self._spec = spec
        self._creds = creds
        self._built: Callable[..., Any] | None = None

    def _build(self) -> Callable[..., Any]:
        sdk = importlib.import_module(f"quantum_ads.connectors.{self._spec.module}.sdk")
        factory = getattr(sdk, self._spec.factory)
        try:
            built: Callable[..., Any] = factory(self._creds, self._spec.version)
        except ImportError as exc:
            raise RuntimeError(f"{self.key}: missing SDK ({exc.name}); {_INSTALL_HINT}") from exc
        return built

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self._built is None:
            self._built = self._build()
        return self._built(*args, **kwargs)


def _google_oauth(env: Mapping[str, str]) -> dict[str, object] | None:
    client_id = env.get("GOOGLE_OAUTH_CLIENT_ID") or env.get("GOOGLE_ADS_CLIENT_ID")
    secret = env.get("GOOGLE_OAUTH_CLIENT_SECRET") or env.get("GOOGLE_ADS_CLIENT_SECRET")
    refresh = env.get("GOOGLE_OAUTH_REFRESH_TOKEN") or env.get("GOOGLE_ADS_REFRESH_TOKEN")
    if not (client_id and secret and refresh):
        return None
    return {"client_id": client_id, "client_secret": secret, "refresh_token": refresh}


def _creds_for(needs: str, env: Mapping[str, str]) -> dict[str, object] | None:
    """Credentials for one requirement class, or None when the environment cannot serve it."""
    if needs == _NONE:
        return {}
    if needs == _HF:
        token = env.get("HF_TOKEN") or env.get("HUGGING_FACE_HUB_TOKEN")
        return {"hf_token": token} if token else {}
    if needs == _LOOKER:
        url, cid, secret = (
            env.get(f"LOOKERSDK_{k}") for k in ("BASE_URL", "CLIENT_ID", "CLIENT_SECRET")
        )
        return (
            {"base_url": url, "client_id": cid, "client_secret": secret}
            if url and cid and secret
            else None
        )
    oauth = _google_oauth(env)
    if oauth is None:
        return None
    project = env.get("GOOGLE_CLOUD_PROJECT", "")
    if needs == _PROJECT and not project:
        return None
    if project:
        oauth.update(project=project, project_id=project, quota_project_id=project)
    if env.get("GOOGLE_VERTEX_LOCATION"):
        oauth["location"] = env["GOOGLE_VERTEX_LOCATION"]
    return oauth


def build_backends(env: Mapping[str, str]) -> dict[str, object]:
    """Every backend the environment can serve, keyed as the connectors expect."""
    resolved = {needs: _creds_for(needs, env) for needs in {s.needs for s in BACKENDS.values()}}
    return {
        key: LazyBackend(key, spec, dict(creds))
        for key, spec in BACKENDS.items()
        if (creds := resolved[spec.needs]) is not None
    }
