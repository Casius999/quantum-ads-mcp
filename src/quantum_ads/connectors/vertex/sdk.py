"""Live boundary — smoke-gated, not unit-tested.

Real Vertex AI SDK glue: a lazy factory building the generative ReadFn dispatching the three
modalities (Gemini text / Imagen 4 images / Veo 3 video). Isolated at the untyped third-party
boundary (``vertexai.*`` and ``google.cloud.*`` are mypy-ignored; this module is coverage-omitted
via the live gate). Imports are local so importing this module stays cheap and credential-free.
SDK-derived values stay implicitly typed (``Any``) — they are never annotated, mirroring the other
connector SDK boundaries.

Auth mirrors the other GCP connectors: build OAuth user credentials from the shared creds dict
(``client_id`` / ``client_secret`` / ``refresh_token``) and pass them to ``vertexai.init`` with the
GCP ``project`` + ``location`` and a ``quota_project_id`` (so the call bills the project where
Vertex AI is enabled, not the OAuth client's project). Generation is billable — callers control spend.

Python package: ``google-cloud-aiplatform`` (provides the ``vertexai`` namespace).
"""

from __future__ import annotations

from collections.abc import Callable

ReadFn = Callable[[str, dict[str, object]], list[dict[str, object]]]

# Veo video generation is long-running; the SDK returns an operation to poll rather than the asset.
_DEFAULT_LOCATION = "us-central1"
_VEO_MODEL = "veo-3.0-generate-001"
_IMAGEN_MODEL = "imagen-4.0-generate-001"


def generative_read_factory(creds: dict[str, object], version: str) -> ReadFn:
    """Build the Vertex AI ReadFn dispatching gemini / imagen / veo generation operations."""
    import vertexai
    from google.oauth2.credentials import Credentials
    from vertexai.preview.generative_models import GenerativeModel
    from vertexai.preview.vision_models import ImageGenerationModel, VideoGenerationModel

    project = str(creds["project"])
    location = str(creds.get("location") or _DEFAULT_LOCATION)
    quota = creds.get("quota_project_id") or project
    oauth = Credentials(
        token=None,
        refresh_token=str(creds["refresh_token"]),
        client_id=str(creds["client_id"]),
        client_secret=str(creds["client_secret"]),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=str(quota) if quota else None,
    )
    vertexai.init(project=project, location=location, credentials=oauth)

    def _gemini(params: dict[str, object]) -> list[dict[str, object]]:
        model = GenerativeModel(str(params["model"]))
        response = model.generate_content(
            str(params["prompt"]),
            generation_config={"max_output_tokens": int(params["max_tokens"])},
        )
        return [{"text": response.text}]

    def _imagen(params: dict[str, object]) -> list[dict[str, object]]:
        model = ImageGenerationModel.from_pretrained(_IMAGEN_MODEL)
        images = model.generate_images(
            prompt=str(params["prompt"]),
            number_of_images=int(params["n"]),
            aspect_ratio=str(params["aspect_ratio"]),
        )
        return [{"image_index": i, "mime_type": img._mime_type} for i, img in enumerate(images)]

    def _veo(params: dict[str, object]) -> list[dict[str, object]]:
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
