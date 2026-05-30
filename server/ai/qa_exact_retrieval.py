from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Mapping, Sequence

from server.ai.qa_candidate_utils import (
    locator_key as _locator_key,
    qa_candidate_identity,
    replace_candidate_rank as _replace_rank,
)
from server.ai.qa_types import QaCandidateSource, QaEvidenceCandidate, QaScope
from server.parsers.base import clean_text


class ExactEvidenceRetriever:
    def retrieve(self, *, scope: QaScope, context: Mapping[str, Any]) -> list[QaEvidenceCandidate]:
        current_block = _mapping_value(context.get("currentBlock")) or _mapping_value(context.get("current_block"))
        if current_block is None:
            return []
        return _retrieve_exact_evidence(
            current_block=current_block,
            segments=_mapping_sequence(context.get("segments")),
            knowledge_point_evidences=_mapping_sequence(
                context.get("knowledgePointEvidences") or context.get("knowledge_point_evidences")
            ),
            adjacent_blocks=_mapping_sequence(context.get("adjacentBlocks") or context.get("adjacent_blocks")),
            scope=scope,
        )


def build_exact_evidence_candidates(
    *,
    current_block: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]] = (),
    knowledge_point_evidences: Sequence[Mapping[str, Any]] = (),
    adjacent_blocks: Sequence[Mapping[str, Any]] = (),
    active_course_id: int | None = None,
    active_parse_run_id: int | None = None,
    active_handout_version_id: int | None = None,
) -> list[QaEvidenceCandidate]:
    scope = QaScope(
        course_id=_as_positive_int(active_course_id)
        or _as_positive_int(_field_value(current_block, "courseId", "course_id")),
        active_parse_run_id=_as_positive_int(active_parse_run_id)
        or _as_positive_int(_field_value(current_block, "parseRunId", "parse_run_id")),
        active_handout_version_id=_as_positive_int(active_handout_version_id)
        or _as_positive_int(_field_value(current_block, "handoutVersionId", "handout_version_id")),
        current_handout_block_id=_field_value(
            current_block,
            "handoutBlockId",
            "handout_block_id",
            "outlineKey",
            "outline_key",
        ),
        current_outline_key=_field_value(current_block, "outlineKey", "outline_key"),
        current_sort_no=_as_int(_field_value(current_block, "sortNo", "sort_no")),
    )
    return ExactEvidenceRetriever().retrieve(
        scope=scope,
        context={
            "currentBlock": current_block,
            "segments": segments,
            "knowledgePointEvidences": knowledge_point_evidences,
            "adjacentBlocks": adjacent_blocks,
        },
    )


def qa_evidence_candidate_from_segment_payload(
    segment: Mapping[str, Any],
    *,
    source: QaCandidateSource = "course_wide_segment_lexical",
    rank: int = 1,
    handout_block_id: int | str | None = None,
    handout_version_id: int | None = None,
    score: float | None = None,
) -> QaEvidenceCandidate | None:
    normalized = _normalize_segment(segment, rank)
    candidate = _candidate_from_segment(
        normalized,
        source=source,
        rank=rank,
        handout_block_id=handout_block_id,
        handout_version_id=handout_version_id,
        content_override=None,
        ref_label=clean_text(str(_field_value(segment, "refLabel", "ref_label") or "")) or None,
        locator_override=None,
    )
    if candidate is None or score is None:
        return candidate
    return replace(candidate, score=score)


