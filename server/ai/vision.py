from __future__ import annotations

import base64
import json
import os
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal, Protocol


VisionSegmentType = Literal["ocr_text", "formula", "image_caption"]
_DEFAULT_VISION_MODEL = "Doubao-Seed-2.0-mini"
_DEFAULT_VISION_TIMEOUT_SEC = 20.0
_DEFAULT_VISION_BATCH_SIZE = 2
_VISION_SYSTEM_PROMPT = """你是 KnowLink 的学习资料视觉解析器。请分析图片中的教学内容，只返回 JSON，不要返回 Markdown 或解释。
JSON 格式固定为：
{"segments":[{"assetId":"...","segmentType":"ocr_text|formula|image_caption","textContent":"..."}]}
规则：
1. 图片中可读正文、题干、选项、表格文字输出为 ocr_text。
2. 公式、集合符号、数学表达式、推导关系输出为 formula。
3. 图表、Venn 图、流程图、坐标图或结构关系输出为 image_caption，用一句到三句说明图中语义。
4. 不要输出低价值碎片，例如单个字母、页码、装饰符号。
5. 文字必须使用原图语言；数学符号尽量还原为 Unicode 符号。
6. 每条 segments 必须填写对应图片清单中的 assetId。
7. 文件上下文已经包含文本层内容；只输出上下文缺失或明显不完整的图片内容，不要重复已有文本。
8. 复杂页面按阅读顺序输出完整 ocr_text block；表格用 Markdown table；公式尽量内联到原句，避免把一句话拆成多个碎片。
"""


@dataclass(frozen=True)
class VisualAsset:
    asset_id: str
    image_bytes: bytes
    mime_type: str
    location: dict[str, Any]
    hint: str | None = None


@dataclass(frozen=True)
class VisionResult:
    segment_type: VisionSegmentType
    text: str


@dataclass(frozen=True)
class VisionAssetResult:
    asset_id: str
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

    def analyze_images(
        self,
        assets: list[VisualAsset],
        *,
        resource_type: str,
        document_context: str | None = None,
    ) -> list[VisionAssetResult]:
        """Return OCR/formula/caption segments for localized visual assets."""


class VisionModelUnsupportedError(RuntimeError):
    """Raised when the configured model cannot accept image input."""


def get_configured_vision_client() -> VisionClient | None:
    if not _env_bool("KNOWLINK_ENABLE_VIVO_VISION"):
        return None

    app_id = os.getenv("KNOWLINK_VIVO_APP_ID", "").strip()
    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    return VivoVisionClient(
        app_id=app_id,
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        model=os.getenv("KNOWLINK_VIVO_VISION_MODEL", _DEFAULT_VISION_MODEL),
        timeout_sec=_env_float("KNOWLINK_VIVO_VISION_TIMEOUT_SEC", _DEFAULT_VISION_TIMEOUT_SEC),
    )


def get_configured_vision_batch_size() -> int:
    return _env_int("KNOWLINK_VIVO_VISION_BATCH_SIZE", _DEFAULT_VISION_BATCH_SIZE, minimum=1, maximum=20)


def analyze_visual_assets(
    client: VisionClient,
    assets: list[VisualAsset],
    *,
    resource_type: str,
    document_context: str | None = None,
) -> list[VisionAssetResult]:
    analyze_images = getattr(client, "analyze_images", None)
    if callable(analyze_images):
        return analyze_images(assets, resource_type=resource_type, document_context=document_context)

    results: list[VisionAssetResult] = []
    for asset in assets:
        for result in client.analyze_image(
            asset.image_bytes,
            mime_type=asset.mime_type,
            resource_type=resource_type,
            location=asset.location,
            hint=asset.hint,
        ):
            results.append(
                VisionAssetResult(
                    asset_id=asset.asset_id,
                    segment_type=result.segment_type,
                    text=result.text,
                )
            )
    return results


class VivoVisionClient:
    def __init__(
        self,
        *,
        app_id: str,
        app_key: str,
        base_url: str,
        model: str,
        timeout_sec: float | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_key = app_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_VISION_TIMEOUT_SEC
        self._last_request_at = 0.0
        self._min_request_interval_sec = 0.8

    def analyze_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        resource_type: str,
        location: dict[str, Any],
        hint: str | None = None,
    ) -> list[VisionResult]:
        if not image_bytes:
            return []

        asset = VisualAsset(
            asset_id="image-1",
            image_bytes=image_bytes,
            mime_type=mime_type,
            location=location,
            hint=hint,
        )
        results = self.analyze_images([asset], resource_type=resource_type)
        return [VisionResult(segment_type=result.segment_type, text=result.text) for result in results]

    def analyze_images(
        self,
        assets: list[VisualAsset],
        *,
        resource_type: str,
        document_context: str | None = None,
    ) -> list[VisionAssetResult]:
        clean_assets = [asset for asset in assets if asset.image_bytes]
        if not clean_assets:
            return []

        try:
            return self._request_analyze_images(
                clean_assets,
                resource_type=resource_type,
                document_context=document_context,
            )
        except RuntimeError as exc:
            if len(clean_assets) <= 1 or not _should_retry_single(str(exc)):
                raise

        results: list[VisionAssetResult] = []
        for asset in clean_assets:
            results.extend(
                self._request_analyze_images(
                    [asset],
                    resource_type=resource_type,
                    document_context=document_context,
                )
            )
        return results

    def _request_analyze_images(
        self,
        assets: list[VisualAsset],
        *,
        resource_type: str,
        document_context: str | None,
    ) -> list[VisionAssetResult]:
        self._throttle()
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": _build_batch_prompt(
                    resource_type=resource_type,
                    assets=assets,
                    document_context=document_context,
                ),
            }
        ]
        for index, asset in enumerate(assets, start=1):
            content.append({"type": "text", "text": _asset_label(index, asset)})
            content.append({"type": "image_url", "image_url": {"url": _data_url(asset.image_bytes, asset.mime_type)}})

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.1,
            "max_tokens": 2048,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{_chat_base_url(self._base_url)}/chat/completions?request_id={uuid.uuid4()}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._app_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                raise RuntimeError(f"vivo multimodal http {exc.code}: {body}") from exc
            _raise_vivo_vision_error(payload, prefix=f"vivo multimodal http {exc.code}")
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError(f"vivo multimodal request failed: {exc}") from exc

        default_asset_id = assets[0].asset_id if len(assets) == 1 else None
        return _parse_chat_response(json.loads(body), default_asset_id=default_asset_id)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_request_interval_sec:
            time.sleep(self._min_request_interval_sec - elapsed)
        self._last_request_at = time.monotonic()


