from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal, Protocol


VisionSegmentType = Literal["ocr_text", "formula", "image_caption"]


@dataclass(frozen=True)
class VisionResult:
    segment_type: VisionSegmentType
    text: str


class VisionClient(Protocol):
    def analyze_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        resource_type: str,
        location: dict[str, Any],
        hint: str | None = None,
    ) -> list[VisionResult]:
        """Return OCR/formula/caption segments for one localized visual asset."""


def get_configured_vision_client() -> VisionClient | None:
    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    return VivoVisionClient(
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        model=os.getenv("KNOWLINK_VIVO_VISION_MODEL", "vivo-vision"),
    )


class VivoVisionClient:
    def __init__(self, *, app_key: str, base_url: str, model: str) -> None:
        self._app_key = app_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    def analyze_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        resource_type: str,
        location: dict[str, Any],
        hint: str | None = None,
    ) -> list[VisionResult]:
        payload = {
            "model": self._model,
            "image": base64.b64encode(image_bytes).decode("ascii"),
            "mimeType": mime_type,
            "resourceType": resource_type,
            "location": location,
            "hint": hint,
        }
        request = urllib.request.Request(
            f"{self._base_url}/vision/analyze",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._app_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError(f"vivo vision request failed: {exc}") from exc

        return _parse_vivo_response(json.loads(body))


def _parse_vivo_response(payload: dict[str, Any]) -> list[VisionResult]:
    segments = payload.get("segments")
    if isinstance(segments, list):
        results: list[VisionResult] = []
        for item in segments:
            if not isinstance(item, dict):
                continue
            segment_type = item.get("segmentType") or item.get("type")
            text = item.get("textContent") or item.get("text")
            if segment_type in ("ocr_text", "formula", "image_caption") and isinstance(text, str):
                results.append(VisionResult(segment_type=segment_type, text=text))
        if results:
            return results

    result = payload.get("result")
    words = _extract_ocr_words(result)
    if words:
        return [VisionResult(segment_type="ocr_text", text="\n".join(words))]
    return []


def _extract_ocr_words(result: Any) -> list[str]:
    if not isinstance(result, dict):
        return []

    words_payload = result.get("words")
    if isinstance(words_payload, list):
        return [item["words"] for item in words_payload if isinstance(item, dict) and isinstance(item.get("words"), str)]

    ocr_payload = result.get("OCR")
    if isinstance(ocr_payload, list):
        return [item["words"] for item in ocr_payload if isinstance(item, dict) and isinstance(item.get("words"), str)]

    nested = result.get("result")
    if isinstance(nested, dict):
        return _extract_ocr_words(nested)
    return []