def _retrieve_exact_evidence(
    *,
    current_block: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
    knowledge_point_evidences: Sequence[Mapping[str, Any]],
    adjacent_blocks: Sequence[Mapping[str, Any]],
    scope: QaScope,
) -> list[QaEvidenceCandidate]:
    course_id = scope.course_id
    parse_run_id = scope.active_parse_run_id
    handout_version_id = scope.active_handout_version_id
    block_id = scope.current_handout_block_id

    if not _block_matches_active_scope(
        current_block,
        active_course_id=course_id,
        active_parse_run_id=parse_run_id,
        active_handout_version_id=handout_version_id,
    ):
        return []

    normalized_segments = [_normalize_segment(segment, index) for index, segment in enumerate(segments, start=1)]
    segment_by_key = {segment["segmentKey"]: segment for segment in normalized_segments if segment.get("segmentKey")}
    segment_by_id = {
        int(segment["segmentId"]): segment
        for segment in normalized_segments
        if _as_positive_int(segment.get("segmentId")) is not None
    }

    candidates: list[QaEvidenceCandidate] = []
    seen: set[tuple[int, str, tuple[tuple[str, Any], ...]]] = set()

    def append(candidate: QaEvidenceCandidate | None) -> None:
        if candidate is None:
            return
        identity = qa_candidate_identity(candidate)
        if identity in seen:
            return
        seen.add(identity)
        candidates.append(candidate)

    for citation in _mapping_list(current_block.get("citations")):
        append(
            _candidate_from_citation(
                citation,
                segment_by_key=segment_by_key,
                segment_by_id=segment_by_id,
                segments=normalized_segments,
                source="current_block_ref",
                rank=len(candidates) + 1,
                fallback_content=_block_text(current_block),
                fallback_handout_block_id=block_id,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
            )
        )

    for source_segment_key in _source_segment_keys(current_block):
        segment = segment_by_key.get(_stable_key(source_segment_key))
        if segment is None:
            continue
        if segment.get("segmentType") != "video_caption":
            continue
        if not _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id):
            continue
        append(
            _candidate_from_segment(
                segment,
                source="current_block_source_segment",
                rank=len(candidates) + 1,
                handout_block_id=block_id,
                handout_version_id=handout_version_id,
                content_override=None,
                ref_label=None,
                locator_override=None,
            )
        )

    current_kp_keys = _current_block_knowledge_point_keys(current_block)
    for evidence in knowledge_point_evidences:
        if not isinstance(evidence, Mapping):
            continue
        if not current_kp_keys:
            continue
        if str(_field_value(evidence, "knowledgePointKey", "knowledge_point_key") or "") not in current_kp_keys:
            continue
        append(
            _candidate_from_evidence(
                evidence,
                segment_by_key=segment_by_key,
                segment_by_id=segment_by_id,
                segments=normalized_segments,
                rank=len(candidates) + 1,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
                handout_block_id=block_id,
            )
        )

    for adjacent_block in _sorted_adjacent_blocks(adjacent_blocks, current_block=current_block):
        if handout_version_id is not None:
            adjacent_version_id = _as_positive_int(_field_value(adjacent_block, "handoutVersionId", "handout_version_id"))
            if adjacent_version_id != handout_version_id:
                continue
        if not _block_matches_active_scope(
            adjacent_block,
            active_course_id=course_id,
            active_parse_run_id=parse_run_id,
            active_handout_version_id=handout_version_id,
        ):
            continue
        for citation in _mapping_list(adjacent_block.get("citations")):
            append(
                _candidate_from_citation(
                    citation,
                    segment_by_key=segment_by_key,
                    segment_by_id=segment_by_id,
                    segments=normalized_segments,
                    source="adjacent_block",
                    rank=len(candidates) + 1,
                    fallback_content=_block_text(adjacent_block),
                    fallback_handout_block_id=_field_value(
                        adjacent_block,
                        "handoutBlockId",
                        "handout_block_id",
                        "outlineKey",
                        "outline_key",
                    ),
                    course_id=course_id,
                    parse_run_id=parse_run_id,
                    handout_version_id=handout_version_id,
                )
            )

    return [_replace_rank(candidate, index) for index, candidate in enumerate(candidates, start=1)]


def _candidate_from_evidence(
    evidence: Mapping[str, Any],
    *,
    segment_by_key: Mapping[str, Mapping[str, Any]],
    segment_by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    rank: int,
    course_id: int | None,
    parse_run_id: int | None,
    handout_version_id: int | None,
    handout_block_id: int | str | None,
) -> QaEvidenceCandidate | None:
    segment = _segment_from_ref(evidence, segment_by_key=segment_by_key, segment_by_id=segment_by_id, segments=segments)
    if segment is None or not _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id):
        return None
    return _candidate_from_segment(
        segment,
        source="knowledge_point_evidence",
        rank=rank,
        handout_block_id=handout_block_id,
        handout_version_id=handout_version_id,
        content_override=None,
        ref_label=None,
        locator_override=None,
    )


def _candidate_from_citation(
    citation: Mapping[str, Any],
    *,
    segment_by_key: Mapping[str, Mapping[str, Any]],
    segment_by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    source: QaCandidateSource,
    rank: int,
    fallback_content: str,
    fallback_handout_block_id: int | str | None,
    course_id: int | None,
    parse_run_id: int | None,
    handout_version_id: int | None,
) -> QaEvidenceCandidate | None:
    segment = _segment_from_ref(citation, segment_by_key=segment_by_key, segment_by_id=segment_by_id, segments=segments)
    if segment is None:
        return None
    if not _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id):
        return None

    locator = _locator_from_citation_segment(citation, segment)
    if not locator:
        return None
    return _candidate_from_segment(
        segment,
        source=source,
        rank=rank,
        handout_block_id=fallback_handout_block_id,
        handout_version_id=handout_version_id,
        content_override=fallback_content if source == "adjacent_block" else None,
        ref_label=clean_text(str(_field_value(citation, "refLabel", "ref_label") or "")) or None,
        locator_override=locator,
    )


