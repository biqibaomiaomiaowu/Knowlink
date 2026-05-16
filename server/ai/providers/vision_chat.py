from __future__ import annotations

import base64
from typing import Any, Sequence

from server.ai.core.errors import AIConfigurationError
from server.ai.core.types import VisionImage


def image_to_data_url(image: VisionImage) -> str:
    mime_type = image.mime_type.strip().lower()
    if not mime_type.startswith("image/"):
        raise AIConfigurationError(f"vision image MIME type must start with image/: {image.mime_type}")
    payload = base64.b64encode(image.data).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def build_vision_content(prompt: str, images: Sequence[VisionImage]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image in images:
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(image)}})
    return content
