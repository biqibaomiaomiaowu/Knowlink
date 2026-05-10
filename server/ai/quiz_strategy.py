from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence

from server.ai.deepseek import DeepSeekJsonChatClient, get_configured_deepseek_chat_config
from server.parsers.base import clean_text


QuizType = Literal["block_check", "chapter_review", "exam_drill"]
QuestionType = Literal["single_choice"]
DifficultyLevel = Literal["easy", "medium", "hard"]
QuestionCountLevel = Literal["small", "medium", "large"]

_OPTION_LABELS = ("A", "B", "C", "D")
QUESTION_COUNT_LEVEL_RANGES: dict[QuestionCountLevel, tuple[int, int]] = {
    "small": (1, 3),
    "medium": (3, 5),
    "large": (5, 10),
}
_DEFAULT_QUIZ_TIMEOUT_SEC = 60.0
_QUIZ_SYSTEM_PROMPT = """你是 KnowLink 的实时测验出题器。只返回 JSON，不要返回 Markdown 代码块或解释。
JSON 格式固定为：
{"quizType":"chapter_review","questions":[{"questionKey":"q1-kp-limit","questionType":"single_choice","stemMd":"...","options":["A. ...","B. ...","C. ...","D. ..."],"correctAnswer":"A","explanationMd":"...","difficultyLevel":"easy|medium|hard","knowledgePointKey":"...","knowledgePointName":"...","sourceBlockKey":"...","sourceSegmentKeys":["..."]}]}
规则：
1. 只能基于输入 JSON 中的 course、learningPreferences、readyHandoutBlocks 和 activeParseRunSegments 出题，不得使用课程外知识补充。
2. questions 数量必须落在输入 questionCountRange 内；不要返回固定题数解释。
3. 题型只能是 single_choice；每题必须且只能有 4 个选项，correctAnswer 只能是 A/B/C/D。
4. sourceBlockKey 必须来自 readyHandoutBlocks[].blockKey。
5. sourceSegmentKeys 必须全部来自该 block 的 sourceSegmentKeys，不能为空；不得编造 pageNo、slideNo、anchorKey、startSec 或 endSec。
6. stemMd、options、explanationMd 使用中文，围绕当前课程材料考查理解，不要生成与上下文无关的常识题。
7. questionKey 在本次 JSON 内必须唯一。
"""
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


class QuizGenerationClient(Protocol):
    def generate_quiz(self, prompt_context: Mapping[str, Any]) -> dict[str, Any]:
        """Return a raw model payload for quiz generation."""


class DeepSeekQuizGenerationClient:
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
            timeout_sec=timeout_sec if timeout_sec is not None else _DEFAULT_QUIZ_TIMEOUT_SEC,
            label="deepseek quiz",
        )

    def generate_quiz(self, prompt_context: Mapping[str, Any]) -> dict[str, Any]:
        return self._client.complete_json(
            system_prompt=_QUIZ_SYSTEM_PROMPT,
            user_prompt=_build_quiz_prompt(prompt_context),
            max_tokens=8192,
        )


def get_configured_quiz_generation_client() -> QuizGenerationClient | None:
    config = get_configured_deepseek_chat_config()
    if config is None:
        return None
    return DeepSeekQuizGenerationClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        timeout_sec=_env_float("KNOWLINK_DEEPSEEK_QUIZ_TIMEOUT_SEC", _DEFAULT_QUIZ_TIMEOUT_SEC),
    )