def _candidate_from_segment(
    segment: Mapping[str, Any],
    *,
    source: QaCandidateSource,
    rank: int,
    handout_block_id: int | str | None,
    handout_version_id: int | None,
    content_override: str | None,
    ref_label: str | None,
    locator_override: Mapping[str, Any] | None,
) -> QaEvidenceCandidate | None:
    content_text = clean_text(content_override or str(segment.get("textContent") or segment.get("plainText") or ""))
    if not content_text:
        return None
    resource_id = _as_positive_int(segment.get("resourceId"))
    locator = dict(locator_override or _locator(segment))
    if resource_id is None or not locator:
        return None
    segment_key = str(segment.get("segmentKey") or "")
    return QaEvidenceCandidate(
        candidate_key=f"{source}:{segment_key or rank}:{_locator_key(locator)}",
        source=source,
        rank=rank,
        content_text=content_text,
        resource_id=resource_id,
        ref_label=ref_label or _segment_label(segment, locator=locator),
        locator=locator,
        segment_id=_as_positive_int(segment.get("segmentId")),
        segment_key=segment_key or None,
        course_id=_as_positive_int(segment.get("courseId")),
        parse_run_id=_as_positive_int(segment.get("parseRunId")),
        handout_version_id=handout_version_id,
        handout_block_id=handout_block_id,
        metadata_json={
            key: value
            for key, value in {
                "segmentType": segment.get("segmentType"),
                "resourceType": segment.get("resourceType"),
                "source": source,
            }.items()
            if value not in (None, "")
        },
    )


def _locator_from_citation_segment(citation: Mapping[str, Any], segment: Mapping[str, Any]) -> dict[str, Any]:
    segment_locator = _locator(segment)
    if not segment_locator:
        return {}

    citation_locator = _locator(citation)
    if not citation_locator:
        return segment_locator

    if "startSec" in segment_locator and "endSec" in segment_locator:
        if "startSec" not in citation_locator or "endSec" not in citation_locator:
            return segment_locator
        start_sec = _as_int(citation_locator.get("startSec"))
        end_sec = _as_int(citation_locator.get("endSec"))
        segment_start = _as_int(segment_locator.get("startSec"))
        segment_end = _as_int(segment_locator.get("endSec"))
        if (
            start_sec is None
            or end_sec is None
            or segment_start is None
            or segment_end is None
            or start_sec < segment_start
            or end_sec > segment_end
            or end_sec <= start_sec
        ):
            return {}
        return {"startSec": start_sec, "endSec": end_sec}

    return segment_locator


