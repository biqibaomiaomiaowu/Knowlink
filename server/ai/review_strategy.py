from __future__ import annotations

from typing import Any, Mapping, Sequence

from server.parsers.base import clean_text


_MAX_REVIEW_TASKS = 3
_DEFAULT_MASTERY_SCORE = 0.5
_DEFAULT_CONFIDENCE_SCORE = 0.3


def build_mastery_record_updates(
    quiz_attempt_result: Mapping[str, Any],
    *,
    existing_records: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    records_by_key = {
        _stable_key(_field_value(record, "knowledgePointKey", "knowledge_point_key")): record
        for record in existing_records
        if isinstance(record, Mapping)
    }
    updates: list[dict[str, Any]] = []

    for delta in _mapping_list(_field_value(quiz_attempt_result, "masteryDelta", "mastery_delta")):
        kp_key = _stable_key(_field_value(delta, "knowledgePointKey", "knowledge_point_key"))
        if not kp_key:
            continue
        current = records_by_key.get(kp_key, {})
        current_mastery = _score(_field_value(current, "masteryScore", "mastery_score"), _DEFAULT_MASTERY_SCORE)
        current_confidence = _score(
            _field_value(current, "confidenceScore", "confidence_score"),
            _DEFAULT_CONFIDENCE_SCORE,
        )
        mastery_delta = _float(_field_value(delta, "delta"), 0.0)
        correct_delta = _as_int(_field_value(delta, "correctCount", "correct_count")) or 0
        wrong_delta = _as_int(_field_value(delta, "wrongCount", "wrong_count")) or 0
        confidence_delta = 0.06 if wrong_delta == 0 and correct_delta > 0 else -0.04 if wrong_delta > 0 else 0.0
        next_mastery = _clamp(current_mastery + mastery_delta)
        next_confidence = _clamp(current_confidence + confidence_delta)

        if wrong_delta > 0:
            status = "needs_review"
        elif mastery_delta > 0:
            status = "improved"
        else:
            status = "unchanged"

        updates.append(
            {
                "knowledgePointKey": kp_key,
                "knowledgePoint": clean_text(str(_field_value(delta, "knowledgePoint", "knowledge_point") or kp_key)),
                "masteryScoreDelta": round(mastery_delta, 4),
                "confidenceDelta": round(confidence_delta, 4),
                "nextMasteryScore": round(next_mastery, 4),
                "nextConfidenceScore": round(next_confidence, 4),
                "correctCountDelta": correct_delta,
                "wrongCountDelta": wrong_delta,
                "reviewPriority": _review_priority(next_mastery, next_confidence, wrong_delta),
                "sourceQuestionKeys": _source_question_keys(delta),
                "status": status,
            }
        )

    return sorted(updates, key=lambda item: (-item["reviewPriority"], item["knowledgePointKey"]))


def generate_review_tasks(
    quiz_attempt_result: Mapping[str, Any],
    *,
    quiz_payload: Mapping[str, Any],
    handout_blocks: Sequence[Mapping[str, Any]],
    mastery_updates: Sequence[Mapping[str, Any]] | None = None,
    max_tasks: int = _MAX_REVIEW_TASKS,
) -> dict[str, Any]:
    updates = list(mastery_updates) if mastery_updates is not None else build_mastery_record_updates(quiz_attempt_result)
    question_context = _question_context_by_kp(quiz_payload)
    block_context = _block_context_by_key(handout_blocks)
    task_candidates: list[dict[str, Any]] = []

    for update in updates:
        kp_key = _stable_key(_field_value(update, "knowledgePointKey", "knowledge_point_key"))
        if not kp_key:
            continue
        context = question_context.get(kp_key, {})
        block_key = _stable_key(context.get("sourceBlockKey"))
        block = block_context.get(block_key, {})
        source_segment_keys = _source_segment_keys(context, block)
        if not source_segment_keys:
            continue
        task_type = _task_type(update, context)
        priority = min(100, max(0, (_as_int(update.get("reviewPriority")) or 0) + _importance_bonus(block, kp_key)))
        question_keys = [
            key
            for key in _string_list(context.get("questionKeys")) + _string_list(update.get("sourceQuestionKeys"))
            if key
        ]
        task = {
            "taskKey": f"review-{kp_key}",
            "taskType": task_type,
            "priorityScore": priority,
            "reasonText": _reason_text(update, context),
            "recommendedMinutes": _recommended_minutes(priority, task_type),
            "knowledgePointKey": kp_key,
            "sourceQuestionKeys": _dedupe(question_keys),
            "sourceBlockKey": block_key,
            "sourceSegmentKeys": source_segment_keys,
            "reviewOrder": 0,
            "reasonTags": _reason_tags(update, priority),
            "recommendedAction": {
                "type": "revisit_block" if task_type != "redo_quiz" else "redo_quiz",
                "targetBlockKey": block_key,
                "label": "回看讲义块" if task_type != "redo_quiz" else "再练同类题",
            },
        }
        task_candidates.append(task)

    limit = min(_MAX_REVIEW_TASKS, max(1, max_tasks))
    tasks: list[dict[str, Any]] = []
    for task in sorted(task_candidates, key=lambda item: (-item["priorityScore"], item["taskKey"]))[:limit]:
        tasks.append({**task, "reviewOrder": len(tasks) + 1})

    return {"tasks": tasks}


def build_review_task_refs(
    review_payload: Mapping[str, Any],
    *,
    handout_blocks: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    blocks_by_key = _block_context_by_key(handout_blocks)
    segments_by_key = {
        _stable_key(_field_value(segment, "segmentKey", "segment_key")): segment
        for segment in segments
        if isinstance(segment, Mapping)
    }
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[tuple[str, Any], ...]]] = set()

    for task_index, task in enumerate(_mapping_list(review_payload.get("tasks")), start=1):
        task_key = _stable_key(_field_value(task, "taskKey", "task_key")) or f"review-{task_index}"
        block_key = _stable_key(_field_value(task, "sourceBlockKey", "source_block_key"))
        source_segment_keys = set(_string_list(_field_value(task, "sourceSegmentKeys", "source_segment_keys")))
        citations = _mapping_list(_field_value(blocks_by_key.get(block_key, {}), "citations"))

        for citation in citations:
            segment_key = _stable_key(_field_value(citation, "segmentKey", "segment_key"))
            if segment_key not in source_segment_keys:
                continue
            ref = _ref_from_citation(
                citation,
                task_key=task_key,
                sort_no=len(refs) + 1,
                segment=segments_by_key.get(segment_key),
            )
            if ref is None:
                continue
            identity = (task_key, str(ref.get("segmentId") or ref.get("segmentKey")), _locator_tuple(ref))
            if identity in seen:
                continue
            seen.add(identity)
            refs.append(ref)

        if any(ref["taskKey"] == task_key for ref in refs):
            continue
        for segment_key in sorted(source_segment_keys):
            segment = segments_by_key.get(segment_key)
            ref = _ref_from_segment(segment, task_key=task_key, sort_no=len(refs) + 1) if segment else None
            if ref is not None:
                refs.append(ref)
                break

    return refs


