"""Live boundary — smoke-gated, not unit-tested.

Real Vertex AI generative glue: a ReadFn dispatching the three modalities (Gemini text / Imagen
images / Veo video).

Gemini text uses a **direct REST ``generateContent`` call** against the Vertex AI ``global``
endpoint — the June-2026 SOTA path: the legacy ``vertexai.generative_models`` SDK is deprecated
(removed 2026-06-24) and Gemini 2.5 models are served from the ``global`` location, which that SDK
does not target. Imagen/Veo still go through the ``vertexai`` vision SDK (lazy-imported, regional
location) pending their own migration to REST / ``google-genai``.

Auth mirrors the other GCP connectors: OAuth user credentials from the shared creds dict, with a
``quota_project_id`` so the call bills the project where Vertex AI is enabled. Generation is
billable — callers control spend.

Python package: ``google-cloud-aiplatform`` (vision SDK) + ``google-auth`` (token for the REST call).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

# Gemini 2.5 is served from the multi-region "global" endpoint (June 2026). Imagen/Veo need a
# regional endpoint, so they fall back to this region.
_DEFAULT_LOCATION = "global"
_VISION_LOCATION = "us-central1"
_VEO_MODEL = "veo-3.0-generate-001"
_IMAGEN_MODEL = "imagen-4.0-generate-001"


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    quota = creds.get("quota_project_id") or creds.get("project")
    return Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=str(quota) if quota else None,
    )


def generative_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Vertex AI ReadFn dispatching gemini (REST) / imagen / veo (SDK) generation."""
    project = str(creds["project"])
    location = str(creds.get("location") or _DEFAULT_LOCATION)
    quota = str(creds.get("quota_project_id") or project)
    oauth = _oauth_credentials(creds)

    def _gemini(params: dict[str, object]) -> list[dict[str, object]]:
        import json
        import urllib.request

        from google.auth.transport.requests import Request

        oauth.refresh(Request())
        model = str(params["model"])
        host = (
            "aiplatform.googleapis.com"
            if location == "global"
            else f"{location}-aiplatform.googleapis.com"
        )
        url = (
            f"https://{host}/v1/projects/{project}/locations/{location}"
            f"/publishers/google/models/{model}:generateContent"
        )
        body = json.dumps(
            {
                "contents": [{"role": "user", "parts": [{"text": str(params["prompt"])}]}],
                "generationConfig": {"maxOutputTokens": int(params["max_tokens"])},
            }
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 — fixed Vertex AI host
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {oauth.token}",
                "Content-Type": "application/json",
                "x-goog-user-project": quota,
            },
        )
        with urllib.request.urlopen(request, timeout=60) as resp:  # noqa: S310
            payload = json.loads(resp.read())
        candidates = payload.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(str(p.get("text", "")) for p in parts)
        return [{"text": text}]

    def _vision_init() -> None:
        import vertexai

        vision_location = location if location != "global" else _VISION_LOCATION
        vertexai.init(project=project, location=vision_location, credentials=oauth)

    def _imagen(params: dict[str, object]) -> list[dict[str, object]]:
        _vision_init()
        from vertexai.preview.vision_models import ImageGenerationModel

        model = ImageGenerationModel.from_pretrained(_IMAGEN_MODEL)
        images = model.generate_images(
            prompt=str(params["prompt"]),
            number_of_images=int(params["n"]),
            aspect_ratio=str(params["aspect_ratio"]),
        )
        return [{"image_index": i, "mime_type": img._mime_type} for i, img in enumerate(images)]

    def _veo(params: dict[str, object]) -> list[dict[str, object]]:
        _vision_init()
        from vertexai.preview.vision_models import VideoGenerationModel

        model = VideoGenerationModel.from_pretrained(_VEO_MODEL)
        operation = model.generate_videos(
            prompt=str(params["prompt"]),
            duration_seconds=int(params["duration_seconds"]),
        )
        return [{"operation_name": operation.operation.name, "done": operation.done()}]

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "gemini": _gemini,
        "imagen": _imagen,
        "veo": _veo,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported vertex operation: {operation!r}")
        return handler(params)

    return read