def generate_quiz_payload(
    handout_blocks: Sequence[Mapping[str, Any]],
    *,
    segments: Sequence[Mapping[str, Any]] = (),
    course_context: Mapping[str, Any] | None = None,
    preferences: Mapping[str, Any] | None = None,
    quiz_type: QuizType = "chapter_review",
    question_count_level: QuestionCountLevel = "medium",
    client: QuizGenerationClient | None = None,
) -> dict[str, Any]:
    """Generate a quiz with DeepSeek and validate it against current course context."""

    candidates = build_quiz_source_candidates(handout_blocks)
    if not candidates:
        raise ValueError("at least one cited handout block or knowledge point is required")

    generation_client = client if client is not None else get_configured_quiz_generation_client()
    if generation_client is None:
        raise RuntimeError("deepseek quiz generation is not configured")

    context = build_quiz_generation_context(
        handout_blocks,
        segments=segments,
        course_context=course_context,
        preferences=preferences,
        quiz_type=quiz_type,
        question_count_level=question_count_level,
    )
    model_payload = generation_client.generate_quiz(context)
    return normalize_quiz_generation_payload(
        model_payload,
        handout_blocks=handout_blocks,
        segments=segments,
        quiz_type=quiz_type,
        question_count_level=question_count_level,
    )


def build_quiz_generation_context(
    handout_blocks: Sequence[Mapping[str, Any]],
    *,
    segments: Sequence[Mapping[str, Any]] = (),
    course_context: Mapping[str, Any] | None = None,
    preferences: Mapping[str, Any] | None = None,
    quiz_type: QuizType = "chapter_review",
    question_count_level: QuestionCountLevel = "medium",
) -> dict[str, Any]:
    min_count, max_count = _question_count_range(question_count_level)
    return {
        "quizType": quiz_type,
        "questionCountLevel": question_count_level,
        "questionCountRange": {"min": min_count, "max": max_count},
        "course": dict(course_context or {}),
        "learningPreferences": dict(preferences or {}),
        "readyHandoutBlocks": [
            _prompt_block_payload(block, index=index) for index, block in enumerate(handout_blocks, start=1) if isinstance(block, Mapping)
        ],
        "activeParseRunSegments": [
            _prompt_segment_payload(segment) for segment in segments if isinstance(segment, Mapping)
        ],
    }


def normalize_quiz_generation_payload(
    payload: Mapping[str, Any],
    *,
    handout_blocks: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]] = (),
    quiz_type: QuizType = "chapter_review",
    question_count_level: QuestionCountLevel = "medium",
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("quiz generation payload must be an object")
    _reject_extra_fields(payload, {"quizType", "questions"}, "quiz")

    if payload.get("quizType") != quiz_type:
        raise ValueError("quizType does not match the requested quiz type")

    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise ValueError("quiz questions must be a list")
    min_count, max_count = _question_count_range(question_count_level)
    if len(questions) < min_count or len(questions) > max_count:
        raise ValueError(f"quiz question count must be in range {min_count}-{max_count}")

    source_context = _source_context(handout_blocks, segments)
    question_keys: set[str] = set()
    normalized_questions: list[dict[str, Any]] = []
    for index, raw_question in enumerate(questions, start=1):
        if not isinstance(raw_question, Mapping):
            raise ValueError("quiz question must be an object")
        normalized_question = _normalize_model_question(
            raw_question,
            index=index,
            source_context=source_context,
        )
        question_key = normalized_question["questionKey"]
        if question_key in question_keys:
            raise ValueError(f"duplicate quiz questionKey: {question_key}")
        question_keys.add(question_key)
        normalized_questions.append(normalized_question)

    return {"quizType": quiz_type, "questions": normalized_questions}


def _build_quiz_prompt(prompt_context: Mapping[str, Any]) -> str:
    return (
        "请严格基于以下 JSON 上下文生成测验 JSON。"
        "除最终 JSON 外不要输出任何解释。\n\n"
        f"{json.dumps(prompt_context, ensure_ascii=False, separators=(',', ':'))}"
    )


def _question_count_range(question_count_level: str) -> tuple[int, int]:
    if question_count_level not in QUESTION_COUNT_LEVEL_RANGES:
        raise ValueError(f"invalid questionCountLevel: {question_count_level}")
    return QUESTION_COUNT_LEVEL_RANGES[question_count_level]  # type: ignore[index]


