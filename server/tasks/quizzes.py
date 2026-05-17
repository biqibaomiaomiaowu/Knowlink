from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.ai.quiz_strategy import build_quiz_question_refs, generate_quiz_payload
from server.infra.db.base import utcnow
from server.infra.db.models import (
    AsyncTask,
    Course,
    CourseSegment,
    HandoutBlock,
    HandoutVersion,
    LearningPreference,
    Quiz,
)
from server.infra.db.session import create_session
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


LOGGER = logging.getLogger(__name__)


class QuizTaskInputError(ValueError):
    pass


def run_quiz_generate(
    message: Mapping[str, Any],
    *,
    session_factory: Callable[[], Session] = create_session,
    generate_quiz_func: Callable[..., dict[str, Any]] = generate_quiz_payload,
) -> dict[str, Any]:
    task_id = _required_int(message, "taskId", "task_id")
    course_id = _required_int(message, "courseId", "course_id")
    quiz_id = _required_int(message, "quizId", "quiz_id")

    session = session_factory()
    try:
        result = _run_quiz_generate_with_session(
            session=session,
            task_id=task_id,
            course_id=course_id,
            quiz_id=quiz_id,
            message=message,
            generate_quiz_func=generate_quiz_func,
        )
        LOGGER.info(
            "quiz generation task finished",
            extra={
                "task_id": task_id,
                "task_type": "quiz_generate",
                "course_id": course_id,
                "quiz_id": quiz_id,
                "task_status": result.get("taskStatus") or result.get("status"),
            },
        )
        return result
    except Exception as exc:
        session.rollback()
        LOGGER.exception(
            "quiz generation task failed",
            extra={
                "task_id": task_id,
                "task_type": "quiz_generate",
                "course_id": course_id,
                "quiz_id": quiz_id,
            },
        )
        return _mark_quiz_task_failed(
            session=session,
            task_id=task_id,
            quiz_id=quiz_id,
            error_message=str(exc),
        )
    finally:
        session.close()


