from __future__ import annotations

import json
import os
import re
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence

from server.parsers.base import clean_text


GenerationStatus = Literal["pending", "generating", "ready", "failed"]
_DEFAULT_OUTLINE_MODEL = "Doubao-Seed-2.0-mini"
_DEFAULT_HANDOUT_TIMEOUT_SEC = 40.0
_OUTLINE_SYSTEM_PROMPT = """你是 KnowLink 的视频讲义目录生成器。只返回 JSON，不要返回 Markdown 或解释。
JSON 格式固定为：
{"title":"...","summary":"...","items":[{"outlineKey":"outline-1","title":"...","summary":"...","startSec":0,"endSec":60,"sortNo":1,"generationStatus":"pending","sourceSegmentKeys":["mp4-c1"],"topicTags":["..."]}]}
规则：
1. 目录只基于输入 video_caption segments 生成，不能虚构视频外内容。
2. 每个 item 的 sourceSegmentKeys 必须来自输入 segmentKey。
3. startSec/endSec 必须覆盖 sourceSegmentKeys 对应字幕的时间范围，按 sortNo 递增且不得重叠。
4. generationStatus 固定返回 pending；完整讲义和知识点后续按 block 懒生成。
5. 标题要短，摘要用 1 句中文说明该段学习重点。
"""


@dataclass(frozen=True)
class HandoutOutlineGeneration:
    outline: dict[str, Any]
    issues: list[str]
    used_fallback: bool


class HandoutOutlineClient(Protocol):
    def generate_outline(
        self,
        caption_segments: Sequence[Mapping[str, Any]],
        *,
        title: str = "视频时间轴目录",
        summary: str = "基于视频字幕快速生成的讲义目录。",
        document_context: str | None = None,
    ) -> dict[str, Any]:
        """Return a schema-compatible handout outline for timestamped captions."""


def get_configured_handout_outline_client() -> HandoutOutlineClient | None:
    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    return VivoHandoutOutlineClient(
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        model=os.getenv("KNOWLINK_VIVO_OUTLINE_MODEL", _DEFAULT_OUTLINE_MODEL),
        timeout_sec=_env_float("KNOWLINK_VIVO_HANDOUT_TIMEOUT_SEC", _DEFAULT_HANDOUT_TIMEOUT_SEC),
    )


def generate_handout_outline(
    caption_segments: Sequence[Mapping[str, Any]],
    *,
    client: HandoutOutlineClient | None = None,
    title: str = "视频时间轴目录",
    summary: str = "基于视频字幕快速生成的讲义目录。",
    document_context: str | None = None,
    max_block_duration_sec: int = 180,
) -> HandoutOutlineGeneration:
    configured_client = client if client is not None else get_configured_handout_outline_client()
    if configured_client is None:
        return HandoutOutlineGeneration(
            outline=build_handout_outline_from_captions(
                caption_segments,
                title=title,
                summary=summary,
                max_block_duration_sec=max_block_duration_sec,
            ),
            issues=["outline.llm_not_configured"],
            used_fallback=True,
        )

    try:
        outline = configured_client.generate_outline(
            caption_segments,
            title=title,
            summary=summary,
            document_context=document_context,
        )
    except Exception:
        return HandoutOutlineGeneration(
            outline=build_handout_outline_from_captions(
                caption_segments,
                title=title,
                summary=summary,
                max_block_duration_sec=max_block_duration_sec,
            ),
            issues=["outline.llm_failed"],
            used_fallback=True,
        )

    issues = outline_timeline_issues(outline.get("items", []))
    if issues:
        return HandoutOutlineGeneration(
            outline=build_handout_outline_from_captions(
                caption_segments,
                title=title,
                summary=summary,
                max_block_duration_sec=max_block_duration_sec,
            ),
            issues=issues,
            used_fallback=True,
        )
    return HandoutOutlineGeneration(outline=outline, issues=[], used_fallback=False)


def build_handout_outline_from_captions(
    caption_segments: Sequence[Mapping[str, Any]],
    *,
    title: str = "视频时间轴目录",
    summary: str = "基于视频字幕快速生成的讲义目录。",
    max_block_duration_sec: int = 180,
) -> dict[str, Any]:
    captions = _valid_video_captions(caption_segments)
    if not captions:
        raise ValueError("at least one valid video_caption segment is required")

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_start: int | None = None

    for caption in captions:
        if not current_group:
            current_start = caption["startSec"]
            current_group.append(caption)
            continue

        if caption["endSec"] - int(current_start) > max_block_duration_sec:
            groups.append(current_group)
            current_group = [caption]
            current_start = caption["startSec"]
        else:
            current_group.append(caption)

    if current_group:
        groups.append(current_group)

    return {
        "title": title,
        "summary": summary,
        "items": _normalize_outline_item_boundaries(
            [_outline_item_from_group(group, index) for index, group in enumerate(groups, start=1)]
        ),
    }


class VivoHandoutOutlineClient:
    def __init__(
        self,
        *,
        app_key: str,
        base_url: str,
        model: str,
        timeout_sec: float | None = None,
    ) -> None:
        self._app_key = app_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_HANDOUT_TIMEOUT_SEC
        self._last_request_at = 0.0
        self._min_request_interval_sec = 0.8

    def generate_outline(
        self,
        caption_segments: Sequence[Mapping[str, Any]],
        *,
        title: str = "视频时间轴目录",
        summary: str = "基于视频字幕快速生成的讲义目录。",
        document_context: str | None = None,
    ) -> dict[str, Any]:
        captions = _valid_video_captions(caption_segments)
        if not captions:
            raise RuntimeError("vivo outline requires at least one valid video_caption segment")

        self._throttle()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _OUTLINE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_outline_prompt(
                        captions,
                        title=title,
                        summary=summary,
                        document_context=document_context,
                    ),
                },
            ],
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
            chat_payload = json.loads(body)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"vivo outline request failed: {exc}") from exc

        return _parse_outline_chat_response(chat_payload, captions=captions, title=title, summary=summary)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_request_interval_sec:
            time.sleep(self._min_request_interval_sec - elapsed)
        self._last_request_at = time.monotonic()


def outline_timeline_issues(items: Sequence[Mapping[str, Any]]) -> list[str]:
    issues: list[str] = []
    max_seen_end: int | None = None
    previous_sort_no = 0
    seen_keys: set[str] = set()

    for item in items:
        outline_key = str(item.get("outlineKey") or "")
        if not outline_key:
            issues.append("outline.key_missing")
        elif outline_key in seen_keys:
            issues.append("outline.key_duplicate")
        seen_keys.add(outline_key)

        sort_no = _as_int(item.get("sortNo"))
        if sort_no is None or sort_no <= previous_sort_no:
            issues.append("outline.sort_not_increasing")
        else:
            previous_sort_no = sort_no

        start_sec = _as_int(item.get("startSec"))
        end_sec = _as_int(item.get("endSec"))
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            issues.append("outline.time_invalid")
            continue

        if max_seen_end is not None and start_sec < max_seen_end:
            issues.append("outline.time_overlap")
        max_seen_end = end_sec if max_seen_end is None else max(max_seen_end, end_sec)

    return issues


def current_outline_item(
    items: Sequence[Mapping[str, Any]],
    *,
    current_sec: int,
) -> Mapping[str, Any] | None:
    ordered = _ordered_outline_items(items)
    for index, item in enumerate(ordered):
        start_sec = int(item["startSec"])
        end_sec = int(item["endSec"])
        is_last = index == len(ordered) - 1
        if start_sec <= current_sec < end_sec or (is_last and current_sec == end_sec):
            return item
    return None


def jump_target_for_outline_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "outlineKey": item["outlineKey"],
        "startSec": item["startSec"],
        "endSec": item["endSec"],
    }


def next_prefetch_outline_item(
    items: Sequence[Mapping[str, Any]],
    *,
    current_sec: int,
    threshold_sec: int = 15,
) -> Mapping[str, Any] | None:
    ordered = _ordered_outline_items(items)
    active = current_outline_item(ordered, current_sec=current_sec)
    if active is None:
        return None

    active_index = ordered.index(active)
    if int(active["endSec"]) - current_sec > threshold_sec:
        return None
    if active_index + 1 >= len(ordered):
        return None

    candidate = ordered[active_index + 1]
    if candidate.get("generationStatus") != "pending":
        return None
    return candidate


def _valid_video_captions(caption_segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    captions: list[dict[str, Any]] = []
    for index, segment in enumerate(caption_segments, start=1):
        if segment.get("segmentType") != "video_caption":
            continue

        start_sec = _as_int(segment.get("startSec"))
        end_sec = _as_int(segment.get("endSec"))
        text_content = clean_text(str(segment.get("textContent") or ""))
        if start_sec is None or end_sec is None or end_sec <= start_sec or not text_content:
            continue

        segment_key = str(segment.get("segmentKey") or f"caption-{index}")
        order_no = _as_int(segment.get("orderNo")) or index
        captions.append(
            {
                "segmentKey": segment_key,
                "orderNo": order_no,
                "textContent": text_content,
                "startSec": start_sec,
                "endSec": end_sec,
            }
        )

    return sorted(captions, key=lambda item: (item["startSec"], item["orderNo"], item["segmentKey"]))


def _build_outline_prompt(
    captions: Sequence[Mapping[str, Any]],
    *,
    title: str,
    summary: str,
    document_context: str | None,
) -> str:
    caption_groups = _outline_prompt_groups(captions)
    context = _clean_context(document_context)
    return "\n".join(
        [
            f"课程标题：{title}",
            f"默认摘要：{summary}",
            f"补充资料上下文：{context or '无'}",
            "请基于以下 video_caption segments 的预分组生成目录。每个 group 建议对应一个 outline item；"
            "可以合并相邻 group，但不要拆分 group 内的 sourceSegmentKeys。",
            f"video_caption groups：{json.dumps(caption_groups, ensure_ascii=False, sort_keys=True)}",
        ]
    )


def _outline_prompt_groups(
    captions: Sequence[Mapping[str, Any]],
    *,
    max_block_duration_sec: int = 180,
    max_text_chars: int = 900,
) -> list[dict[str, Any]]:
    groups: list[list[Mapping[str, Any]]] = []
    current_group: list[Mapping[str, Any]] = []
    current_start: int | None = None

    for caption in captions:
        if not current_group:
            current_start = int(caption["startSec"])
            current_group.append(caption)
            continue

        if int(caption["endSec"]) - int(current_start) > max_block_duration_sec:
            groups.append(current_group)
            current_group = [caption]
            current_start = int(caption["startSec"])
        else:
            current_group.append(caption)

    if current_group:
        groups.append(current_group)

    return [
        {
            "groupKey": f"group-{index}",
            "sourceSegmentKeys": [str(item["segmentKey"]) for item in group],
            "startSec": int(group[0]["startSec"]),
            "endSec": int(group[-1]["endSec"]),
            "textContent": _truncate_text("\n".join(str(item["textContent"]) for item in group), max_text_chars),
        }
        for index, group in enumerate(groups, start=1)
    ]


def _parse_outline_chat_response(
    payload: dict[str, Any],
    *,
    captions: Sequence[Mapping[str, Any]],
    title: str,
    summary: str,
) -> dict[str, Any]:
    if "error" in payload:
        raise RuntimeError(f"vivo outline failed: {payload['error']}")

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("vivo outline response missing message content") from exc

    text = _message_content_to_text(content)
    json_text = _extract_json_object(text)
    if json_text is None:
        raise RuntimeError("vivo outline response is not JSON")

    try:
        model_payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"vivo outline response has invalid JSON: {exc}") from exc

    return _normalize_model_outline(model_payload, captions=captions, title=title, summary=summary)


def _normalize_model_outline(
    payload: Any,
    *,
    captions: Sequence[Mapping[str, Any]],
    title: str,
    summary: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("vivo outline JSON must be an object")

    caption_by_key = {str(item["segmentKey"]): item for item in captions}
    items_payload = payload.get("items")
    if not isinstance(items_payload, list) or not items_payload:
        raise RuntimeError("vivo outline JSON missing non-empty items")

    normalized_items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for raw_item in items_payload:
        if not isinstance(raw_item, dict):
            continue

        source_keys = _valid_source_segment_keys(raw_item.get("sourceSegmentKeys"), caption_by_key)
        if not source_keys:
            source_keys = _source_keys_from_time_range(raw_item, captions)
        if not source_keys:
            continue

        source_captions = [caption_by_key[key] for key in source_keys]
        outline_key = _stable_outline_key(str(raw_item.get("outlineKey") or ""), len(normalized_items) + 1, seen_keys)
        seen_keys.add(outline_key)
        source_text = "\n".join(str(item["textContent"]) for item in source_captions)
        normalized_items.append(
            {
                "outlineKey": outline_key,
                "title": clean_text(str(raw_item.get("title") or "")) or _short_title(
                    source_text,
                    fallback=f"第 {len(normalized_items) + 1} 段",
                ),
                "summary": clean_text(str(raw_item.get("summary") or "")) or _truncate_text(source_text, 72),
                "startSec": min(int(item["startSec"]) for item in source_captions),
                "endSec": max(int(item["endSec"]) for item in source_captions),
                "sortNo": len(normalized_items) + 1,
                "generationStatus": "pending",
                "sourceSegmentKeys": source_keys,
                "topicTags": _clean_topic_tags(raw_item.get("topicTags")),
            }
        )

    if not normalized_items:
        raise RuntimeError("vivo outline JSON produced no valid items")

    normalized_items = sorted(normalized_items, key=lambda item: (item["startSec"], item["endSec"], item["outlineKey"]))
    for index, item in enumerate(normalized_items, start=1):
        item["sortNo"] = index
    normalized_items = _normalize_outline_item_boundaries(normalized_items)

    issues = outline_timeline_issues(normalized_items)
    if issues:
        raise RuntimeError(f"vivo outline timeline invalid: {issues}")

    return {
        "title": clean_text(str(payload.get("title") or "")) or title,
        "summary": clean_text(str(payload.get("summary") or "")) or summary,
        "items": normalized_items,
    }


def _valid_source_segment_keys(value: Any, caption_by_key: Mapping[str, Mapping[str, Any]]) -> list[str]:
    if not isinstance(value, list):
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for item in value:
        key = str(item or "")
        if key in caption_by_key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _source_keys_from_time_range(raw_item: Mapping[str, Any], captions: Sequence[Mapping[str, Any]]) -> list[str]:
    start_sec = _as_int(raw_item.get("startSec"))
    end_sec = _as_int(raw_item.get("endSec"))
    if start_sec is None or end_sec is None or end_sec <= start_sec:
        return []

    keys: list[str] = []
    for caption in captions:
        caption_start = int(caption["startSec"])
        caption_end = int(caption["endSec"])
        if caption_start < end_sec and caption_end > start_sec:
            keys.append(str(caption["segmentKey"]))
    return keys


def _stable_outline_key(candidate: str, index: int, seen_keys: set[str]) -> str:
    key = re.sub(r"[^a-zA-Z0-9._:-]+", "-", candidate).strip("-._:")
    if not key or not re.match(r"^[a-zA-Z0-9]", key):
        key = f"outline-{index}"
    base_key = key
    suffix = 2
    while key in seen_keys:
        key = f"{base_key}-{suffix}"
        suffix += 1
    return key


def _clean_topic_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = clean_text(str(item or ""))
        if tag and tag not in seen:
            tags.append(tag)
            seen.add(tag)
    return tags[:8]


def _normalize_outline_item_boundaries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    previous_end: int | None = None
    for item in items:
        clean_item = dict(item)
        start_sec = int(clean_item["startSec"])
        end_sec = int(clean_item["endSec"])
        if previous_end is not None and start_sec < previous_end < end_sec:
            clean_item["startSec"] = previous_end
            start_sec = previous_end
        if end_sec <= start_sec:
            continue
        normalized.append(clean_item)
        previous_end = end_sec
    return normalized


def _outline_item_from_group(group: list[dict[str, Any]], index: int) -> dict[str, Any]:
    text = clean_text("\n".join(item["textContent"] for item in group))
    title = _short_title(text, fallback=f"第 {index} 段")
    return {
        "outlineKey": f"outline-{index}",
        "title": title,
        "summary": _truncate_text(text, 72),
        "startSec": group[0]["startSec"],
        "endSec": group[-1]["endSec"],
        "sortNo": index,
        "generationStatus": "pending",
        "sourceSegmentKeys": [item["segmentKey"] for item in group],
        "topicTags": [],
    }


def _ordered_outline_items(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    clean_items = [
        item
        for item in items
        if _as_int(item.get("startSec")) is not None
        and _as_int(item.get("endSec")) is not None
        and _as_int(item.get("endSec")) > _as_int(item.get("startSec"))
    ]
    return sorted(clean_items, key=lambda item: (int(item.get("startSec", 0)), int(item.get("sortNo", 0))))


def _chat_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "\n".join(text for text in texts if text)
    return str(content)


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


def _clean_context(text: str | None) -> str:
    if not text:
        return ""
    compact = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return compact[:4000]


def _short_title(text: str, *, fallback: str) -> str:
    first_line = text.split("\n", 1)[0].strip()
    first_sentence = re.split(r"[。！？.!?]", first_line, maxsplit=1)[0].strip()
    return _truncate_text(first_sentence, 24) or fallback


def _truncate_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(clean_text(text).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