def _prompt_block_payload(block: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    block_key = _block_key(block, fallback_index=index)
    return {
        "blockKey": block_key,
        "title": clean_text(str(_field_value(block, "title") or f"讲义块 {index}")),
        "summary": _truncate_text(_field_value(block, "summary"), 240),
        "contentMd": _truncate_text(_field_value(block, "contentMd", "content_md"), 1200),
        "sourceSegmentKeys": _source_segment_keys(block),
        "knowledgePoints": [
            {
                "knowledgePointKey": _stable_key(
                    _field_value(item, "knowledgePointKey", "knowledge_point_key")
                ),
                "displayName": clean_text(
                    str(_field_value(item, "displayName", "display_name", "canonicalName", "canonical_name") or "")
                ),
                "description": _truncate_text(_field_value(item, "description"), 240),
                "difficultyLevel": _field_value(item, "difficultyLevel", "difficulty_level"),
                "importanceScore": _field_value(item, "importanceScore", "importance_score"),
            }
            for item in _mapping_list(_field_value(block, "knowledgePoints", "knowledge_points"))
        ],
        "citations": [
            {
                key: value
                for key, value in {
                    "resourceId": _field_value(citation, "resourceId", "resource_id"),
                    "segmentKey": _stable_key(_field_value(citation, "segmentKey", "segment_key")),
                    "refLabel": _field_value(citation, "refLabel", "ref_label"),
                    **_locator(citation),
                }.items()
                if value not in (None, "", [])
            }
            for citation in _mapping_list(_field_value(block, "citations"))
        ],
    }


def _prompt_segment_payload(segment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "segmentId": _field_value(segment, "segmentId", "segment_id"),
            "segmentKey": _stable_key(_field_value(segment, "segmentKey", "segment_key")),
            "resourceId": _field_value(segment, "resourceId", "resource_id"),
            "segmentType": _field_value(segment, "segmentType", "segment_type"),
            "title": _truncate_text(_field_value(segment, "title"), 120),
            "textContent": _truncate_text(
                _field_value(segment, "textContent", "text_content", "plainText", "plain_text"),
                600,
            ),
            **_locator(segment),
        }.items()
        if value not in (None, "", [])
    }


def _source_context(
    handout_blocks: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    blocks_by_key: dict[str, Mapping[str, Any]] = {}
    segment_keys_by_block: dict[str, set[str]] = {}
    knowledge_point_keys_by_block: dict[str, set[str]] = {}
    global_segment_keys = {
        _stable_key(_field_value(segment, "segmentKey", "segment_key"))
        for segment in segments
        if isinstance(segment, Mapping) and _stable_key(_field_value(segment, "segmentKey", "segment_key"))
    }

    for block_index, block in enumerate(handout_blocks, start=1):
        if not isinstance(block, Mapping):
            continue
        block_key = _block_key(block, fallback_index=block_index)
        blocks_by_key[block_key] = block
        block_segment_keys = set(_source_segment_keys(block))
        global_segment_keys.update(block_segment_keys)
        segment_keys_by_block[block_key] = block_segment_keys
        kp_keys = {
            _stable_key(_field_value(item, "knowledgePointKey", "knowledge_point_key"))
            for item in _mapping_list(_field_value(block, "knowledgePoints", "knowledge_points"))
            if _stable_key(_field_value(item, "knowledgePointKey", "knowledge_point_key"))
        }
        if not kp_keys:
            kp_keys.add(f"{block_key}-main")
        knowledge_point_keys_by_block[block_key] = kp_keys

    return {
        "blocksByKey": blocks_by_key,
        "segmentKeysByBlock": segment_keys_by_block,
        "globalSegmentKeys": global_segment_keys,
        "knowledgePointKeysByBlock": knowledge_point_keys_by_block,
    }


_ALLOWED_QUESTION_FIELDS = {
    "questionKey",
    "questionType",
    "stemMd",
    "options",
    "correctAnswer",
    "explanationMd",
    "difficultyLevel",
    "knowledgePointKey",
    "knowledgePointName",
    "sourceBlockKey",
    "sourceSegmentKeys",
}


def _normalize_model_question(
    question: Mapping[str, Any],
    *,
    index: int,
    source_context: Mapping[str, Any],
) -> dict[str, Any]:
    _reject_extra_fields(question, _ALLOWED_QUESTION_FIELDS, f"quiz.questions[{index}]")
    missing = [field for field in _ALLOWED_QUESTION_FIELDS if field not in question]
    if missing:
        raise ValueError(f"quiz question missing fields: {', '.join(sorted(missing))}")

    question_key = _required_text(question["questionKey"], f"quiz.questions[{index}].questionKey")
    question_type = _required_text(question["questionType"], f"quiz.questions[{index}].questionType")
    if question_type != "single_choice":
        raise ValueError("quiz questionType must be single_choice")

    options = question["options"]
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("quiz options must contain exactly 4 items")
    normalized_options = [_required_text(option, f"quiz.questions[{index}].options") for option in options]

    correct_answer = _normalize_answer(question["correctAnswer"])
    if correct_answer not in _OPTION_LABELS:
        raise ValueError("quiz correctAnswer must be A/B/C/D")

    difficulty_level = _required_text(question["difficultyLevel"], f"quiz.questions[{index}].difficultyLevel")
    if difficulty_level not in {"easy", "medium", "hard"}:
        raise ValueError("quiz difficultyLevel must be easy/medium/hard")

    source_block_key = _required_text(question["sourceBlockKey"], f"quiz.questions[{index}].sourceBlockKey")
    blocks_by_key = source_context["blocksByKey"]
    if source_block_key not in blocks_by_key:
        raise ValueError(f"quiz question references unknown sourceBlockKey: {source_block_key}")

    source_segment_keys = _source_keys(question["sourceSegmentKeys"], f"quiz.questions[{index}].sourceSegmentKeys")
    global_segment_keys: set[str] = source_context["globalSegmentKeys"]
    unknown_segments = sorted(key for key in source_segment_keys if key not in global_segment_keys)
    if unknown_segments:
        raise ValueError(f"quiz question references unknown sourceSegmentKeys: {', '.join(unknown_segments)}")
    block_segment_keys: set[str] = source_context["segmentKeysByBlock"].get(source_block_key, set())
    if not block_segment_keys:
        raise ValueError(f"quiz question references a sourceBlockKey without source segments: {source_block_key}")
    out_of_block = sorted(key for key in source_segment_keys if key not in block_segment_keys)
    if out_of_block:
        raise ValueError(f"quiz question references segments outside sourceBlockKey: {', '.join(out_of_block)}")

    knowledge_point_key = _required_text(
        question["knowledgePointKey"],
        f"quiz.questions[{index}].knowledgePointKey",
    )
    block_kp_keys: set[str] = source_context["knowledgePointKeysByBlock"].get(source_block_key, set())
    if block_kp_keys and knowledge_point_key not in block_kp_keys:
        raise ValueError(f"quiz question references unknown knowledgePointKey: {knowledge_point_key}")

    return {
        "questionKey": question_key,
        "questionType": "single_choice",
        "stemMd": _required_text(question["stemMd"], f"quiz.questions[{index}].stemMd"),
        "options": normalized_options,
        "correctAnswer": correct_answer,
        "explanationMd": _required_text(question["explanationMd"], f"quiz.questions[{index}].explanationMd"),
        "difficultyLevel": difficulty_level,
        "knowledgePointKey": knowledge_point_key,
        "knowledgePointName": _required_text(
            question["knowledgePointName"],
            f"quiz.questions[{index}].knowledgePointName",
        ),
        "sourceBlockKey": source_block_key,
        "sourceSegmentKeys": source_segment_keys,
    }


def _reject_extra_fields(mapping: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = sorted(set(mapping) - allowed)
    if extra:
        raise ValueError(f"{label} has unsupported fields: {', '.join(extra)}")


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    text = clean_text(value)
    if not text:
        raise ValueError(f"{label} must be a non-empty string")
    return text


def _source_keys(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{label} must contain only strings")
        key = _stable_key(item)
        if not key:
            raise ValueError(f"{label} must not contain empty keys")
        if key in result:
            raise ValueError(f"{label} contains duplicate key: {key}")
        result.append(key)
    return result


def _truncate_text(value: Any, limit: int) -> str:
    text = clean_text(str(value or ""))
    return text[:limit]


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


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
