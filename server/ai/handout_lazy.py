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

from server.ai.deepseek import DeepSeekJsonChatClient, get_configured_deepseek_chat_config
from server.parsers.base import clean_text


GenerationStatus = Literal["pending", "generating", "ready", "failed"]
_DEFAULT_OUTLINE_MODEL = "Doubao-Seed-2.0-mini"
_DEFAULT_HANDOUT_TIMEOUT_SEC = 75.0
_OUTLINE_SYSTEM_PROMPT = """你是 KnowLink 的视频讲义目录生成器。只返回 JSON，不要返回 Markdown 或解释。
JSON 格式固定为：
{"title":"...","summary":"...","items":[{"outlineKey":"section-1","title":"...","summary":"...","startSec":0,"endSec":120,"sortNo":1,"children":[{"outlineKey":"outline-1","title":"...","summary":"...","startSec":0,"endSec":60,"sortNo":1,"generationStatus":"pending","sourceSegmentKeys":["mp4-c1"],"topicTags":["..."]}]}]}
规则：
1. 目录只基于输入 video_caption segments 生成，不能虚构视频外内容。
2. items[] 是大标题 section，只负责语义分组和展开；section 不得包含 blockId、generationStatus、sourceSegmentKeys 或 topicTags。
3. items[].children[] 是可点击的小标题 leaf，只有 child 能绑定 sourceSegmentKeys、generationStatus 和后续讲义块。
4. 大标题必须按概念关联组织，例如“集合的概念与表示”下包含“集合的定义”“集合符号与枚举法”；不要机械按每 3 组聚合。
5. 每个 child 的 sourceSegmentKeys 必须全部来自输入 segmentKey，不能为空，不得虚构或改写。
6. child 的 startSec/endSec 必须等于 sourceSegmentKeys 对应字幕的最小 startSec 和最大 endSec；child 按时间线严格递增且不得重叠。
7. parent 的 startSec/endSec 必须等于 children 的最小 startSec 和最大 endSec；同一 parent 下 children 必须在视频时间线上连续归属，不能与其他 parent 穿插。
8. child 的 generationStatus 固定返回 pending；完整讲义和知识点后续按 child block 懒生成。
9. title 必须是 4-12 字的概念型短标题，例如“集合论基础”“文氏图表示”；不要直接复制 ASR 长句，不要以省略号结尾。
10. summary 必须是 1 句学习重点，不要截断字幕原文，不要写成时间轴说明。
11. 可用补充资料上下文纠正 ASR 噪声，例如把 zero/ZF、文试图/文氏图一类误识别改成课程资料中的正确概念。
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
    provider = os.getenv("KNOWLINK_HANDOUT_OUTLINE_PROVIDER", "vivo").strip().lower()
    if provider == "deepseek":
        config = get_configured_deepseek_chat_config()
        if config is None:
            return None
        return DeepSeekHandoutOutlineClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            timeout_sec=_env_float("KNOWLINK_VIVO_HANDOUT_TIMEOUT_SEC", _DEFAULT_HANDOUT_TIMEOUT_SEC),
        )
    if provider not in {"", "vivo"}:
        return None

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
        outline = _outline_with_pending_child_statuses(outline)
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

    issues = [
        *outline_structure_issues(outline.get("items", [])),
        *outline_timeline_issues(outline.get("items", [])),
        *outline_source_issues(outline.get("items", []), caption_segments),
    ]
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

        overlaps_current_group = caption["startSec"] < max(int(item["endSec"]) for item in current_group)
        if caption["endSec"] - int(current_start) > max_block_duration_sec and not overlaps_current_group:
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
        "items": _fallback_sections_from_leaf_items(
            _normalize_outline_item_boundaries(
                [_outline_item_from_group(group, index) for index, group in enumerate(groups, start=1)]
            )
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


class DeepSeekHandoutOutlineClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str,
        timeout_sec: float | None = None,
    ) -> None:
        self._client = DeepSeekJsonChatClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_sec=timeout_sec if timeout_sec is not None else _DEFAULT_HANDOUT_TIMEOUT_SEC,
            label="deepseek outline",
        )

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
            raise RuntimeError("deepseek outline requires at least one valid video_caption segment")

        model_payload = self._client.complete_json(
            system_prompt=_OUTLINE_SYSTEM_PROMPT,
            user_prompt=_build_outline_prompt(
                captions,
                title=title,
                summary=summary,
                document_context=document_context,
            ),
            max_tokens=8192,
        )
        return _normalize_model_outline(model_payload, captions=captions, title=title, summary=summary)


def outline_structure_issues(items: Any) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["outline.items_missing"]

    issues: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            issues.append("outline.section_invalid")
            continue
        if any(key in item for key in ("blockId", "generationStatus", "sourceSegmentKeys", "topicTags")):
            issues.append("outline.parent_leaf_fields_present")
        children = item.get("children")
        if not isinstance(children, list) or not children:
            issues.append("outline.children_missing")
            continue
        for child in children:
            if not isinstance(child, Mapping):
                issues.append("outline.children_invalid")
                continue
            if "children" in child:
                issues.append("outline.child_nested")
    return issues


def outline_timeline_issues(items: Sequence[Mapping[str, Any]]) -> list[str]:
    issues: list[str] = []
    seen_keys: set[str] = set()
    previous_parent_sort_no = 0
    previous_parent_end: int | None = None
    previous_leaf_sort_no = 0
    previous_leaf_end: int | None = None

    for item in items:
        children = item.get("children")
        if not isinstance(children, list):
            child_issues, previous_leaf_sort_no, previous_leaf_end = _append_leaf_timeline_issues(
                item,
                seen_keys=seen_keys,
                previous_sort_no=previous_leaf_sort_no,
                previous_end=previous_leaf_end,
            )
            issues.extend(child_issues)
            continue

        parent_key_issues = _append_outline_key_issues(item, seen_keys=seen_keys)
        issues.extend(parent_key_issues)

        parent_sort_no = _as_int(item.get("sortNo"))
        if parent_sort_no is None or parent_sort_no <= previous_parent_sort_no:
            issues.append("outline.sort_not_increasing")
        else:
            previous_parent_sort_no = parent_sort_no

        parent_start = _as_int(item.get("startSec"))
        parent_end = _as_int(item.get("endSec"))
        if parent_start is None or parent_end is None or parent_end <= parent_start:
            issues.append("outline.time_invalid")

        valid_child_ranges: list[tuple[int, int]] = []
        if not children:
            issues.append("outline.children_missing")
        for child in children:
            if not isinstance(child, Mapping):
                issues.append("outline.children_invalid")
                continue
            child_issues, previous_leaf_sort_no, previous_leaf_end = _append_leaf_timeline_issues(
                child,
                seen_keys=seen_keys,
                previous_sort_no=previous_leaf_sort_no,
                previous_end=previous_leaf_end,
            )
            issues.extend(child_issues)
            child_start = _as_int(child.get("startSec"))
            child_end = _as_int(child.get("endSec"))
            if child_start is not None and child_end is not None and child_end > child_start:
                valid_child_ranges.append((child_start, child_end))

        if parent_start is None or parent_end is None or not valid_child_ranges:
            continue
        child_min_start = min(start for start, _ in valid_child_ranges)
        child_max_end = max(end for _, end in valid_child_ranges)
        if parent_start != child_min_start or parent_end != child_max_end:
            issues.append("outline.parent_time_mismatch")
        if previous_parent_end is not None and parent_start < previous_parent_end:
            issues.append("outline.time_overlap")
        previous_parent_end = parent_end if previous_parent_end is None else max(previous_parent_end, parent_end)

    return issues


def outline_source_issues(
    items: Sequence[Mapping[str, Any]],
    caption_segments: Sequence[Mapping[str, Any]],
) -> list[str]:
    captions = _valid_video_captions(caption_segments)
    captions_by_key = {str(item["segmentKey"]): item for item in captions}
    issues: list[str] = []

    for item in outline_leaf_items(items):
        raw_keys = item.get("sourceSegmentKeys")
        if not isinstance(raw_keys, list) or not raw_keys:
            issues.append("outline.source_segments_missing")
            continue

        source_keys = [str(key) for key in raw_keys]
        source_captions = [captions_by_key[key] for key in source_keys if key in captions_by_key]
        if len(source_captions) != len(source_keys):
            issues.append("outline.source_segment_unknown")
            continue

        start_sec = _as_int(item.get("startSec"))
        end_sec = _as_int(item.get("endSec"))
        if start_sec is None or end_sec is None:
            continue
        if start_sec != min(int(source["startSec"]) for source in source_captions):
            issues.append("outline.source_time_mismatch")
            continue
        if end_sec != max(int(source["endSec"]) for source in source_captions):
            issues.append("outline.source_time_mismatch")

    return issues


def current_outline_item(
    items: Sequence[Mapping[str, Any]],
    *,
    current_sec: int,
) -> Mapping[str, Any] | None:
    ordered = _ordered_outline_items(outline_leaf_items(items))
    return _current_ordered_outline_item(ordered, current_sec=current_sec)


def _current_ordered_outline_item(
    ordered: Sequence[Mapping[str, Any]],
    *,
    current_sec: int,
) -> Mapping[str, Any] | None:
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
    ordered = _ordered_outline_items(outline_leaf_items(items))
    active = _current_ordered_outline_item(ordered, current_sec=current_sec)
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
            f"补充资料上下文（用于纠正 ASR 同音词和识别噪声，不可生成超出字幕时间线的新段落）：{context or '无'}",
            "请基于以下 video_caption segments 的预分组生成两级目录。groups 只是候选字幕片段；"
            "你需要根据语义关联决定哪些连续 groups 归入同一个大标题 section，不要机械每 3 组一类。",
            "每个 child 可以合并相邻 group，但 sourceSegmentKeys 必须完整来自输入；不得拆分单个字幕 segment。",
            "parent 只负责分组，不能带 blockId/generationStatus/sourceSegmentKeys；"
            "child 才是可点击、可生成讲义块的小标题。",
            "每个 title 用概念短语，不要复制字幕长句；summary 只写 1 句学习重点；"
            "child startSec/endSec 必须等于 sourceSegmentKeys 的最小 startSec 和最大 endSec，"
            "parent startSec/endSec 必须等于 children 的最小 startSec 和最大 endSec。",
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
            "startSec": min(int(item["startSec"]) for item in group),
            "endSec": max(int(item["endSec"]) for item in group),
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

    normalized_sections: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for raw_section in items_payload:
        if not isinstance(raw_section, dict):
            continue

        children_payload = raw_section.get("children")
        if not isinstance(children_payload, list) or not children_payload:
            raise RuntimeError("vivo outline section missing non-empty children")

        children: list[dict[str, Any]] = []
        for raw_child in children_payload:
            if not isinstance(raw_child, dict):
                continue
            source_keys = _required_source_segment_keys(raw_child.get("sourceSegmentKeys"), caption_by_key)
            source_captions = [caption_by_key[key] for key in source_keys]
            source_start = min(int(item["startSec"]) for item in source_captions)
            source_end = max(int(item["endSec"]) for item in source_captions)
            child_start = _as_int(raw_child.get("startSec"))
            child_end = _as_int(raw_child.get("endSec"))
            if child_start != source_start or child_end != source_end:
                raise RuntimeError("vivo outline child time does not match sourceSegmentKeys")

            outline_key = _stable_outline_key(
                str(raw_child.get("outlineKey") or ""),
                len(seen_keys) + 1,
                seen_keys,
            )
            seen_keys.add(outline_key)
            source_text = "\n".join(str(item["textContent"]) for item in source_captions)
            children.append(
                {
                    "outlineKey": outline_key,
                    "title": clean_text(str(raw_child.get("title") or "")) or _short_title(
                        source_text,
                        fallback=f"第 {len(children) + 1} 段",
                    ),
                    "summary": clean_text(str(raw_child.get("summary") or "")) or _truncate_text(source_text, 72),
                    "startSec": source_start,
                    "endSec": source_end,
                    "sortNo": 1,
                    "generationStatus": "pending",
                    "sourceSegmentKeys": source_keys,
                    "topicTags": _clean_topic_tags(raw_child.get("topicTags")),
                }
            )

        if not children:
            raise RuntimeError("vivo outline section produced no valid children")
        children = sorted(children, key=lambda item: (item["startSec"], item["endSec"], item["outlineKey"]))
        section_start = min(int(item["startSec"]) for item in children)
        section_end = max(int(item["endSec"]) for item in children)
        raw_section_start = _as_int(raw_section.get("startSec"))
        raw_section_end = _as_int(raw_section.get("endSec"))
        if raw_section_start != section_start or raw_section_end != section_end:
            raise RuntimeError("vivo outline parent time does not match children")

        section_key = _stable_outline_key(
            str(raw_section.get("outlineKey") or ""),
            len(seen_keys) + 1,
            seen_keys,
        )
        seen_keys.add(section_key)
        child_text = "\n".join(str(child["title"]) for child in children)
        normalized_sections.append(
            {
                "outlineKey": section_key,
                "title": clean_text(str(raw_section.get("title") or "")) or _short_title(
                    child_text,
                    fallback=f"第 {len(normalized_sections) + 1} 部分",
                ),
                "summary": clean_text(str(raw_section.get("summary") or "")) or _truncate_text(child_text, 72),
                "startSec": section_start,
                "endSec": section_end,
                "sortNo": 1,
                "children": children,
            }
        )

    if not normalized_sections:
        raise RuntimeError("vivo outline JSON produced no valid items")

    normalized_sections = sorted(
        normalized_sections,
        key=lambda item: (item["startSec"], item["endSec"], item["outlineKey"]),
    )
    leaf_sort_no = 1
    for section_index, section in enumerate(normalized_sections, start=1):
        section["sortNo"] = section_index
        for child in section["children"]:
            child["sortNo"] = leaf_sort_no
            leaf_sort_no += 1

    issues = outline_timeline_issues(normalized_sections)
    if issues:
        raise RuntimeError(f"vivo outline timeline invalid: {issues}")

    return {
        "title": clean_text(str(payload.get("title") or "")) or title,
        "summary": clean_text(str(payload.get("summary") or "")) or summary,
        "items": normalized_sections,
    }


def _required_source_segment_keys(value: Any, caption_by_key: Mapping[str, Mapping[str, Any]]) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuntimeError("vivo outline child missing sourceSegmentKeys")
    keys: list[str] = []
    seen: set[str] = set()
    for item in value:
        key = str(item or "")
        if key not in caption_by_key:
            raise RuntimeError("vivo outline child references unknown sourceSegmentKeys")
        if key not in seen:
            keys.append(key)
            seen.add(key)
    if not keys:
        raise RuntimeError("vivo outline child missing sourceSegmentKeys")
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
    for item in items:
        clean_item = dict(item)
        start_sec = int(clean_item["startSec"])
        end_sec = int(clean_item["endSec"])
        if end_sec <= start_sec:
            continue
        normalized.append(clean_item)
    return normalized


def _fallback_sections_from_leaf_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        child = dict(item)
        child["sortNo"] = index
        sections.append(
            {
                "outlineKey": f"section-{index}",
                "title": child["title"],
                "summary": child["summary"],
                "startSec": child["startSec"],
                "endSec": child["endSec"],
                "sortNo": index,
                "children": [child],
            }
        )
    return sections


def _outline_item_from_group(group: list[dict[str, Any]], index: int) -> dict[str, Any]:
    text = clean_text("\n".join(item["textContent"] for item in group))
    title = _short_title(text, fallback=f"第 {index} 段")
    return {
        "outlineKey": f"outline-{index}",
        "title": title,
        "summary": _truncate_text(text, 72),
        "startSec": min(int(item["startSec"]) for item in group),
        "endSec": max(int(item["endSec"]) for item in group),
        "sortNo": index,
        "generationStatus": "pending",
        "sourceSegmentKeys": [item["segmentKey"] for item in group],
        "topicTags": [],
    }


def _outline_with_pending_child_statuses(outline: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(outline)
    items: list[Any] = []
    for raw_item in outline.get("items", []):
        if not isinstance(raw_item, dict):
            items.append(raw_item)
            continue
        item = dict(raw_item)
        children = item.get("children")
        if isinstance(children, list):
            item["children"] = [
                {**child, "generationStatus": "pending"} if isinstance(child, dict) else child
                for child in children
            ]
        items.append(item)
    normalized["items"] = items
    return normalized


def outline_leaf_items(items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    leaves: list[Mapping[str, Any]] = []
    for item in items:
        children = item.get("children")
        if isinstance(children, list):
            leaves.extend(child for child in children if isinstance(child, Mapping))
    return leaves


def _append_outline_key_issues(item: Mapping[str, Any], *, seen_keys: set[str]) -> list[str]:
    outline_key = str(item.get("outlineKey") or "")
    if not outline_key:
        return ["outline.key_missing"]
    if outline_key in seen_keys:
        return ["outline.key_duplicate"]
    seen_keys.add(outline_key)
    return []


def _append_leaf_timeline_issues(
    item: Mapping[str, Any],
    *,
    seen_keys: set[str],
    previous_sort_no: int,
    previous_end: int | None,
) -> tuple[list[str], int, int | None]:
    issues = _append_outline_key_issues(item, seen_keys=seen_keys)

    sort_no = _as_int(item.get("sortNo"))
    if sort_no is None or sort_no <= previous_sort_no:
        issues.append("outline.sort_not_increasing")
    else:
        previous_sort_no = sort_no

    start_sec = _as_int(item.get("startSec"))
    end_sec = _as_int(item.get("endSec"))
    if start_sec is None or end_sec is None or end_sec <= start_sec:
        issues.append("outline.time_invalid")
        return issues, previous_sort_no, previous_end

    if previous_end is not None and start_sec < previous_end:
        issues.append("outline.time_overlap")
    previous_end = end_sec if previous_end is None else max(previous_end, end_sec)
    return issues, previous_sort_no, previous_end


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