def _run_quiz_generate_with_session(
    *,
    session: Session,
    task_id: int,
    course_id: int,
    quiz_id: int,
    message: Mapping[str, Any],
    generate_quiz_func: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    task = _require_model(session, AsyncTask, task_id, "async_task.not_found")
    course = _require_model(session, Course, course_id, "course.not_found")
    quiz = _require_model(session, Quiz, quiz_id, "quiz.not_found")
    version = _require_model(session, HandoutVersion, quiz.handout_version_id, "handout.not_found")
    _validate_quiz_task_ownership(task=task, course=course, quiz=quiz, version=version)
    task_payload = _task_payload(task=task, message=message)

    if task.status in {"succeeded", "failed", "canceled", "skipped"}:
        return _terminal_quiz_task_result(task=task, quiz=quiz)
    if quiz.status == "ready":
        task.status = "succeeded"
        task.progress_pct = 100
        task.result_json = {
            "courseId": course.id,
            "quizId": quiz.id,
            "status": "ready",
            "questionCount": quiz.question_count,
        }
        task.finished_at = task.finished_at or utcnow()
        session.commit()
        return _terminal_quiz_task_result(task=task, quiz=quiz)

    if not _quiz_task_targets_active_course(course=course, quiz=quiz, version=version):
        raise QuizTaskInputError("quiz task does not match the active course parse/handout context")

    now = utcnow()
    task.status = "running"
    task.progress_pct = 50
    task.started_at = task.started_at or now
    task.error_code = None
    task.error_message = None
    quiz.status = "generating"
    course.pipeline_stage = "quiz"
    course.pipeline_status = "running"
    course.updated_at = now
    session.commit()

    blocks = _ready_handout_blocks(session, version)
    if not blocks:
        raise QuizTaskInputError("active handout version has no ready blocks for quiz generation")
    block_payloads = [_handout_block_payload(block) for block in blocks]
    segments = _segments_for_quiz(session, course_id=course.id, parse_run_id=version.source_parse_run_id)
    segment_payloads = [_segment_payload(segment) for segment in segments]
    question_count_level = _question_count_level(task_payload)

    payload = generate_quiz_func(
        block_payloads,
        segments=segment_payloads,
        course_context=_course_context_payload(course),
        preferences=_learning_preference_payload(session, course),
        question_count_level=question_count_level,
    )
    refs = build_quiz_question_refs(
        payload,
        handout_blocks=block_payloads,
        segments=segment_payloads,
    )
    saved = SqlAlchemyRuntimeRepository(session, user_id=course.user_id).save_quiz_generation_result(
        quiz.id,
        payload,
        refs,
    )
    if saved is None:
        raise QuizTaskInputError("quiz generation result was rejected by repository")

    finished_at = utcnow()
    task.status = "succeeded"
    task.progress_pct = 100
    task.result_json = {
        "courseId": course.id,
        "quizId": quiz.id,
        "status": "ready",
        "questionCount": saved["questionCount"],
    }
    task.finished_at = finished_at
    course.pipeline_stage = "quiz"
    course.pipeline_status = "succeeded"
    course.last_error = None
    course.updated_at = finished_at
    session.commit()

    return {
        "taskId": task.id,
        "courseId": course.id,
        "quizId": quiz.id,
        "status": "ready",
        "questionCount": saved["questionCount"],
    }


def _validate_quiz_task_ownership(
    *,
    task: AsyncTask,
    course: Course,
    quiz: Quiz,
    version: HandoutVersion,
) -> None:
    if task.course_id != course.id or quiz.course_id != course.id or version.course_id != course.id:
        raise QuizTaskInputError("quiz task message does not match task/course/quiz ownership")
    if task.task_type != "quiz_generate":
        raise QuizTaskInputError(f"async task is not quiz_generate: {task.task_type}")
    if task.target_type != "quiz" or task.target_id != quiz.id:
        raise QuizTaskInputError("quiz task target does not match quiz")
    if version.source_parse_run_id != quiz.source_parse_run_id:
        raise QuizTaskInputError("quiz source parse run does not match handout version")
    if task.parse_run_id != version.source_parse_run_id:
        raise QuizTaskInputError("quiz task does not match source parse run")


def _quiz_task_targets_active_course(
    *,
    course: Course,
    quiz: Quiz,
    version: HandoutVersion,
) -> bool:
    return (
        course.active_handout_version_id == version.id
        and course.active_parse_run_id == version.source_parse_run_id
        and quiz.handout_version_id == version.id
        and quiz.course_id == course.id
    )


def _terminal_quiz_task_result(*, task: AsyncTask, quiz: Quiz) -> dict[str, Any]:
    return {
        "taskId": task.id,
        "courseId": quiz.course_id,
        "quizId": quiz.id,
        "status": quiz.status if task.status == "succeeded" else task.status,
        "taskStatus": task.status,
        "questionCount": quiz.question_count,
    }


def _mark_quiz_task_failed(
    *,
    session: Session,
    task_id: int,
    quiz_id: int,
    error_message: str,
) -> dict[str, Any]:
    task = session.get(AsyncTask, task_id)
    quiz = session.get(Quiz, quiz_id)
    finished_at = utcnow()
    if task is not None:
        task.status = "failed"
        task.progress_pct = 100
        task.error_code = "quiz.generate_failed"
        task.error_message = error_message
        task.finished_at = finished_at
    if quiz is not None:
        quiz.status = "failed"
        quiz.error_code = "quiz.generate_failed"
        quiz.error_message = error_message
        course = session.get(Course, quiz.course_id)
        version = session.get(HandoutVersion, quiz.handout_version_id)
        if (
            course is not None
            and version is not None
            and _quiz_task_targets_active_course(course=course, quiz=quiz, version=version)
        ):
            course.pipeline_stage = "quiz"
            course.pipeline_status = "failed"
            course.last_error = error_message
            course.updated_at = finished_at
    session.commit()
    return {
        "taskId": task_id,
        "quizId": quiz_id,
        "status": "failed",
        "errorMessage": error_message,
    }


def _ready_handout_blocks(session: Session, version: HandoutVersion) -> list[HandoutBlock]:
    return list(
        session.scalars(
            select(HandoutBlock)
            .where(
                HandoutBlock.handout_version_id == version.id,
                HandoutBlock.status == "ready",
            )
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
    )


def _segments_for_quiz(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int | None,
) -> list[CourseSegment]:
    if parse_run_id is None:
        return []
    return list(
        session.scalars(
            select(CourseSegment)
            .where(
                CourseSegment.course_id == course_id,
                CourseSegment.parse_run_id == parse_run_id,
                CourseSegment.is_active.is_(True),
            )
            .order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
        ).all()
    )


def _handout_block_payload(block: HandoutBlock) -> dict[str, Any]:
    return {
        "blockId": block.id,
        "outlineKey": block.outline_key,
        "title": block.title,
        "summary": block.summary,
        "contentMd": block.content_md,
        "sourceSegmentKeys": list(block.source_segment_keys_json or []),
        "knowledgePoints": list(block.knowledge_points_json or []),
        "citations": list(block.citations_json or []),
    }


def _segment_payload(segment: CourseSegment) -> dict[str, Any]:
    return {
        "segmentId": segment.id,
        "segmentKey": f"segment-{segment.id}",
        "courseId": segment.course_id,
        "resourceId": segment.resource_id,
        "parseRunId": segment.parse_run_id,
        "segmentType": segment.segment_type,
        "title": segment.title,
        "textContent": segment.text_content,
        "plainText": segment.plain_text,
        "pageNo": segment.page_no,
        "slideNo": segment.slide_no,
        "anchorKey": f"segment-{segment.id}" if segment.segment_type == "docx_block_text" else None,
        "startSec": int(segment.start_sec) if segment.start_sec is not None else None,
        "endSec": int(segment.end_sec) if segment.end_sec is not None else None,
        "bboxJson": segment.bbox_json,
    }


def _task_payload(*, task: AsyncTask, message: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(task.payload_json, Mapping):
        payload.update(task.payload_json)
    payload.update({key: value for key, value in message.items() if value is not None})
    return payload


def _question_count_level(payload: Mapping[str, Any]) -> str:
    value = payload.get("questionCountLevel") or payload.get("question_count_level") or "medium"
    if not isinstance(value, str):
        raise QuizTaskInputError("questionCountLevel must be a string")
    normalized = value.strip().lower()
    if normalized not in {"small", "medium", "large"}:
        raise QuizTaskInputError(f"invalid questionCountLevel: {value}")
    return normalized


def _course_context_payload(course: Course) -> dict[str, Any]:
    return {
        "courseId": course.id,
        "title": course.title,
        "goalText": course.goal_text,
        "preferredStyle": course.preferred_style,
        "examAt": course.exam_at.isoformat() if course.exam_at is not None else None,
        "summary": course.summary,
    }


def _learning_preference_payload(session: Session, course: Course) -> dict[str, Any]:
    preference = session.scalar(
        select(LearningPreference).where(
            LearningPreference.user_id == course.user_id,
            LearningPreference.course_id == course.id,
        )
    )
    if preference is None:
        return {}
    return {
        "goalType": preference.goal_type,
        "selfLevel": preference.self_level,
        "timeBudgetMinutes": preference.time_budget_minutes,
        "examAt": preference.exam_at.isoformat() if preference.exam_at is not None else None,
        "preferredStyle": preference.preferred_style,
        "exampleDensity": preference.example_density,
        "formulaDetailLevel": preference.formula_detail_level,
        "languageStyle": preference.language_style,
        "focusKnowledge": list(preference.focus_knowledge_json or []),
    }


def _require_model(session: Session, model: type[Any], item_id: int, error_code: str) -> Any:
    row = session.get(model, item_id)
    if row is None:
        raise QuizTaskInputError(error_code)
    return row


def _required_int(message: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = message.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            break
    raise QuizTaskInputError(f"Missing required integer field: {'/'.join(keys)}")
