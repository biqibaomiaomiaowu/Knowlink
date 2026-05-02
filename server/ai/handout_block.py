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


DifficultyLevel = Literal["beginner", "intermediate", "advanced"]
_DEFAULT_HANDOUT_BLOCK_MODEL = "Doubao-Seed-2.0-pro"
_DEFAULT_HANDOUT_BLOCK_TIMEOUT_SEC = 120.0
_INVALID_VIDEO_SEED = object()
_HANDOUT_BLOCK_SYSTEM_PROMPT = """你是 KnowLink 的单段视频讲义生成器。只返回 JSON，不要返回 Markdown 代码块或解释。
JSON 格式固定为：
{"outlineKey":"...","title":"...","summary":"...","contentMd":"...","estimatedMinutes":3,"sourceSegmentKeys":["mp4-c1"],"knowledgePoints":[{"knowledgePointKey":"kp-outline-1-1","displayName":"...","description":"...","difficultyLevel":"beginner","importanceScore":80,"sortNo":1}],"citations":[{"resourceId":1,"segmentKey":"mp4-c1","startSec":0,"endSec":30,"refLabel":"视频 00:00-00:30"}]}
规则：
1. 只能基于输入 segments 生成讲义，不得虚构引用。
2. sourceSegmentKeys 只能来自当前 outline item 的 video_caption segments。
3. citations 必须引用输入中的 segmentKey；视频 citation 必须落在 outline item 时间范围内。
4. 每个 citation 只能使用一种定位：pageNo、slideNo、anchorKey、或 startSec/endSec。
5. contentMd 使用中文 Markdown，先解释本段核心概念，再给出简短例子或学习提醒。
"""


@dataclass(frozen=True)
class HandoutBlockContext:
    source_segments: list[dict[str, Any]]
    supplemental_segments: list[dict[str, Any]]

    @property
    def all_segments(self) -> list[dict[str, Any]]:
        return [*self.source_segments, *self.supplemental_segments]


