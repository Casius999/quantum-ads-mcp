"""Free text-to-video connector: ``video.generate`` over Hugging Face ZeroGPU Spaces.

The no-billing counterpart to paid Vertex Veo (``vertex.veo.generate``): Wan 2.2 first, LTX-Video
as fallback, with a structured ``QUOTA_EXHAUSTED`` error when the free daily GPU quota runs out.
"""

from __future__ import annotations

from .connector import register_video

__all__ = ["register_video"]
