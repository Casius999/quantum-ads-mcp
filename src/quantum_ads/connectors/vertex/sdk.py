"""Live boundary — smoke-gated, not unit-tested.

Real Vertex AI generative glue: a ReadFn dispatching Gemini text, Imagen images, Veo video and
Veo operation polling — all as **direct REST calls** to the Vertex AI ``publishers/google/models``
endpoints. No ``vertexai`` / ``google-cloud-aiplatform`` SDK: its ``generative_models`` module was
removed on 2026-06-24 and its vision wrappers lag the model releases, while the REST surface is
the stable contract Google documents for every model.

- ``gemini``     -> ``:generateContent`` on the ``global`` endpoint (where current Gemini is served).
- ``imagen``     -> image generation, returned as base64. Defaults to ``gemini-3.1-flash-image``
  (``:generateContent`` with an IMAGE response modality): the Imagen publisher models are no longer
  in the Vertex catalog (verified 2026-11-01). An explicit ``imagen-*`` model still uses ``:predict``.
- ``veo``        -> ``:predictLongRunning``; returns the operation name to poll.
- ``veo.status`` -> ``:fetchPredictOperation``; returns done/error and the video URIs or bytes.

Auth mirrors the other GCP connectors: OAuth user credentials from the shared creds dict, with a
``quota_project_id`` so calls bill the project where Vertex AI is enabled. Generation is billable —
callers control spend.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

# Current Gemini models are served from the multi-region "global" endpoint; Veo is regional, so a
# "global" configuration falls back to this region for it. Defaults verified GA in the live
# publisher catalog on 2026-11-01 (tests/live_smoke/test_vertex_catalog_conformance.py).
_DEFAULT_LOCATION = "global"
_VISION_LOCATION = "us-central1"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"
DEFAULT_VIDEO_MODEL = "veo-3.1-generate-001"
_TIMEOUT_SECONDS = 120


def _oauth_credentials(creds: dict[str, object]) -> Any:
    from google.oauth2.credentials import Credentials

    quota = creds.get("quota_project_id") or creds.get("project")
    return Credentials(
        token=creds.get("access_token"),
        refresh_token=creds.get("refresh_token"),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=str(quota) if quota else None,
    )


def _host(location: str) -> str:
    return (
        "aiplatform.googleapis.com"
        if location == "global"
        else f"{location}-aiplatform.googleapis.com"
    )


def generative_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Vertex AI ReadFn dispatching gemini / imagen / veo / veo.status over REST."""
    project = str(creds["project"])
    location = str(creds.get("location") or _DEFAULT_LOCATION)
    vision_location = location if location != "global" else _VISION_LOCATION
    quota = str(creds.get("quota_project_id") or project)
    oauth = _oauth_credentials(creds)

    def _model_url(model: str, verb: str, where: str) -> str:
        return (
            f"https://{_host(where)}/v1/projects/{project}/locations/{where}"
            f"/publishers/google/models/{model}:{verb}"
        )

    def _post(url: str, body: dict[str, object]) -> dict[str, Any]:
        from google.auth.transport.requests import Request

        if not oauth.valid:
            oauth.refresh(Request())
        request = urllib.request.Request(  # noqa: S310 — fixed Vertex AI host
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {oauth.token}",
                "Content-Type": "application/json",
                "x-goog-user-project": quota,
            },
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:  # noqa: S310
            payload: dict[str, Any] = json.loads(resp.read())
        return payload

    def _gemini(params: dict[str, object]) -> list[dict[str, object]]:
        payload = _post(
            _model_url(str(params["model"]), "generateContent", location),
            {
                "contents": [{"role": "user", "parts": [{"text": str(params["prompt"])}]}],
                "generationConfig": {"maxOutputTokens": int(str(params["max_tokens"]))},
            },
        )
        candidates = payload.get("candidates", [])
        first = candidates[0] if candidates else {}
        parts = first.get("content", {}).get("parts", [])
        # Thinking models can spend the whole max_tokens budget reasoning and return no text
        # (finish_reason MAX_TOKENS): surface the reason so an empty answer is diagnosable.
        return [
            {
                "text": "".join(str(p.get("text", "")) for p in parts),
                "finish_reason": str(first.get("finishReason", "")),
            }
        ]

    def _imagen(params: dict[str, object]) -> list[dict[str, object]]:
        model = str(params.get("model") or DEFAULT_IMAGE_MODEL)
        count = int(str(params["n"]))
        aspect_ratio = str(params["aspect_ratio"])
        if model.startswith("imagen"):
            payload = _post(
                _model_url(model, "predict", vision_location),
                {
                    "instances": [{"prompt": str(params["prompt"])}],
                    "parameters": {"sampleCount": count, "aspectRatio": aspect_ratio},
                },
            )
            images = [
                (str(p.get("mimeType", "image/png")), str(p.get("bytesBase64Encoded", "")))
                for p in payload.get("predictions", [])
            ]
        else:
            images = []
            for _ in range(count):  # one image per call: candidateCount>1 is not image-capable
                payload = _post(
                    _model_url(model, "generateContent", location),
                    {
                        "contents": [{"role": "user", "parts": [{"text": str(params["prompt"])}]}],
                        "generationConfig": {
                            "responseModalities": ["IMAGE"],
                            "imageConfig": {"aspectRatio": aspect_ratio},
                        },
                    },
                )
                for candidate in payload.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        inline = part.get("inlineData")
                        if inline:
                            images.append(
                                (str(inline.get("mimeType", "image/png")), str(inline["data"]))
                            )
        return [
            {"image_index": i, "mime_type": mime, "image_base64": data}
            for i, (mime, data) in enumerate(images)
        ]

    def _veo(params: dict[str, object]) -> list[dict[str, object]]:
        payload = _post(
            _model_url(
                str(params.get("model") or DEFAULT_VIDEO_MODEL),
                "predictLongRunning",
                vision_location,
            ),
            {
                "instances": [{"prompt": str(params["prompt"])}],
                "parameters": {
                    "durationSeconds": int(str(params["duration_seconds"])),
                    "sampleCount": 1,
                },
            },
        )
        return [{"operation_name": str(payload.get("name", "")), "done": False}]

    def _veo_status(params: dict[str, object]) -> list[dict[str, object]]:
        operation_name = str(params["operation_name"])
        # The operation name embeds the model: .../publishers/google/models/<model>/operations/<id>
        model = operation_name.split("/models/")[1].split("/")[0]
        payload = _post(
            _model_url(model, "fetchPredictOperation", vision_location),
            {"operationName": operation_name},
        )
        response = payload.get("response", {}) or {}
        videos = [
            {
                "gcs_uri": str(v.get("gcsUri", "")),
                "mime_type": str(v.get("mimeType", "video/mp4")),
                "video_base64": str(v.get("bytesBase64Encoded", "")),
            }
            for v in response.get("videos", [])
        ]
        error = payload.get("error")
        return [
            {
                "operation_name": operation_name,
                "done": bool(payload.get("done", False)),
                "error": error if error else None,
                "videos": videos,
            }
        ]

    handlers: dict[str, Callable[[dict[str, object]], list[dict[str, object]]]] = {
        "gemini": _gemini,
        "imagen": _imagen,
        "veo": _veo,
        "veo.status": _veo_status,
    }

    def read(operation: str, params: dict[str, object]) -> list[dict[str, object]]:
        handler = handlers.get(operation)
        if handler is None:
            raise ValueError(f"unsupported vertex operation: {operation!r}")
        return handler(params)

    return read