class HandoutBlockClient(Protocol):
    def generate_block(
        self,
        outline_item: Mapping[str, Any],
        context_segments: Sequence[Mapping[str, Any]],
        *,
        preferences: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a raw model payload for one ready handout block."""


def get_configured_handout_block_client() -> HandoutBlockClient | None:
    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    return VivoHandoutBlockClient(
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        model=os.getenv("KNOWLINK_VIVO_HANDOUT_BLOCK_MODEL", _DEFAULT_HANDOUT_BLOCK_MODEL),
        timeout_sec=_env_float("KNOWLINK_VIVO_HANDOUT_BLOCK_TIMEOUT_SEC", _DEFAULT_HANDOUT_BLOCK_TIMEOUT_SEC),
    )


def generate_handout_block(
    outline_item: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
    preferences: Mapping[str, Any] | None = None,
    client: HandoutBlockClient | None = None,
) -> dict[str, Any]:
    context = build_handout_block_context(outline_item, segments)
    configured_client = client if client is not None else get_configured_handout_block_client()

    if configured_client is not None:
        try:
            payload = configured_client.generate_block(
                outline_item,
                context.all_segments,
                preferences=preferences,
            )
            return normalize_handout_block_payload(
                payload,
                outline_item=outline_item,
                segments=context.all_segments,
                preferences=preferences,
            )
        except Exception:
            pass

    return fallback_handout_block(
        outline_item,
        context=context,
        preferences=preferences,
    )


def build_handout_block_context(
    outline_item: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
    *,
    max_supplemental_segments: int = 6,
) -> HandoutBlockContext:
    known_segments = [_normalize_segment(segment, index) for index, segment in enumerate(segments, start=1)]
    known_by_key = {segment["segmentKey"]: segment for segment in known_segments}

    outline_start = _as_int(outline_item.get("startSec"))
    outline_end = _as_int(outline_item.get("endSec"))
    source_keys = [
        str(item)
        for item in outline_item.get("sourceSegmentKeys", [])
        if str(item) in known_by_key and known_by_key[str(item)].get("segmentType") == "video_caption"
    ]
    source_segments = [
        known_by_key[key]
        for key in source_keys
        if _video_segment_is_in_outline(known_by_key[key], outline_start=outline_start, outline_end=outline_end)
    ]

    if not source_segments and outline_start is not None and outline_end is not None:
        source_segments = [
            segment
            for segment in known_segments
            if segment.get("segmentType") == "video_caption"
            and _video_segment_overlaps(segment, outline_start=outline_start, outline_end=outline_end)
        ]

    if not source_segments:
        raise ValueError("at least one known video_caption segment is required for handout block generation")

    source_text = "\n".join(str(segment["textContent"]) for segment in source_segments)
    query_text = " ".join(
        clean_text(
            " ".join(
                [
                    str(outline_item.get("title") or ""),
                    str(outline_item.get("summary") or ""),
                    source_text,
                ]
            )
        ).split()
    )
    supplemental = _rank_supplemental_segments(
        [segment for segment in known_segments if segment.get("segmentType") != "video_caption"],
        query_text=query_text,
    )[:max_supplemental_segments]

    return HandoutBlockContext(source_segments=source_segments, supplemental_segments=supplemental)


class VivoHandoutBlockClient:
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
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_HANDOUT_BLOCK_TIMEOUT_SEC
        self._last_request_at = 0.0
        self._min_request_interval_sec = 0.8

    def generate_block(
        self,
        outline_item: Mapping[str, Any],
        context_segments: Sequence[Mapping[str, Any]],
        *,
        preferences: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not context_segments:
            raise RuntimeError("vivo handout block requires context segments")

        self._throttle()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _HANDOUT_BLOCK_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_handout_block_prompt(
                        outline_item,
                        context_segments,
                        preferences=preferences,
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
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
            raise RuntimeError(f"vivo handout block request failed: {exc}") from exc

        return _parse_chat_json_payload(chat_payload, label="vivo handout block")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_request_interval_sec:
            time.sleep(self._min_request_interval_sec - elapsed)
        self._last_request_at = time.monotonic()


def normalize_handout_block_payload(
    payload: Mapping[str, Any],
    *,
    outline_item: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
    preferences: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_segments = [_normalize_segment(segment, index) for index, segment in enumerate(segments, start=1)]
    context = build_handout_block_context(outline_item, normalized_segments)
    source_key_set = {segment["segmentKey"] for segment in context.source_segments}

    title = clean_text(str(_first_present(payload, "title") or outline_item.get("title") or "")) or "讲义片段"
    summary = clean_text(str(_first_present(payload, "summary") or outline_item.get("summary") or "")) or _truncate(
        "\n".join(segment["textContent"] for segment in context.source_segments),
        90,
    )
    content_md = _clean_markdown(str(_first_present(payload, "contentMd", "content_md") or ""))
    if not content_md:
        content_md = _fallback_content_md(title=title, summary=summary, context=context)

    knowledge_points = _normalize_knowledge_points(
        _first_present(payload, "knowledgePoints", "knowledge_points"),
        outline_key=str(outline_item.get("outlineKey") or "outline"),
        fallback_title=title,
        fallback_summary=summary,
        preferences=preferences,
    )
    source_segment_keys = _valid_source_keys(
        _first_present(payload, "sourceSegmentKeys", "source_segment_keys"),
        source_key_set=source_key_set,
    )
    if not source_segment_keys:
        source_segment_keys = [segment["segmentKey"] for segment in context.source_segments]

    citations = _normalize_citations(
        _first_present(payload, "citations") or [],
        outline_item=outline_item,
        segments=normalized_segments,
        source_segment_keys=[segment["segmentKey"] for segment in context.source_segments],
    )
    if not citations:
        citations = _fallback_citations(outline_item=outline_item, context=context)
    citations = _ensure_source_video_citation(
        citations,
        outline_item=outline_item,
        source_segments=context.source_segments,
        source_segment_keys=source_segment_keys,
    )

    return {
        "outlineKey": _stable_key(str(outline_item.get("outlineKey") or _first_present(payload, "outlineKey") or "")),
        "title": title,
        "summary": summary,
        "contentMd": content_md,
        "estimatedMinutes": _estimated_minutes(_first_present(payload, "estimatedMinutes", "estimated_minutes"), content_md),
        "sourceSegmentKeys": source_segment_keys,
        "knowledgePoints": knowledge_points,
        "citations": citations,
    }


def fallback_handout_block(
    outline_item: Mapping[str, Any],
    *,
    context: HandoutBlockContext,
    preferences: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    title = clean_text(str(outline_item.get("title") or "")) or "讲义片段"
    summary = clean_text(str(outline_item.get("summary") or "")) or _truncate(
        "\n".join(segment["textContent"] for segment in context.source_segments),
        90,
    )
    content_md = _fallback_content_md(title=title, summary=summary, context=context)
    knowledge_points = _fallback_knowledge_points(
        outline_key=str(outline_item.get("outlineKey") or "outline"),
        title=title,
        summary=summary,
        preferences=preferences,
    )
    return {
        "outlineKey": _stable_key(str(outline_item.get("outlineKey") or "outline")),
        "title": title,
        "summary": summary,
        "contentMd": content_md,
        "estimatedMinutes": _estimated_minutes(None, content_md),
        "sourceSegmentKeys": [segment["segmentKey"] for segment in context.source_segments],
        "knowledgePoints": knowledge_points,
        "citations": _fallback_citations(outline_item=outline_item, context=context),
    }


def citation_segment_keys(block: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for citation in block.get("citations", []):
        if not isinstance(citation, Mapping):
            continue
        key = citation.get("segmentKey")
        if isinstance(key, str) and key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _normalize_segment(segment: Mapping[str, Any], index: int) -> dict[str, Any]:
    segment_key = str(segment.get("segmentKey") or segment.get("segment_key") or f"segment-{index}")
    clean_segment = dict(segment)
    clean_segment["segmentKey"] = _stable_key(segment_key, fallback=f"segment-{index}")
    clean_segment["segmentType"] = str(segment.get("segmentType") or segment.get("segment_type") or "")
    clean_segment["orderNo"] = _as_int(segment.get("orderNo") or segment.get("order_no")) or index
    clean_segment["textContent"] = clean_text(str(segment.get("textContent") or segment.get("text_content") or ""))

    for camel, snake in (
        ("resourceId", "resource_id"),
        ("segmentId", "segment_id"),
        ("pageNo", "page_no"),
        ("slideNo", "slide_no"),
        ("startSec", "start_sec"),
        ("endSec", "end_sec"),
    ):
        value = _as_int(segment.get(camel) if camel in segment else segment.get(snake))
        if value is not None:
            clean_segment[camel] = value

    anchor_key = segment.get("anchorKey") or segment.get("anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        clean_segment["anchorKey"] = clean_text(anchor_key)
    return clean_segment


def _rank_supplemental_segments(segments: Sequence[Mapping[str, Any]], *, query_text: str) -> list[dict[str, Any]]:
    keywords = _keywords(query_text)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, segment in enumerate(segments):
        text = str(segment.get("textContent") or "")
        if not text:
            continue
        compact = text.lower()
        score = sum(1 for keyword in keywords if keyword in compact)
        if score == 0:
            score = 1
        scored.append((-score, int(segment.get("orderNo") or index + 1), dict(segment)))
    return [item[2] for item in sorted(scored, key=lambda item: (item[0], item[1], item[2]["segmentKey"]))]


def _keywords(text: str) -> set[str]:
    tokens = set(re.findall(r"[A-Za-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", text.lower()))
    return {token for token in tokens if len(token) >= 2}


def _fallback_content_md(*, title: str, summary: str, context: HandoutBlockContext) -> str:
    source_text = _truncate(" ".join(segment["textContent"] for segment in context.source_segments), 360)
    lines = [
        f"## {title}",
        "",
        summary,
        "",
        "### 本段核心",
        f"- {source_text}",
    ]
    if context.supplemental_segments:
        lines.extend(["", "### 资料补充"])
        for segment in context.supplemental_segments[:3]:
            lines.append(f"- {segment_label(segment)}：{_truncate(str(segment['textContent']), 160)}")
    return "\n".join(lines)


def _normalize_knowledge_points(
    payload: Any,
    *,
    outline_key: str,
    fallback_title: str,
    fallback_summary: str,
    preferences: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    items = payload if isinstance(payload, list) else []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            continue
        display_name = clean_text(str(_first_present(raw_item, "displayName", "display_name") or ""))
        description = clean_text(str(_first_present(raw_item, "description") or ""))
        if not display_name or not description:
            continue
        key = _stable_key(
            str(_first_present(raw_item, "knowledgePointKey", "knowledge_point_key") or display_name),
            fallback=f"kp-{outline_key}-{len(normalized) + 1}",
        )
        if key in seen:
            key = _stable_key(f"{key}-{len(normalized) + 1}")
        seen.add(key)
        normalized.append(
            {
                "knowledgePointKey": key,
                "displayName": display_name,
                "description": description,
                "difficultyLevel": _difficulty_level(
                    _first_present(raw_item, "difficultyLevel", "difficulty_level"),
                    preferences=preferences,
                ),
                "importanceScore": _score_0_to_100(_first_present(raw_item, "importanceScore", "importance_score"), 80),
                "sortNo": len(normalized) + 1,
            }
        )

    if normalized:
        return normalized
    return _fallback_knowledge_points(
        outline_key=outline_key,
        title=fallback_title,
        summary=fallback_summary,
        preferences=preferences,
    )


def _fallback_knowledge_points(
    *,
    outline_key: str,
    title: str,
    summary: str,
    preferences: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    key = _stable_key(f"kp-{outline_key}-1")
    return [
        {
            "knowledgePointKey": key,
            "displayName": _truncate(title, 36),
            "description": summary,
            "difficultyLevel": _difficulty_level(None, preferences=preferences),
            "importanceScore": 80,
            "sortNo": 1,
        }
    ]


def _normalize_citations(
    payload: Any,
    *,
    outline_item: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
    source_segment_keys: Sequence[str],
) -> list[dict[str, Any]]:
    raw_citations = payload if isinstance(payload, list) else []
    normalized_segments = [_normalize_segment(segment, index) for index, segment in enumerate(segments, start=1)]
    by_key = {segment["segmentKey"]: segment for segment in normalized_segments}
    by_id = {
        int(segment["segmentId"]): segment
        for segment in normalized_segments
        if _as_int(segment.get("segmentId")) is not None
    }
    outline_start = _as_int(outline_item.get("startSec"))
    outline_end = _as_int(outline_item.get("endSec"))

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[tuple[str, Any], ...]]] = set()
    for raw_item in raw_citations:
        if not isinstance(raw_item, Mapping):
            continue
        expanded_citations = _expand_video_time_range_citations(
            raw_item,
            by_key=by_key,
            by_id=by_id,
            segments=normalized_segments,
            source_segment_keys=source_segment_keys,
            outline_start=outline_start,
            outline_end=outline_end,
        )
        if expanded_citations is not None:
            for citation in expanded_citations:
                _append_unique_citation(normalized, citation, seen=seen)
            continue

        segment = _citation_segment(raw_item, by_key=by_key, by_id=by_id, segments=normalized_segments)
        if segment is None:
            continue

        citation = _citation_from_segment(
            segment,
            raw_item=raw_item,
            outline_start=outline_start,
            outline_end=outline_end,
        )
        if citation is None:
            continue
        _append_unique_citation(normalized, citation, seen=seen)

    return normalized


def _append_unique_citation(
    citations: list[dict[str, Any]],
    citation: dict[str, Any],
    *,
    seen: set[tuple[str, tuple[tuple[str, Any], ...]]],
) -> None:
    identity = _citation_identity(citation)
    if identity in seen:
        return
    seen.add(identity)
    citations.append(citation)


def _citation_identity(citation: Mapping[str, Any]) -> tuple[str, tuple[tuple[str, Any], ...]]:
    return (
        str(citation["segmentKey"]),
        tuple((key, citation[key]) for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec") if key in citation),
    )


def _expand_video_time_range_citations(
    raw_item: Mapping[str, Any],
    *,
    by_key: Mapping[str, Mapping[str, Any]],
    by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    source_segment_keys: Sequence[str],
    outline_start: int | None,
    outline_end: int | None,
) -> list[dict[str, Any]] | None:
    raw_locator = _raw_locator(raw_item)
    if "timeRange" not in raw_locator:
        return None
    if len(raw_locator) != 1:
        return []

    raw_start, raw_end = raw_locator["timeRange"]
    if raw_end <= raw_start:
        return []

    source_key_set = set(source_segment_keys)
    seed_segment = _seed_video_segment(raw_item, by_key=by_key, by_id=by_id)
    if seed_segment is _INVALID_VIDEO_SEED:
        return []
    if seed_segment is not None and source_key_set and seed_segment["segmentKey"] not in source_key_set:
        return []

    raw_resource_id = _as_positive_int(raw_item.get("resourceId") or raw_item.get("resource_id"))
    seed_resource_id = _as_positive_int(seed_segment.get("resourceId")) if isinstance(seed_segment, Mapping) else None
    if raw_resource_id is not None and seed_resource_id is not None and raw_resource_id != seed_resource_id:
        return []

    resource_id = raw_resource_id or seed_resource_id
    if resource_id is None:
        return []

    citations: list[dict[str, Any]] = []
    for segment in segments:
        if segment.get("segmentType") != "video_caption":
            continue
        if source_key_set and segment["segmentKey"] not in source_key_set:
            continue
        if _as_positive_int(segment.get("resourceId")) != resource_id:
            continue

        segment_start = _as_int(segment.get("startSec"))
        segment_end = _as_int(segment.get("endSec"))
        if segment_start is None or segment_end is None or segment_end <= segment_start:
            continue

        start_sec = max(value for value in (raw_start, segment_start, outline_start) if value is not None)
        end_sec = min(value for value in (raw_end, segment_end, outline_end) if value is not None)
        if end_sec <= start_sec:
            continue

        citation = _citation_from_segment(
            segment,
            raw_item={**raw_item, "startSec": start_sec, "endSec": end_sec},
            outline_start=outline_start,
            outline_end=outline_end,
        )
        if citation is not None:
            citations.append(citation)

    return citations


def _seed_video_segment(
    raw_item: Mapping[str, Any],
    *,
    by_key: Mapping[str, Mapping[str, Any]],
    by_id: Mapping[int, Mapping[str, Any]],
) -> Mapping[str, Any] | None | object:
    key = raw_item.get("segmentKey") or raw_item.get("segment_key")
    if isinstance(key, str) and key.strip():
        segment = by_key.get(_stable_key(key))
        if segment is None or segment.get("segmentType") != "video_caption":
            return _INVALID_VIDEO_SEED
        return segment

    segment_id = _as_int(raw_item.get("segmentId") or raw_item.get("segment_id"))
    if segment_id is not None:
        segment = by_id.get(segment_id)
        if segment is None or segment.get("segmentType") != "video_caption":
            return _INVALID_VIDEO_SEED
        return segment

    return None


def _ensure_source_video_citation(
    citations: list[dict[str, Any]],
    *,
    outline_item: Mapping[str, Any],
    source_segments: Sequence[Mapping[str, Any]],
    source_segment_keys: Sequence[str],
) -> list[dict[str, Any]]:
    source_key_set = set(source_segment_keys)
    source_video_segments = [
        segment
        for segment in source_segments
        if segment.get("segmentType") == "video_caption" and segment.get("segmentKey") in source_key_set
    ]
    if not source_video_segments:
        return citations

    source_video_key_set = {segment["segmentKey"] for segment in source_video_segments}
    if any(citation.get("segmentKey") in source_video_key_set for citation in citations):
        return citations

    citation = _citation_from_segment(
        source_video_segments[0],
        raw_item={},
        outline_start=_as_int(outline_item.get("startSec")),
        outline_end=_as_int(outline_item.get("endSec")),
    )
    if citation is None:
        return citations
    return [citation, *citations]


def _fallback_citations(*, outline_item: Mapping[str, Any], context: HandoutBlockContext) -> list[dict[str, Any]]:
    outline_start = _as_int(outline_item.get("startSec"))
    outline_end = _as_int(outline_item.get("endSec"))
    citations: list[dict[str, Any]] = []
    for segment in [*context.source_segments[:2], *context.supplemental_segments[:3]]:
        citation = _citation_from_segment(
            segment,
            raw_item={},
            outline_start=outline_start,
            outline_end=outline_end,
        )
        if citation is not None:
            citations.append(citation)
    if not citations:
        raise ValueError("handout block needs at least one segment with resourceId and locator for citation")
    return citations


def _citation_segment(
    raw_item: Mapping[str, Any],
    *,
    by_key: Mapping[str, Mapping[str, Any]],
    by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    key = raw_item.get("segmentKey") or raw_item.get("segment_key")
    if isinstance(key, str) and key.strip():
        return by_key.get(_stable_key(key))

    segment_id = _as_int(raw_item.get("segmentId") or raw_item.get("segment_id"))
    if segment_id is not None:
        return by_id.get(segment_id)

    resource_id = _as_int(raw_item.get("resourceId") or raw_item.get("resource_id"))
    if resource_id is None:
        return None

    raw_locator = _raw_locator(raw_item)
    if len(raw_locator) != 1:
        return None
    locator_key, locator_value = next(iter(raw_locator.items()))
    for segment in segments:
        segment_locator = _segment_locator(segment)
        if locator_key == "timeRange":
            matches_locator = (
                segment_locator.get("startSec") == locator_value[0]
                and segment_locator.get("endSec") == locator_value[1]
            )
        else:
            matches_locator = segment_locator.get(locator_key) == locator_value
        if _as_int(segment.get("resourceId")) == resource_id and matches_locator:
            return segment
    return None


def _citation_from_segment(
    segment: Mapping[str, Any],
    *,
    raw_item: Mapping[str, Any],
    outline_start: int | None,
    outline_end: int | None,
) -> dict[str, Any] | None:
    segment_locator = _segment_locator(segment)
    if not segment_locator:
        return None

    raw_locator = _raw_locator(raw_item)
    if len(raw_locator) > 1:
        return None
    if raw_locator:
        raw_key, raw_value = next(iter(raw_locator.items()))
        if raw_key == "timeRange":
            if "startSec" not in segment_locator or "endSec" not in segment_locator:
                return None
        elif raw_key not in segment_locator:
            return None
        if raw_key != "timeRange" and segment_locator.get(raw_key) != raw_value:
            return None

    if segment.get("segmentType") == "video_caption":
        if "timeRange" in raw_locator:
            start_sec, end_sec = raw_locator["timeRange"]
        else:
            start_sec = _as_int(segment.get("startSec"))
            end_sec = _as_int(segment.get("endSec"))
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            return None
        if outline_start is not None and start_sec < outline_start:
            return None
        if outline_end is not None and end_sec > outline_end:
            return None
        segment_start = _as_int(segment.get("startSec"))
        segment_end = _as_int(segment.get("endSec"))
        if segment_start is not None and start_sec < segment_start:
            return None
        if segment_end is not None and end_sec > segment_end:
            return None
        locator = {"startSec": start_sec, "endSec": end_sec}
    else:
        locator = segment_locator

    resource_id = _as_positive_int(segment.get("resourceId") or raw_item.get("resourceId") or raw_item.get("resource_id"))
    if resource_id is None:
        return None

    citation: dict[str, Any] = {
        "resourceId": resource_id,
        "segmentKey": segment["segmentKey"],
        "refLabel": clean_text(str(raw_item.get("refLabel") or raw_item.get("ref_label") or "")) or segment_label(segment),
    }
    segment_id = _as_positive_int(segment.get("segmentId") or raw_item.get("segmentId") or raw_item.get("segment_id"))
    if segment_id is not None:
        citation["segmentId"] = segment_id
    citation.update(locator)
    return citation


def _segment_locator(segment: Mapping[str, Any]) -> dict[str, Any]:
    if _as_int(segment.get("pageNo")) is not None:
        return {"pageNo": int(segment["pageNo"])}
    if _as_int(segment.get("slideNo")) is not None:
        return {"slideNo": int(segment["slideNo"])}
    anchor_key = segment.get("anchorKey")
    if isinstance(anchor_key, str) and anchor_key.strip():
        return {"anchorKey": clean_text(anchor_key)}
    if segment.get("segmentType") == "docx_block_text" or segment.get("sectionPath"):
        return {"anchorKey": str(segment["segmentKey"])}
    start_sec = _as_int(segment.get("startSec"))
    end_sec = _as_int(segment.get("endSec"))
    if start_sec is not None and end_sec is not None and end_sec > start_sec:
        return {"startSec": start_sec, "endSec": end_sec}
    return {}


def _raw_locator(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    locators: dict[str, Any] = {}
    for key in ("pageNo", "slideNo"):
        value = _as_int(_field_value(raw_item, key, _camel_to_snake(key)))
        if value is not None:
            locators[key] = value
    anchor_key = _field_value(raw_item, "anchorKey", "anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        locators["anchorKey"] = clean_text(anchor_key)
    start_sec = _as_int(_field_value(raw_item, "startSec", "start_sec"))
    end_sec = _as_int(_field_value(raw_item, "endSec", "end_sec"))
    if start_sec is not None or end_sec is not None:
        if start_sec is not None and end_sec is not None:
            locators["timeRange"] = (start_sec, end_sec)
        else:
            locators["time"] = None
    return locators


def segment_label(segment: Mapping[str, Any]) -> str:
    if segment.get("segmentType") == "video_caption":
        start_sec = _as_int(segment.get("startSec")) or 0
        end_sec = _as_int(segment.get("endSec")) or start_sec
        return f"视频 {start_sec:02d}s-{end_sec:02d}s"
    if _as_int(segment.get("pageNo")) is not None:
        return f"PDF 第 {int(segment['pageNo'])} 页"
    if _as_int(segment.get("slideNo")) is not None:
        return f"PPT 第 {int(segment['slideNo'])} 页"
    return "文档片段"


def _valid_source_keys(value: Any, *, source_key_set: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for item in value:
        key = _stable_key(str(item or ""))
        if key in source_key_set and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _video_segment_is_in_outline(segment: Mapping[str, Any], *, outline_start: int | None, outline_end: int | None) -> bool:
    if outline_start is None or outline_end is None:
        return True
    start_sec = _as_int(segment.get("startSec"))
    end_sec = _as_int(segment.get("endSec"))
    return start_sec is not None and end_sec is not None and outline_start <= start_sec and end_sec <= outline_end


def _video_segment_overlaps(segment: Mapping[str, Any], *, outline_start: int, outline_end: int) -> bool:
    start_sec = _as_int(segment.get("startSec"))
    end_sec = _as_int(segment.get("endSec"))
    return start_sec is not None and end_sec is not None and start_sec < outline_end and end_sec > outline_start


def _build_handout_block_prompt(
    outline_item: Mapping[str, Any],
    context_segments: Sequence[Mapping[str, Any]],
    *,
    preferences: Mapping[str, Any] | None,
) -> str:
    return "\n".join(
        [
            f"outline item：{json.dumps(dict(outline_item), ensure_ascii=False, sort_keys=True)}",
            f"preferences：{json.dumps(dict(preferences or {}), ensure_ascii=False, sort_keys=True)}",
            "segments："
            + json.dumps(
                [_serializable_segment(segment) for segment in context_segments],
                ensure_ascii=False,
                sort_keys=True,
            ),
        ]
    )


def _serializable_segment(segment: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "resourceId",
        "segmentId",
        "segmentKey",
        "segmentType",
        "orderNo",
        "textContent",
        "pageNo",
        "slideNo",
        "anchorKey",
        "startSec",
        "endSec",
        "sectionPath",
    )
    return {key: segment[key] for key in keys if key in segment}


def _parse_chat_json_payload(payload: dict[str, Any], *, label: str) -> dict[str, Any]:
    if "error" in payload:
        raise RuntimeError(f"{label} failed: {payload['error']}")
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{label} response missing message content") from exc

    text = _message_content_to_text(content)
    json_text = _extract_json_object(text)
    if json_text is None:
        raise RuntimeError(f"{label} response is not JSON")
    try:
        result = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} response has invalid JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{label} JSON must be an object")
    return result


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


def _first_present(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _field_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _difficulty_level(value: Any, *, preferences: Mapping[str, Any] | None) -> DifficultyLevel:
    text = str(value or preferences.get("difficultyLevel") if preferences else value or "").strip()
    if text in {"beginner", "intermediate", "advanced"}:
        return text  # type: ignore[return-value]
    return "beginner"


def _score_0_to_100(value: Any, default: int) -> int:
    parsed = _as_int(value)
    if parsed is None:
        return default
    return min(max(parsed, 0), 100)


def _estimated_minutes(value: Any, content_md: str) -> int:
    parsed = _as_int(value)
    if parsed is not None and parsed > 0:
        return parsed
    visible_chars = len(re.sub(r"\s+", "", content_md))
    return max(1, min(12, round(visible_chars / 220) or 1))


def _stable_key(value: str, fallback: str = "item") -> str:
    key = re.sub(r"[^a-zA-Z0-9._:-]+", "-", value).strip("-._:")
    if not key or not re.match(r"^[a-zA-Z0-9]", key):
        key = fallback
    return key


def _clean_markdown(value: str) -> str:
    lines = [clean_text(line) for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _truncate(text: str, max_chars: int) -> str:
    cleaned = " ".join(clean_text(text).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _as_positive_int(value: Any) -> int | None:
    parsed = _as_int(value)
    if parsed is None or parsed < 1:
        return None
    return parsed


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


def _chat_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def _camel_to_snake(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", value).lower()