def _segment_from_ref(
    ref: Mapping[str, Any],
    *,
    segment_by_key: Mapping[str, Mapping[str, Any]],
    segment_by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    key = _field_value(ref, "segmentKey", "segment_key")
    segment_from_key = segment_by_key.get(_stable_key(key)) if isinstance(key, str) and key.strip() else None
    segment_id = _as_positive_int(_field_value(ref, "segmentId", "segment_id"))
    segment_from_id = segment_by_id.get(segment_id) if segment_id is not None else None
    if key or segment_id is not None:
        if segment_from_key is not None and segment_from_id is not None:
            if segment_from_key.get("segmentKey") != segment_from_id.get("segmentKey"):
                return None
            return segment_from_key
        return segment_from_key or segment_from_id

    resource_id = _as_positive_int(_field_value(ref, "resourceId", "resource_id"))
    locator = _locator(ref)
    if resource_id is None or not locator:
        return None
    for segment in segments:
        if _as_positive_int(segment.get("resourceId")) != resource_id:
            continue
        if _locator(segment) == locator:
            return segment
    return None


def _block_matches_active_scope(
    block: Mapping[str, Any],
    *,
    active_course_id: int | None,
    active_parse_run_id: int | None,
    active_handout_version_id: int | None,
) -> bool:
    course_id = _as_positive_int(_field_value(block, "courseId", "course_id"))
    parse_run_id = _as_positive_int(_field_value(block, "parseRunId", "parse_run_id"))
    handout_version_id = _as_positive_int(_field_value(block, "handoutVersionId", "handout_version_id"))
    if active_course_id is not None and course_id is not None and course_id != active_course_id:
        return False
    if active_parse_run_id is not None and parse_run_id is not None and parse_run_id != active_parse_run_id:
        return False
    if active_handout_version_id is not None and handout_version_id != active_handout_version_id:
        return False
    return True


def _current_block_knowledge_point_keys(block: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for item in _mapping_list(block.get("knowledgePoints") or block.get("knowledge_points")):
        key = _field_value(item, "knowledgePointKey", "knowledge_point_key")
        if isinstance(key, str) and key:
            keys.add(key)
    return keys


def _sorted_adjacent_blocks(
    adjacent_blocks: Sequence[Mapping[str, Any]],
    *,
    current_block: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    current_sort = _as_int(_field_value(current_block, "sortNo", "sort_no")) or 0
    return sorted(
        [block for block in adjacent_blocks if isinstance(block, Mapping)],
        key=lambda block: (
            abs((_as_int(_field_value(block, "sortNo", "sort_no")) or 0) - current_sort),
            _as_int(_field_value(block, "sortNo", "sort_no")) or 0,
        ),
    )


def _normalize_segment(segment: Mapping[str, Any], index: int) -> dict[str, Any]:
    clean_segment = dict(segment)
    clean_segment["segmentKey"] = _stable_key(_field_value(segment, "segmentKey", "segment_key") or f"segment-{index}")
    clean_segment["segmentType"] = str(_field_value(segment, "segmentType", "segment_type") or "")
    clean_segment["resourceType"] = str(_field_value(segment, "resourceType", "resource_type") or "")
    clean_segment["orderNo"] = _as_int(_field_value(segment, "orderNo", "order_no")) or index
    clean_segment["textContent"] = clean_text(
        str(_field_value(segment, "textContent", "text_content", "plainText", "plain_text") or "")
    )
    for camel, snake in (
        ("courseId", "course_id"),
        ("parseRunId", "parse_run_id"),
        ("resourceId", "resource_id"),
        ("segmentId", "segment_id"),
        ("pageNo", "page_no"),
        ("slideNo", "slide_no"),
        ("startSec", "start_sec"),
        ("endSec", "end_sec"),
    ):
        value = _as_int(_field_value(segment, camel, snake))
        if value is not None:
            clean_segment[camel] = value
    anchor_key = _field_value(segment, "anchorKey", "anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        clean_segment["anchorKey"] = clean_text(anchor_key)
    return clean_segment


def _matches_course_parse(segment: Mapping[str, Any], *, course_id: int | None, parse_run_id: int | None) -> bool:
    segment_course_id = _as_positive_int(segment.get("courseId"))
    segment_parse_run_id = _as_positive_int(segment.get("parseRunId"))
    if course_id is not None and segment_course_id != course_id:
        return False
    if parse_run_id is not None and segment_parse_run_id != parse_run_id:
        return False
    return True


def _block_text(block: Mapping[str, Any]) -> str:
    return clean_text(
        "\n".join(
            str(_field_value(block, key, _camel_to_snake(key)) or "")
            for key in ("title", "summary", "contentMd")
        )
    )


def _locator(payload: Mapping[str, Any]) -> dict[str, Any]:
    locators: dict[str, Any] = {}
    for key in ("pageNo", "slideNo"):
        value = _as_positive_int(_field_value(payload, key, _camel_to_snake(key)))
        if value is not None:
            locators[key] = value
    anchor_key = _field_value(payload, "anchorKey", "anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        locators["anchorKey"] = clean_text(anchor_key)
    start_sec = _as_int(_field_value(payload, "startSec", "start_sec"))
    end_sec = _as_int(_field_value(payload, "endSec", "end_sec"))
    if start_sec is not None and end_sec is not None and end_sec > start_sec:
        locators["startSec"] = start_sec
        locators["endSec"] = end_sec
    return locators if _locator_group_count(locators) == 1 else {}


def _locator_group_count(locator: Mapping[str, Any]) -> int:
    groups = 0
    groups += 1 if "pageNo" in locator else 0
    groups += 1 if "slideNo" in locator else 0
    groups += 1 if "anchorKey" in locator else 0
    groups += 1 if "startSec" in locator and "endSec" in locator else 0
    return groups


def _segment_label(segment: Mapping[str, Any], *, locator: Mapping[str, Any]) -> str:
    if "startSec" in locator and "endSec" in locator:
        return f"视频 {int(locator['startSec']):02d}s-{int(locator['endSec']):02d}s"
    if "pageNo" in locator:
        return f"PDF 第 {int(locator['pageNo'])} 页"
    if "slideNo" in locator:
        return f"PPT 第 {int(locator['slideNo'])} 页"
    if "anchorKey" in locator:
        title = clean_text(str(segment.get("title") or ""))
        return title or "文档片段"
    return "课程片段"


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping_sequence(value: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _mapping_value(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [clean_text(str(item)) for item in value if clean_text(str(item))]


def _source_segment_keys(block: Mapping[str, Any]) -> list[str]:
    return _string_list(_field_value(block, "sourceSegmentKeys", "source_segment_keys"))


def _field_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _camel_to_snake(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _stable_key(value: Any, fallback: str = "item") -> str:
    key = re.sub(r"[^a-zA-Z0-9._:-]+", "-", str(value or "")).strip("-._:")
    if not key or not re.match(r"^[a-zA-Z0-9]", key):
        return fallback
    return key


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_positive_int(value: Any) -> int | None:
    parsed = _as_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed
