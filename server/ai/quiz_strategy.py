from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from server.parsers.base import clean_text


QuizType = Literal["block_check", "chapter_review", "exam_drill"]
QuestionType = Literal["single_choice"]
DifficultyLevel = Literal["easy", "medium", "hard"]

_OPTION_LABELS = ("A", "B", "C", "D")
_MIN_QUESTION_COUNT = 3
_MAX_QUESTION_COUNT = 5
_DIFFICULTY_BY_SOURCE = {
    "beginner": "easy",
    "easy": "easy",
    "intermediate": "medium",
    "medium": "medium",
    "advanced": "hard",
    "hard": "hard",
}
_MASTERY_DELTA = {
    "easy": (0.10, -0.12),
    "medium": (0.14, -0.16),
    "hard": (0.18, -0.20),
}


@dataclass(frozen=True)
class QuizSourceCandidate:
    candidate_key: str
    block_key: str
    block_title: str
    knowledge_point_key: str
    knowledge_point_name: str
    description: str
    difficulty_level: DifficultyLevel
    importance_score: int
    source_segment_keys: tuple[str, ...]


def generate_quiz_payload(
    handout_blocks: Sequence[Mapping[str, Any]],
    *,
    quiz_type: QuizType = "chapter_review",
    question_count: int = _MIN_QUESTION_COUNT,
) -> dict[str, Any]:
    """Build a deterministic MVP quiz from ready handout blocks.

    The payload is intentionally model/API-neutral: it stores source keys for
    later reverse lookup and never asks an AI model to invent locator fields.
    """

    candidates = build_quiz_source_candidates(handout_blocks)
    if not candidates:
        raise ValueError("at least one cited handout block or knowledge point is required")

    target_count = min(_MAX_QUESTION_COUNT, max(_MIN_QUESTION_COUNT, question_count))
    selected = _repeat_to_count(candidates, target_count)

    return {
        "quizType": quiz_type,
        "questions": [
            _question_from_candidate(candidate, index=index)
            for index, candidate in enumerate(selected, start=1)
        ],
    }


def build_quiz_source_candidates(
    handout_blocks: Sequence[Mapping[str, Any]],
) -> list[QuizSourceCandidate]:
    candidates: list[QuizSourceCandidate] = []
    seen: set[tuple[str, str]] = set()

    for block_index, block in enumerate(handout_blocks, start=1):
        if not isinstance(block, Mapping):
            continue
        block_key = _block_key(block, fallback_index=block_index)
        block_title = clean_text(str(_field_value(block, "title") or f"讲义块 {block_index}")) or f"讲义块 {block_index}"
        source_segment_keys = _source_segment_keys(block)
        if not source_segment_keys:
            continue

        knowledge_points = _mapping_list(_field_value(block, "knowledgePoints", "knowledge_points"))
        if not knowledge_points:
            knowledge_points = [
                {
                    "knowledgePointKey": f"{block_key}-main",
                    "displayName": block_title,
                    "description": _text_summary(block),
                    "difficultyLevel": "medium",
                    "importanceScore": 60,
                }
            ]

        for kp_index, knowledge_point in enumerate(knowledge_points, start=1):
            kp_key = _stable_key(
                _field_value(knowledge_point, "knowledgePointKey", "knowledge_point_key")
                or f"{block_key}-kp-{kp_index}"
            )
            identity = (block_key, kp_key)
            if identity in seen:
                continue
            seen.add(identity)
            kp_name = clean_text(
                str(_field_value(knowledge_point, "displayName", "display_name", "canonicalName", "canonical_name") or "")
            )
            if not kp_name:
                kp_name = block_title
            description = clean_text(str(_field_value(knowledge_point, "description") or _text_summary(block)))
            if not description:
                description = f"结合“{block_title}”理解“{kp_name}”。"
            candidates.append(
                QuizSourceCandidate(
                    candidate_key=f"{block_key}:{kp_key}",
                    block_key=block_key,
                    block_title=block_title,
                    knowledge_point_key=kp_key,
                    knowledge_point_name=kp_name,
                    description=description,
                    difficulty_level=_difficulty_level(
                        _field_value(knowledge_point, "difficultyLevel", "difficulty_level"),
                        _field_value(knowledge_point, "importanceScore", "importance_score"),
                    ),
                    importance_score=_score(_field_value(knowledge_point, "importanceScore", "importance_score")),
                    source_segment_keys=tuple(source_segment_keys),
                )
            )

    return sorted(candidates, key=lambda item: (-item.importance_score, item.block_key, item.knowledge_point_key))


def grade_quiz_attempt(
    quiz_payload: Mapping[str, Any],
    answers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    questions = _mapping_list(quiz_payload.get("questions"))
    answers_by_key = _answers_by_question_key(answers)
    items: list[dict[str, Any]] = []
    delta_by_kp: dict[str, dict[str, Any]] = {}

    for index, question in enumerate(questions, start=1):
        question_key = _question_key(question, fallback_index=index)
        answer = _answer_for_question(question, question_key=question_key, answers_by_key=answers_by_key)
        selected = _normalize_selected_answer(
            _field_value(answer, "selectedOption", "selected_option"),
            question,
        )
        correct_answer = _normalize_answer(_field_value(question, "correctAnswer", "correct_answer"))
        is_correct = selected == correct_answer
        obtained_score = 1 if is_correct else 0
        difficulty = str(_field_value(question, "difficultyLevel", "difficulty_level") or "medium")
        if difficulty not in _MASTERY_DELTA:
            difficulty = "medium"
        delta = _MASTERY_DELTA[difficulty][0 if is_correct else 1]
        kp_key = _stable_key(_field_value(question, "knowledgePointKey", "knowledge_point_key"))
        kp_name = clean_text(str(_field_value(question, "knowledgePointName", "knowledge_point_name") or kp_key))

        items.append(
            {
                "questionKey": question_key,
                "selectedOption": selected,
                "correctAnswer": correct_answer,
                "isCorrect": is_correct,
                "obtainedScore": obtained_score,
                "explanationMd": str(_field_value(question, "explanationMd", "explanation_md") or ""),
                "knowledgePointKey": kp_key,
                "sourceBlockKey": _stable_key(_field_value(question, "sourceBlockKey", "source_block_key")),
            }
        )
        if kp_key:
            aggregate = delta_by_kp.setdefault(
                kp_key,
                {
                    "knowledgePointKey": kp_key,
                    "knowledgePoint": kp_name or kp_key,
                    "delta": 0.0,
                    "correctCount": 0,
                    "wrongCount": 0,
                    "questionKeys": [],
                },
            )
            aggregate["delta"] += delta
            aggregate["correctCount" if is_correct else "wrongCount"] += 1
            aggregate["questionKeys"].append(question_key)

    score = sum(item["obtainedScore"] for item in items)
    total_score = len(items)
    mastery_delta = [_finalize_mastery_delta(delta) for delta in delta_by_kp.values()]

    return {
        "score": score,
        "totalScore": total_score,
        "accuracy": round(score / total_score, 4) if total_score else 0.0,
        "items": items,
        "masteryDelta": mastery_delta,
        "recommendedReviewAction": _recommended_review_action(items),
    }


def build_quiz_question_refs(
    quiz_payload: Mapping[str, Any],
    *,
    handout_blocks: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    blocks_by_key = {}
    for block_index, block in enumerate(handout_blocks, start=1):
        if isinstance(block, Mapping):
            blocks_by_key[_block_key(block, fallback_index=block_index)] = block
    segments_by_key = {
        _stable_key(_field_value(segment, "segmentKey", "segment_key")): segment
        for segment in segments
        if isinstance(segment, Mapping)
    }
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[tuple[str, Any], ...]]] = set()

    for question_index, question in enumerate(_mapping_list(quiz_payload.get("questions")), start=1):
        question_key = _question_key(question, fallback_index=question_index)
        block_key = _stable_key(_field_value(question, "sourceBlockKey", "source_block_key"))
        source_segment_keys = {
            _stable_key(item)
            for item in _field_value(question, "sourceSegmentKeys", "source_segment_keys") or []
            if _stable_key(item)
        }
        block = blocks_by_key.get(block_key)
        citations = _mapping_list(_field_value(block or {}, "citations"))

        for citation in citations:
            citation_segment_key = _stable_key(_field_value(citation, "segmentKey", "segment_key"))
            if citation_segment_key not in source_segment_keys:
                continue
            ref = _ref_from_citation(
                citation,
                question_key=question_key,
                sort_no=len(refs) + 1,
                segment=segments_by_key.get(citation_segment_key),
            )
            if ref is None:
                continue
            identity = (
                question_key,
                str(ref.get("segmentId") or ref.get("segmentKey") or ref.get("resourceId")),
                _locator_tuple(ref),
            )
            if identity in seen:
                continue
            seen.add(identity)
            refs.append(ref)

        if any(ref["questionKey"] == question_key for ref in refs):
            continue
        for segment_key in sorted(source_segment_keys):
            segment = segments_by_key.get(segment_key)
            ref = _ref_from_segment(segment, question_key=question_key, sort_no=len(refs) + 1) if segment else None
            if ref is not None:
                refs.append(ref)
                break

    return refs


def _question_from_candidate(candidate: QuizSourceCandidate, *, index: int) -> dict[str, Any]:
    correct_text = f"{candidate.knowledge_point_name}：{candidate.description}"
    options = [
        correct_text,
        f"{candidate.knowledge_point_name} 与当前讲义块没有直接关系。",
        "只需要记住名称，不需要理解条件或例子。",
        "当前材料没有提供可追溯依据。",
    ]
    return {
        "questionKey": f"q{index}-{_slug(candidate.knowledge_point_key)}",
        "questionType": "single_choice",
        "stemMd": f"关于“{candidate.block_title}”中的“{candidate.knowledge_point_name}”，哪项说法最符合当前材料？",
        "options": options,
        "correctAnswer": "A",
        "explanationMd": f"答案依据讲义块“{candidate.block_title}”及其来源片段，可回溯到当前课程材料。",
        "difficultyLevel": candidate.difficulty_level,
        "knowledgePointKey": candidate.knowledge_point_key,
        "knowledgePointName": candidate.knowledge_point_name,
        "sourceBlockKey": candidate.block_key,
        "sourceSegmentKeys": list(candidate.source_segment_keys),
    }


def _repeat_to_count(candidates: Sequence[QuizSourceCandidate], target_count: int) -> list[QuizSourceCandidate]:
    if len(candidates) >= target_count:
        return list(candidates[:target_count])
    repeated: list[QuizSourceCandidate] = []
    while len(repeated) < target_count:
        repeated.extend(candidates)
    return repeated[:target_count]


def _answers_by_question_key(answers: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for answer in answers:
        if not isinstance(answer, Mapping):
            continue
        key = _stable_key(_field_value(answer, "questionKey", "question_key"))
        if key:
            result[key] = answer
        question_id = _field_value(answer, "questionId", "question_id")
        if question_id is not None:
            result[str(question_id)] = answer
    return result


def _answer_for_question(
    question: Mapping[str, Any],
    *,
    question_key: str,
    answers_by_key: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    if question_key in answers_by_key:
        return answers_by_key[question_key]
    question_id = _field_value(question, "questionId", "question_id")
    if question_id is not None:
        return answers_by_key.get(str(question_id), {})
    return {}


def _question_key(question: Mapping[str, Any], *, fallback_index: int) -> str:
    key = _stable_key(_field_value(question, "questionKey", "question_key"))
    if key:
        return key
    question_id = _field_value(question, "questionId", "question_id")
    return str(question_id) if question_id is not None else f"q{fallback_index}"


def _finalize_mastery_delta(delta: dict[str, Any]) -> dict[str, Any]:
    value = round(float(delta["delta"]), 4)
    if value > 0:
        status = "improved"
    elif value < 0:
        status = "weakened"
    else:
        status = "unchanged"
    return {**delta, "delta": value, "status": status}


def _recommended_review_action(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    wrong = [item for item in items if not item.get("isCorrect")]
    if wrong:
        first = wrong[0]
        return {
            "type": "revisit_block",
            "targetBlockKey": first.get("sourceBlockKey"),
            "reason": "建议先回看答错题目对应的讲义块，再进入下一轮练习。",
        }
    return {
        "type": "redo_quiz",
        "reason": "本轮全部答对，可继续用同一知识点做间隔复测。",
    }


def _ref_from_citation(
    citation: Mapping[str, Any],
    *,
    question_key: str,
    sort_no: int,
    segment: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    resource_id = _as_int(_field_value(citation, "resourceId", "resource_id"))
    locator = _locator(citation)
    if resource_id is None or not locator:
        return None
    segment_id = _as_int(_field_value(segment or citation, "segmentId", "segment_id"))
    segment_key = _stable_key(_field_value(citation, "segmentKey", "segment_key"))
    ref = {
        "questionKey": question_key,
        "resourceId": resource_id,
        "segmentId": segment_id,
        "segmentKey": segment_key,
        "refType": _ref_type(locator),
        "quoteText": _quote_text(segment, citation),
        "refLabel": clean_text(str(_field_value(citation, "refLabel", "ref_label") or "")),
        "sortNo": sort_no,
        **locator,
    }
    return {key: value for key, value in ref.items() if value not in (None, "", [])}


def _ref_from_segment(segment: Mapping[str, Any], *, question_key: str, sort_no: int) -> dict[str, Any] | None:
    resource_id = _as_int(_field_value(segment, "resourceId", "resource_id"))
    locator = _locator(segment)
    if resource_id is None or not locator:
        return None
    segment_key = _stable_key(_field_value(segment, "segmentKey", "segment_key"))
    ref = {
        "questionKey": question_key,
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


def _block_key(block: Mapping[str, Any], *, fallback_index: int) -> str:
    return _stable_key(_field_value(block, "handoutBlockId", "blockId", "outlineKey", "outline_key")) or f"block-{fallback_index}"


def _source_segment_keys(block: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for item in _field_value(block, "sourceSegmentKeys", "source_segment_keys") or []:
        key = _stable_key(item)
        if key and key not in keys:
            keys.append(key)
    for citation in _mapping_list(_field_value(block, "citations")):
        key = _stable_key(_field_value(citation, "segmentKey", "segment_key"))
        if key and key not in keys:
            keys.append(key)
    return keys


def _difficulty_level(raw: Any, importance: Any) -> DifficultyLevel:
    mapped = _DIFFICULTY_BY_SOURCE.get(str(raw or "").strip())
    if mapped in {"easy", "medium", "hard"}:
        return mapped  # type: ignore[return-value]
    score = _score(importance)
    if score >= 85:
        return "hard"
    if score >= 60:
        return "medium"
    return "easy"


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


def _text_summary(block: Mapping[str, Any]) -> str:
    return clean_text(str(_field_value(block, "summary", "contentMd", "content_md") or ""))[:120]


def _score(value: Any) -> int:
    number = _as_int(value)
    if number is None:
        return 50
    return min(100, max(0, number))


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_answer(value: Any) -> str:
    answer = str(value or "").strip()
    if not answer:
        return ""
    if answer.upper() in _OPTION_LABELS:
        return answer.upper()
    return answer


def _normalize_selected_answer(value: Any, question: Mapping[str, Any]) -> str:
    answer = _normalize_answer(value)
    if answer in _OPTION_LABELS:
        return answer
    normalized_answer = clean_text(answer)
    if not normalized_answer:
        return ""
    for index, option in enumerate(_field_value(question, "options") or ()):
        if index >= len(_OPTION_LABELS):
            break
        if clean_text(_option_text(option)) == normalized_answer:
            return _OPTION_LABELS[index]
    return ""


def _option_text(option: Any) -> str:
    if isinstance(option, Mapping):
        return str(_field_value(option, "text", "label", "value") or "")
    return str(option or "")


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _field_value(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _stable_key(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "item"
