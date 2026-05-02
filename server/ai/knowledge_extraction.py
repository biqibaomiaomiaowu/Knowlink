from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from server.parsers.base import clean_text


def handout_block_to_knowledge_extraction(
    block: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_segments = [_normalize_segment(segment, index) for index, segment in enumerate(segments, start=1)]
    by_key = {segment["segmentKey"]: segment for segment in normalized_segments}
    by_id = {
        int(segment["segmentId"]): segment
        for segment in normalized_segments
        if _as_positive_int(segment.get("segmentId")) is not None
    }

    knowledge_points = _knowledge_points(block.get("knowledgePoints") or block.get("knowledge_points"))
    known_kp_keys = {item["knowledgePointKey"] for item in knowledge_points}
    evidence_segments = _evidence_segments(block, by_key=by_key, by_id=by_id)

    segment_knowledge_points: list[dict[str, Any]] = []
    seen_relations: set[tuple[str, str]] = set()
    for segment_index, segment in enumerate(evidence_segments, start=1):
        for kp_index, knowledge_point in enumerate(knowledge_points, start=1):
            relation_key = (segment["segmentKey"], knowledge_point["knowledgePointKey"])
            if relation_key in seen_relations:
                continue
            seen_relations.add(relation_key)
            segment_knowledge_points.append(
                {
                    "segmentKey": segment["segmentKey"],
                    "knowledgePointKey": knowledge_point["knowledgePointKey"],
                    "relevanceScore": 1.0 if segment_index == 1 and kp_index == 1 else 0.75,
                    "sortNo": len(segment_knowledge_points) + 1,
                }
            )

    evidences: list[dict[str, Any]] = []
    for citation in block.get("citations", []):
        if not isinstance(citation, Mapping):
            continue
        segment = _segment_for_citation(citation, by_key=by_key, by_id=by_id)
        if segment is None:
            continue
        locator = _locator_from_citation(citation)
        if not locator:
            continue
        for knowledge_point in knowledge_points:
            kp_key = knowledge_point["knowledgePointKey"]
            if kp_key not in known_kp_keys:
                continue
            evidences.append(
                {
                    "segmentKey": segment["segmentKey"],
                    "knowledgePointKey": kp_key,
                    "evidenceType": _evidence_type(segment),
                    "sortNo": len(evidences) + 1,
                    **locator,
                }
            )

    return {
        "knowledgePoints": knowledge_points,
        "segmentKnowledgePoints": segment_knowledge_points,
        "knowledgePointEvidences": evidences,
    }


def _knowledge_points(payload: Any) -> list[dict[str, Any]]:
    raw_items = payload if isinstance(payload, list) else []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            continue
        display_name = clean_text(str(raw_item.get("displayName") or raw_item.get("display_name") or ""))
        description = clean_text(str(raw_item.get("description") or ""))
        if not display_name or not description:
            continue
        key = _stable_key(
            str(raw_item.get("knowledgePointKey") or raw_item.get("knowledge_point_key") or display_name),
            fallback=f"kp-{len(output) + 1}",
        )
        if key in seen:
            key = _stable_key(f"{key}-{len(output) + 1}")
        seen.add(key)
        output.append(
            {
                "knowledgePointKey": key,
                "displayName": display_name,
                "canonicalName": clean_text(
                    str(raw_item.get("canonicalName") or raw_item.get("canonical_name") or display_name)
                ),
                "description": description,
                "difficultyLevel": _difficulty_level(raw_item.get("difficultyLevel") or raw_item.get("difficulty_level")),
                "importanceScore": _score_0_to_100(raw_item.get("importanceScore") or raw_item.get("importance_score"), 80),
                "aliases": _aliases(raw_item.get("aliases")),
                "sortNo": len(output) + 1,
            }
        )

    if output:
        return output
    return [
        {
            "knowledgePointKey": "kp-1",
            "displayName": "本段知识点",
            "canonicalName": "本段知识点",
            "description": "由讲义块正文派生的知识点。",
            "difficultyLevel": "beginner",
            "importanceScore": 60,
            "aliases": [],
            "sortNo": 1,
        }
    ]


def _evidence_segments(
    block: Mapping[str, Any],
    *,
    by_key: Mapping[str, Mapping[str, Any]],
    by_id: Mapping[int, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    output: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for key in block.get("sourceSegmentKeys", []) or []:
        if isinstance(key, str) and key in by_key and key not in seen:
            output.append(by_key[key])
            seen.add(key)
    for citation in block.get("citations", []) or []:
        if not isinstance(citation, Mapping):
            continue
        segment = _segment_for_citation(citation, by_key=by_key, by_id=by_id)
        if segment is not None and segment["segmentKey"] not in seen:
            output.append(segment)
            seen.add(segment["segmentKey"])
    return output


def _segment_for_citation(
    citation: Mapping[str, Any],
    *,
    by_key: Mapping[str, Mapping[str, Any]],
    by_id: Mapping[int, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    key = citation.get("segmentKey") or citation.get("segment_key")
    if isinstance(key, str) and key in by_key:
        return by_key[key]
    segment_id = _as_positive_int(citation.get("segmentId") or citation.get("segment_id"))
    if segment_id is not None:
        return by_id.get(segment_id)
    return None


def _locator_from_citation(citation: Mapping[str, Any]) -> dict[str, Any]:
    locators: dict[str, Any] = {}
    for key in ("pageNo", "slideNo"):
        value = _as_positive_int(citation.get(key))
        if value is not None:
            locators[key] = value
    anchor_key = citation.get("anchorKey")
    if isinstance(anchor_key, str) and anchor_key.strip():
        locators["anchorKey"] = clean_text(anchor_key)
    start_sec = _as_int(citation.get("startSec"))
    end_sec = _as_int(citation.get("endSec"))
    if start_sec is not None and end_sec is not None and end_sec > start_sec:
        locators["startSec"] = start_sec
        locators["endSec"] = end_sec

    locator_groups = 0
    locator_groups += 1 if "pageNo" in locators else 0
    locator_groups += 1 if "slideNo" in locators else 0
    locator_groups += 1 if "anchorKey" in locators else 0
    locator_groups += 1 if "startSec" in locators and "endSec" in locators else 0
    return locators if locator_groups == 1 else {}


def _normalize_segment(segment: Mapping[str, Any], index: int) -> dict[str, Any]:
    clean_segment = dict(segment)
    clean_segment["segmentKey"] = str(segment.get("segmentKey") or segment.get("segment_key") or f"segment-{index}")
    clean_segment["segmentType"] = str(segment.get("segmentType") or segment.get("segment_type") or "")
    return clean_segment


def _evidence_type(segment: Mapping[str, Any]) -> str:
    if segment.get("segmentType") == "video_caption":
        return "teacher_emphasis"
    if segment.get("segmentType") == "formula":
        return "formula"
    if segment.get("segmentType") == "image_caption":
        return "example"
    return "summary"


def _aliases(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    aliases: list[str] = []
    seen: set[str] = set()
    for item in value:
        alias = clean_text(str(item or ""))
        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def _difficulty_level(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"beginner", "intermediate", "advanced"}:
        return text
    return "beginner"


def _score_0_to_100(value: Any, default: int) -> int:
    parsed = _as_int(value)
    if parsed is None:
        return default
    return min(max(parsed, 0), 100)


def _stable_key(value: str, *, fallback: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9._:-]+", "-", value).strip("-._:")
    if not key or not re.match(r"^[a-zA-Z0-9]", key):
        key = fallback
    return key


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
