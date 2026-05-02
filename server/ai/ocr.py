from __future__ import annotations

import base64
import json
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


_DEFAULT_OCR_TIMEOUT_SEC = 10.0


@dataclass(frozen=True)
class OcrBox:
    text: str
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None


@dataclass(frozen=True)
class OcrAsset:
    asset_id: str
    image_bytes: bytes
    mime_type: str
    location: dict[str, Any]
    hint: str | None = None


@dataclass(frozen=True)
class OcrAssetResult:
    asset_id: str
    text: str
    boxes: list[OcrBox]


class OcrClient(Protocol):
    def recognize_images(
        self,
        assets: list[OcrAsset],
        *,
        resource_type: str,
    ) -> list[OcrAssetResult]:
        """Return text and internal bbox data for localized image assets."""


def get_configured_ocr_client() -> OcrClient | None:
    if not _env_bool("KNOWLINK_ENABLE_VIVO_OCR"):
        return None

    app_id = os.getenv("KNOWLINK_VIVO_APP_ID", "").strip()
    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    business_id = os.getenv("KNOWLINK_VIVO_OCR_BUSINESS_ID", "").strip()
    if not business_id and app_id:
        business_id = f"aigc{app_id}"
    if not app_key or not business_id:
        return None

    return VivoOcrClient(
        app_key=app_key,
        business_id=business_id,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        timeout_sec=_env_float("KNOWLINK_VIVO_OCR_TIMEOUT_SEC", _DEFAULT_OCR_TIMEOUT_SEC),
    )


class VivoOcrClient:
    def __init__(
        self,
        *,
        app_key: str,
        business_id: str,
        base_url: str,
        timeout_sec: float | None = None,
    ) -> None:
        self._app_key = app_key
        self._business_id = business_id
        self._base_url = base_url.rstrip("/")
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_OCR_TIMEOUT_SEC
        self._last_request_at = 0.0
        self._min_request_interval_sec = 0.2

    def recognize_images(
        self,
        assets: list[OcrAsset],
        *,
        resource_type: str,
    ) -> list[OcrAssetResult]:
        results: list[OcrAssetResult] = []
        for asset in assets:
            if not asset.image_bytes:
                continue
            result = self._recognize_image(asset)
            if result is not None:
                results.append(result)
        return results

    def _recognize_image(self, asset: OcrAsset) -> OcrAssetResult | None:
        self._throttle()
        body = urllib.parse.urlencode(
            {
                "image": base64.b64encode(asset.image_bytes).decode("ascii"),
                "pos": 2,
                "businessid": self._business_id,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self._ocr_base_url()}/ocr/general_recognition?requestId={uuid.uuid4()}",
            data=body,
            headers={
                "Authorization": f"Bearer {self._app_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"vivo ocr request failed: {exc}") from exc

        if int(payload.get("error_code", 0) or 0) != 0:
            raise RuntimeError(f"vivo ocr failed: {payload.get('error_msg') or payload}")

        return _parse_ocr_payload(payload, asset_id=asset.asset_id)

    def _ocr_base_url(self) -> str:
        trimmed = self._base_url.rstrip("/")
        if trimmed.endswith("/v1"):
            return trimmed[:-3]
        return trimmed

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_request_interval_sec:
            time.sleep(self._min_request_interval_sec - elapsed)
        self._last_request_at = time.monotonic()


def _parse_ocr_payload(payload: dict[str, Any], *, asset_id: str) -> OcrAssetResult | None:
    result = payload.get("result")
    if not isinstance(result, dict):
        return None

    boxes = _parse_ocr_boxes(result)
    text_parts = [box.text for box in boxes if box.text]

    words = result.get("words")
    if not text_parts and isinstance(words, list):
        for item in words:
            if isinstance(item, dict) and isinstance(item.get("words"), str):
                text_parts.append(item["words"])
            elif isinstance(item, str):
                text_parts.append(item)
    elif not text_parts and isinstance(words, str):
        text_parts.append(words)

    text = "\n".join(part.strip() for part in text_parts if part and part.strip())
    if not text:
        return None

    return OcrAssetResult(asset_id=asset_id, text=text, boxes=boxes)


def _parse_ocr_boxes(result: dict[str, Any]) -> list[OcrBox]:
    items = result.get("OCR")
    if not isinstance(items, list):
        return []

    boxes: list[OcrBox] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get("words")
        if not isinstance(text, str) or not text.strip():
            continue

        box = _location_to_box(text.strip(), item.get("location"))
        boxes.append(box)

    boxes.sort(key=lambda box: ((box.y if box.y is not None else 0), (box.x if box.x is not None else 0)))
    return boxes


def _location_to_box(text: str, location: Any) -> OcrBox:
    if not isinstance(location, dict):
        return OcrBox(text=text)

    points = []
    for key in ("top_left", "top_right", "down_right", "down_left"):
        point = location.get(key)
        if not isinstance(point, dict):
            continue
        x = _as_float(point.get("x"))
        y = _as_float(point.get("y"))
        if x is not None and y is not None:
            points.append((_normalize_coord(x), _normalize_coord(y)))

    if not points:
        return OcrBox(text=text)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left = min(xs)
    top = min(ys)
    return OcrBox(text=text, x=left, y=top, w=max(xs) - left, h=max(ys) - top)


def _normalize_coord(value: float) -> float:
    if value > 1.0 and value <= 100.0:
        value = value / 100.0
    return min(max(value, 0.0), 1.0)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _env_bool(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
