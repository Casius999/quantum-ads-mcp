"""Live boundary — smoke-gated, not unit-tested.

Real Vertex AI SDK glue: a lazy factory building the generative ReadFn dispatching the three
modalities (Gemini text / Imagen 4 images / Veo 3 video). Isolated at the untyped third-party
boundary (``vertexai.*`` and ``google.cloud.*`` are mypy-ignored; this module is coverage-omitted
via the live gate). Imports are local so importing this module stays cheap and credential-free.
SDK-derived values stay implicitly typed (``Any``) — they are never annotated, mirroring the other
connector SDK boundaries.

Auth differs from the OAuth-refresh-token connectors: Vertex AI uses Application Default
Credentials (ADC) plus a GCP project + location, derived here from the shared creds dict
(``project`` / ``location`` keys, falling back to env-configured defaults the operator sets).

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
    from vertexai.preview.generative_models import GenerativeModel
    from vertexai.preview.vision_models import ImageGenerationModel, VideoGenerationModel

    project = str(creds["project"])
    location = str(creds.get("location") or _DEFAULT_LOCATION)
    vertexai.init(project=project, location=location)

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