def _build_batch_prompt(
    *,
    resource_type: str,
    assets: list[VisualAsset],
    document_context: str | None,
) -> str:
    asset_manifest = [
        {
            "assetId": asset.asset_id,
            "location": asset.location,
            "hint": asset.hint or "visual_content",
        }
        for asset in assets
    ]
    context = clean_context(document_context)
    return "\n".join(
        [
            _VISION_SYSTEM_PROMPT,
            f"资源类型：{resource_type}",
            f"文件上下文：{context or '无'}",
            f"图片清单：{json.dumps(asset_manifest, ensure_ascii=False, sort_keys=True)}",
        ]
    )


def _asset_label(index: int, asset: VisualAsset) -> str:
    location_text = json.dumps(asset.location, ensure_ascii=False, sort_keys=True)
    return f"图片 {index}: assetId={asset.asset_id}; location={location_text}; hint={asset.hint or 'visual_content'}"


def _data_url(image_bytes: bytes, mime_type: str) -> str:
    mime = mime_type if mime_type.startswith("image/") else "image/png"
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{image_base64}"


def _chat_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def _parse_chat_response(payload: dict[str, Any], *, default_asset_id: str | None) -> list[VisionAssetResult]:
    error = _error_from_payload(payload)
    if error is not None:
        _raise_vivo_vision_error(error, prefix="vivo multimodal failed")

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("vivo multimodal response missing message content") from exc

    text = _message_content_to_text(content)
    return _parse_model_content(text, default_asset_id=default_asset_id)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "\n".join(text for text in texts if text)
    return str(content)


def _parse_model_content(content: str, *, default_asset_id: str | None) -> list[VisionAssetResult]:
    json_text = _extract_json_object(content)
    if json_text is None:
        text = content.strip()
        if default_asset_id is not None and text:
            return [VisionAssetResult(asset_id=default_asset_id, segment_type="image_caption", text=text)]
        return []

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        text = content.strip()
        if default_asset_id is not None and text:
            return [VisionAssetResult(asset_id=default_asset_id, segment_type="image_caption", text=text)]
        return []

    segments = payload.get("segments")
    if isinstance(segments, list):
        results: list[VisionAssetResult] = []
        for item in segments:
            if not isinstance(item, dict):
                continue
            asset_id = item.get("assetId") or item.get("asset_id") or default_asset_id
            segment_type = item.get("segmentType") or item.get("type")
            text = item.get("textContent") or item.get("text")
            if (
                isinstance(asset_id, str)
                and asset_id.strip()
                and segment_type in ("ocr_text", "formula", "image_caption")
                and isinstance(text, str)
                and text.strip()
            ):
                results.append(VisionAssetResult(asset_id=asset_id.strip(), segment_type=segment_type, text=text))
        return results

    return []


def _extract_json_object(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return stripped[start : end + 1]


def clean_context(text: str | None) -> str:
    if not text:
        return ""
    compact = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return compact[:4000]


def is_vision_model_unsupported_error(exc: BaseException) -> bool:
    return isinstance(exc, VisionModelUnsupportedError) or _is_model_unsupported_error(str(exc))


def _error_from_payload(payload: dict[str, Any]) -> Any | None:
    if "error" in payload:
        return payload["error"]
    if "choices" not in payload and any(
        key in payload for key in ("code", "error_code", "errorCode", "message", "error_msg")
    ):
        return payload
    return None


def _raise_vivo_vision_error(error: Any, *, prefix: str) -> None:
    message = f"{prefix}: {_format_error(error)}"
    if _is_model_unsupported_error(error):
        raise VisionModelUnsupportedError(message)
    raise RuntimeError(message)


def _is_model_unsupported_error(error: Any) -> bool:
    code = _error_code(error)
    text = _format_error(error).lower()
    return code == "1010" or "model do not support image input" in text or "model does not support image input" in text


def _error_code(error: Any) -> str:
    if not isinstance(error, dict):
        return ""
    value = error.get("code") or error.get("error_code") or error.get("errorCode")
    return str(value).strip()


def _format_error(error: Any) -> str:
    if not isinstance(error, dict):
        return str(error)
    code = _error_code(error)
    message = error.get("message") or error.get("error_msg") or error.get("errorMessage")
    if code and message:
        return f"code={code} message={message}"
    if code:
        return f"code={code}"
    if message:
        return str(message)
    return str(error)


def _should_retry_single(message: str) -> bool:
    lower = message.lower()
    return any(token in lower for token in ("multiple", "too many", "image_url", "content item", "asset"))


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return min(max(parsed, minimum), maximum)
