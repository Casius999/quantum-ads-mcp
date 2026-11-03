"""Fit generated images to Google Ads image specs (Pillow, ``connectors`` extra).

Image models produce 16:9 or 1:1; Performance Max and Demand Gen want landscape 1.91:1
(1200x628) and square 1:1 (1200x1200). Images are centre-cropped to the target ratio and resized,
then re-encoded as PNG.
"""

from __future__ import annotations

import base64
import io

SPECS = {"landscape": (1200, 628), "square": (1200, 1200), "portrait": (960, 1200)}


def fit(image_base64: str, kind: str) -> str:
    from PIL import Image

    width, height = SPECS[kind]
    with Image.open(io.BytesIO(base64.b64decode(image_base64))) as source:
        image = source.convert("RGB")
    ratio = width / height
    if image.width / image.height > ratio:
        new_width = round(image.height * ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    else:
        new_height = round(image.width / ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    image = image.resize((width, height))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()