def _question_context_by_kp(quiz_payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for index, question in enumerate(_mapping_list(quiz_payload.get("questions")), start=1):
        kp_key = _stable_key(_field_value(question, "knowledgePointKey", "knowledge_point_key"))
        if not kp_key:
            continue
        item = context.setdefault(
            kp_key,
            {
                "questionKeys": [],
                "sourceSegmentKeys": [],
                "knowledgePointName": clean_text(
                    str(_field_value(question, "knowledgePointName", "knowledge_point_name") or kp_key)
                ),
                "difficultyLevel": str(_field_value(question, "difficultyLevel", "difficulty_level") or "medium"),
                "sourceBlockKey": _stable_key(_field_value(question, "sourceBlockKey", "source_block_key")),
            },
        )
        item["questionKeys"].append(_question_key(question, fallback_index=index))
        for segment_key in _string_list(_field_value(question, "sourceSegmentKeys", "source_segment_keys")):
            item["sourceSegmentKeys"].append(segment_key)
    return context


def _block_context_by_key(handout_blocks: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    blocks: dict[str, Mapping[str, Any]] = {}
    for index, block in enumerate(handout_blocks, start=1):
        if isinstance(block, Mapping):
            blocks[_block_key(block, fallback_index=index)] = block
    return blocks


def _source_segment_keys(context: Mapping[str, Any], block: Mapping[str, Any]) -> list[str]:
    keys = _string_list(context.get("sourceSegmentKeys"))
    if keys:
        return _dedupe(keys)
    for citation in _mapping_list(_field_value(block, "citations")):
        key = _stable_key(_field_value(citation, "segmentKey", "segment_key"))
        if key:
            keys.append(key)
    return _dedupe(keys)


def _task_type(update: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    if (_as_int(update.get("wrongCountDelta")) or 0) > 0:
        return "revisit_block"
    if str(context.get("difficultyLevel")) == "hard":
        return "formula_drill"
    return "redo_quiz"


def _reason_text(update: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    kp_name = clean_text(str(context.get("knowledgePointName") or update.get("knowledgePoint") or update.get("knowledgePointKey")))
    if (_as_int(update.get("wrongCountDelta")) or 0) > 0:
        return f"“{kp_name}”本轮出现错题，建议先回看来源讲义块再重做同类题。"
    if (_float(update.get("nextMasteryScore"), 0.0) < 0.7):
        return f"“{kp_name}”掌握度仍未稳定，建议用短练习巩固。"
    return f"“{kp_name}”本轮答对，建议做一次间隔复测保持熟练度。"


def _reason_tags(update: Mapping[str, Any], priority: int) -> list[str]:
    tags: list[str] = []
    if (_as_int(update.get("wrongCountDelta")) or 0) > 0:
        tags.append("recent_wrong")
    if _float(update.get("nextMasteryScore"), 1.0) < 0.7:
        tags.append("low_mastery")
    if priority >= 85:
        tags.append("high_priority")
    return tags or ["spacing_review"]


def _recommended_minutes(priority: int, task_type: str) -> int:
    if task_type == "formula_drill":
        return 18 if priority >= 85 else 12
    if priority >= 85:
        return 15
    if priority >= 70:
        return 10
    return 6


def _importance_bonus(block: Mapping[str, Any], kp_key: str) -> int:
    for item in _mapping_list(_field_value(block, "knowledgePoints", "knowledge_points")):
        if _stable_key(_field_value(item, "knowledgePointKey", "knowledge_point_key")) == kp_key:
            score = _as_int(_field_value(item, "importanceScore", "importance_score")) or 0
            return 8 if score >= 90 else 4 if score >= 75 else 0
    return 0


def _review_priority(mastery_score: float, confidence_score: float, wrong_count: int) -> int:
    raw = (1 - mastery_score) * 65 + (1 - confidence_score) * 20 + min(2, wrong_count) * 12
    return min(100, max(0, round(raw)))


def _source_question_keys(delta: Mapping[str, Any]) -> list[str]:
    return _string_list(_field_value(delta, "questionKeys", "question_keys", "sourceQuestionKeys", "source_question_keys"))


def _question_key(question: Mapping[str, Any], *, fallback_index: int) -> str:
    key = _stable_key(_field_value(question, "questionKey", "question_key"))
    if key:
        return key
    question_id = _field_value(question, "questionId", "question_id")
    return str(question_id) if question_id is not None else f"q{fallback_index}"


def _ref_from_citation(
    citation: Mapping[str, Any],
    *,
    task_key: str,
    sort_no: int,
    segment: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    resource_id = _as_int(_field_value(citation, "resourceId", "resource_id"))
    locator = _locator(citation)
    if resource_id is None or not locator:
        return None
    segment_key = _stable_key(_field_value(citation, "segmentKey", "segment_key"))
    ref = {
        "taskKey": task_key,
        "resourceId": resource_id,
        "segmentId": _as_int(_field_value(segment or citation, "segmentId", "segment_id")),
        "segmentKey": segment_key,
        "refType": _ref_type(locator),
        "quoteText": _quote_text(segment, citation),
        "refLabel": clean_text(str(_field_value(citation, "refLabel", "ref_label") or "")),
        "sortNo": sort_no,
        **locator,
    }
    return {key: value for key, value in ref.items() if value not in (None, "", [])}


def _ref_from_segment(segment: Mapping[str, Any], *, task_key: str, sort_no: int) -> dict[str, Any] | None:
    resource_id = _as_int(_field_value(segment, "resourceId", "resource_id"))
    locator = _locator(segment)
    if resource_id is None or not locator:
        return None
    segment_key = _stable_key(_field_value(segment, "segmentKey", "segment_key"))
    ref = {
        "taskKey": task_key,
        "resourceId": resource_id,
        "segmentId": _as_int(_field_value(segment, "segmentId", "segment_id")),
        "segmentKey": segment_key,
        "refType": _ref_type(locator),
        "quoteText": _quote_text(segment, segment),
        "refLabel": clean_text(str(_field_value(segment, "refLabel", "ref_label") or segment_key)),
        "sortNo": sort_no,
        **locator,
    }
    return {key: value for key, value in ref.items() if value not in (None, "", [])}


def _locator(item: Mapping[str, Any]) -> dict[str, Any]:
    page_no = _as_int(_field_value(item, "pageNo", "page_no"))
    slide_no = _as_int(_field_value(item, "slideNo", "slide_no"))
    anchor_key = _stable_key(_field_value(item, "anchorKey", "anchor_key"))
    start_sec = _as_int(_field_value(item, "startSec", "start_sec"))
    end_sec = _as_int(_field_value(item, "endSec", "end_sec"))
    if page_no is not None:
        return {"pageNo": page_no}
    if slide_no is not None:
        return {"slideNo": slide_no}
    if anchor_key:
        return {"anchorKey": anchor_key}
    if start_sec is not None and end_sec is not None and end_sec >= start_sec:
        return {"startSec": start_sec, "endSec": end_sec}
    return {}


def _ref_type(locator: Mapping[str, Any]) -> str:
    if "startSec" in locator and "endSec" in locator:
        return "video_time_range"
    if "pageNo" in locator:
        return "pdf_page"
    if "slideNo" in locator:
        return "ppt_slide"
    if "anchorKey" in locator:
        return "doc_anchor"
    return "segment"


def _locator_tuple(ref: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple((key, ref[key]) for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec") if key in ref)


def _quote_text(segment: Mapping[str, Any] | None, fallback: Mapping[str, Any]) -> str:
    text = clean_text(str(_field_value(segment or {}, "textContent", "text_content") or ""))
    if not text:
        text = clean_text(str(_field_value(fallback, "quoteText", "quote_text", "refLabel", "ref_label") or ""))
    return text[:300]


def _block_key(block: Mapping[str, Any], *, fallback_index: int) -> str:
    return _stable_key(_field_value(block, "handoutBlockId", "blockId", "outlineKey", "outline_key")) or f"block-{fallback_index}"


def _score(value: Any, fallback: float) -> float:
    return _clamp(_float(value, fallback))


def _float(value: Any, fallback: float) -> float:
    if isinstance(value, bool) or value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_stable_key(item) for item in value if _stable_key(item)]


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _field_value(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _stable_key(value: Any) -> str:
    return str(value or "").strip()
