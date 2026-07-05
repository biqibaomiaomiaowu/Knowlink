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
    CourseResource,
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
    version = _optional_handout_version(session, quiz)
    _validate_quiz_task_ownership(task=task, course=course, quiz=quiz, version=version)
    task_payload = _task_payload(task=task, message=message)
    _validate_quiz_task_scope(quiz=quiz, payload=task_payload)

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

    if not _quiz_task_targets_active_context(session=session, course=course, quiz=quiz, version=version):
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

    block_payloads = _source_block_payloads_for_quiz(session=session, course=course, quiz=quiz, version=version)
    if not block_payloads:
        raise QuizTaskInputError("quiz scope has no ready handout blocks or parsed resource segments for quiz generation")
    segments = _segments_for_quiz(
        session,
        course_id=course.id,
        parse_run_id=quiz.source_parse_run_id,
        source_segment_keys=_source_segment_keys_from_blocks(block_payloads),
    )
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
    version: HandoutVersion | None,
) -> None:
    if task.course_id != course.id or quiz.course_id != course.id:
        raise QuizTaskInputError("quiz task message does not match task/course/quiz ownership")
    if version is not None and version.course_id != course.id:
        raise QuizTaskInputError("quiz task message does not match task/course/quiz ownership")
    if task.task_type != "quiz_generate":
        raise QuizTaskInputError(f"async task is not quiz_generate: {task.task_type}")
    if task.target_type != "quiz" or task.target_id != quiz.id:
        raise QuizTaskInputError("quiz task target does not match quiz")
    if version is None and quiz.scope_type not in {"course", "lesson"}:
        raise QuizTaskInputError("scoped quiz task is missing handout version")
    if version is not None and version.source_parse_run_id != quiz.source_parse_run_id:
        raise QuizTaskInputError("quiz source parse run does not match handout version")
    if task.parse_run_id != quiz.source_parse_run_id:
        raise QuizTaskInputError("quiz task does not match source parse run")


def _validate_quiz_task_scope(*, quiz: Quiz, payload: Mapping[str, Any]) -> None:
    expected = {
        "scopeType": quiz.scope_type or "course",
        "lessonId": quiz.lesson_id,
        "startLessonId": quiz.start_lesson_id,
        "endLessonId": quiz.end_lesson_id,
    }
    actual = {
        "scopeType": str(payload.get("scopeType") or payload.get("scope_type") or "course"),
        "lessonId": _optional_int(payload, "lessonId", "lesson_id"),
        "startLessonId": _optional_int(payload, "startLessonId", "start_lesson_id"),
        "endLessonId": _optional_int(payload, "endLessonId", "end_lesson_id"),
    }
    if actual != expected:
        raise QuizTaskInputError("quiz task payload scope does not match quiz scope")


def _quiz_task_targets_active_context(
    *,
    session: Session,
    course: Course,
    quiz: Quiz,
    version: HandoutVersion | None,
) -> bool:
    if quiz.course_id != course.id or quiz.source_parse_run_id != course.active_parse_run_id:
        return False
    if version is None:
        if quiz.handout_version_id is not None:
            return False
        if quiz.scope_type == "course":
            return True
        return quiz.scope_type == "lesson" and quiz.lesson_id is not None
    if (
        version.course_id != course.id
        or version.source_parse_run_id != quiz.source_parse_run_id
        or quiz.handout_version_id != version.id
    ):
        return False
    if version.scope_type == "course":
        return (
            quiz.scope_type == "course"
            and version.lesson_id is None
            and course.active_handout_version_id == version.id
        )
    if version.scope_type == "lesson":
        latest = _latest_lesson_handout_version(
            session,
            course_id=course.id,
            lesson_id=version.lesson_id,
            parse_run_id=version.source_parse_run_id,
        )
        return (
            quiz.scope_type == "lesson"
            and quiz.lesson_id == version.lesson_id
            and latest is not None
            and latest.id == version.id
        )
    return False


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
        version = _optional_handout_version(session, quiz, raise_on_missing=False)
        if course is not None and _quiz_task_targets_active_context(
            session=session,
            course=course,
            quiz=quiz,
            version=version,
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


def _source_block_payloads_for_quiz(
    *,
    session: Session,
    course: Course,
    quiz: Quiz,
    version: HandoutVersion | None,
) -> list[dict[str, Any]]:
    if version is not None:
        return [_handout_block_payload(block) for block in _ready_handout_blocks(session, version)]
    if quiz.scope_type == "course":
        blocks: list[HandoutBlock] = []
        for lesson_version in _latest_lesson_handout_versions_for_quiz(
            session,
            course_id=course.id,
            parse_run_id=quiz.source_parse_run_id,
        ):
            blocks.extend(_ready_handout_blocks(session, lesson_version))
        if blocks:
            return [_handout_block_payload(block) for block in blocks]
        return _resource_segment_source_blocks(
            session,
            course_id=course.id,
            parse_run_id=quiz.source_parse_run_id,
            scope_type="course",
            lesson_id=None,
        )
    if quiz.scope_type == "lesson":
        return _resource_segment_source_blocks(
            session,
            course_id=course.id,
            parse_run_id=quiz.source_parse_run_id,
            scope_type="lesson",
            lesson_id=quiz.lesson_id,
        )
    return []


def _optional_handout_version(
    session: Session,
    quiz: Quiz,
    *,
    raise_on_missing: bool = True,
) -> HandoutVersion | None:
    if quiz.handout_version_id is None:
        return None
    version = session.get(HandoutVersion, quiz.handout_version_id)
    if version is None and raise_on_missing:
        raise QuizTaskInputError("handout.not_found")
    return version


def _latest_lesson_handout_version(
    session: Session,
    *,
    course_id: int,
    lesson_id: int | None,
    parse_run_id: int | None,
) -> HandoutVersion | None:
    if lesson_id is None:
        return None
    versions = _latest_lesson_handout_versions_for_quiz(
        session,
        course_id=course_id,
        parse_run_id=parse_run_id,
    )
    for version in versions:
        if version.lesson_id == lesson_id:
            return version
    return None


def _latest_lesson_handout_versions_for_quiz(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int | None,
) -> list[HandoutVersion]:
    stmt = select(HandoutVersion).where(
        HandoutVersion.course_id == course_id,
        HandoutVersion.scope_type == "lesson",
        HandoutVersion.lesson_id.is_not(None),
    )
    if parse_run_id is None:
        stmt = stmt.where(HandoutVersion.source_parse_run_id.is_(None))
    else:
        stmt = stmt.where(HandoutVersion.source_parse_run_id == parse_run_id)
    rows = session.scalars(
        stmt.order_by(
            HandoutVersion.lesson_id.asc(),
            HandoutVersion.created_at.desc(),
            HandoutVersion.id.desc(),
        )
    ).all()
    latest_by_lesson: dict[int, HandoutVersion] = {}
    for version in rows:
        if version.lesson_id is None:
            continue
        latest_by_lesson.setdefault(version.lesson_id, version)
    return list(latest_by_lesson.values())


def _segments_for_quiz(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int | None,
    source_segment_keys: list[str],
) -> list[CourseSegment]:
    if parse_run_id is None:
        return []
    segment_ids = [_segment_id_from_source_key(key) for key in source_segment_keys]
    segment_ids = [segment_id for segment_id in segment_ids if segment_id is not None]
    if source_segment_keys and not segment_ids:
        return []
    stmt = select(CourseSegment).where(
        CourseSegment.course_id == course_id,
        CourseSegment.parse_run_id == parse_run_id,
        CourseSegment.is_active.is_(True),
    )
    if segment_ids:
        stmt = stmt.where(CourseSegment.id.in_(segment_ids))
    return list(
        session.scalars(
            stmt.order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
        ).all()
    )


def _resource_segment_source_blocks(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int | None,
    scope_type: str,
    lesson_id: int | None,
) -> list[dict[str, Any]]:
    if parse_run_id is None:
        return []
    rows = _scoped_resource_segments(
        session,
        course_id=course_id,
        parse_run_id=parse_run_id,
        scope_type=scope_type,
        lesson_id=lesson_id,
    )
    return [_resource_segment_source_block(segment, resource) for segment, resource in rows]


def _scoped_resource_segments(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int,
    scope_type: str,
    lesson_id: int | None,
) -> list[tuple[CourseSegment, CourseResource]]:
    stmt = (
        select(CourseSegment, CourseResource)
        .join(CourseResource, CourseResource.id == CourseSegment.resource_id)
        .where(
            CourseSegment.course_id == course_id,
            CourseSegment.parse_run_id == parse_run_id,
            CourseSegment.is_active.is_(True),
            CourseResource.course_id == course_id,
            CourseResource.scope_type == scope_type,
        )
        .order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
    )
    if scope_type == "course":
        stmt = stmt.where(CourseResource.lesson_id.is_(None))
    elif scope_type == "lesson":
        if lesson_id is None:
            return []
        stmt = stmt.where(CourseResource.lesson_id == lesson_id)
    else:
        return []
    return [(segment, resource) for segment, resource in session.execute(stmt).all()]


def _resource_segment_source_block(segment: CourseSegment, resource: CourseResource) -> dict[str, Any]:
    segment_key = _segment_source_key(segment)
    block_key = f"resource-{resource.id}-segment-{segment.id}"
    title = segment.title or resource.original_name or f"Resource segment {segment.id}"
    content = segment.text_content or segment.plain_text or ""
    citation: dict[str, Any] = {
        "resourceId": resource.id,
        "segmentId": segment.id,
        "segmentKey": segment_key,
        "refLabel": resource.original_name or f"Resource {resource.id}",
    }
    if segment.page_no is not None:
        citation["pageNo"] = segment.page_no
    if segment.slide_no is not None:
        citation["slideNo"] = segment.slide_no
    if segment.start_sec is not None:
        citation["startSec"] = int(segment.start_sec)
    if segment.end_sec is not None:
        citation["endSec"] = int(segment.end_sec)
    return {
        "blockId": block_key,
        "outlineKey": block_key,
        "title": title,
        "summary": content[:240],
        "contentMd": content,
        "sourceSegmentKeys": [segment_key],
        "knowledgePoints": [
            {
                "knowledgePointKey": f"{block_key}-main",
                "displayName": title,
            }
        ],
        "citations": [citation],
    }


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


def _source_segment_keys_from_blocks(blocks: list[Mapping[str, Any]]) -> list[str]:
    keys: list[str] = []
    for block in blocks:
        raw_keys = block.get("sourceSegmentKeys") or block.get("source_segment_keys") or []
        for raw_key in raw_keys:
            key = str(raw_key) if raw_key is not None else ""
            if key and key not in keys:
                keys.append(key)
        for citation in block.get("citations") or []:
            if not isinstance(citation, Mapping):
                continue
            raw_key = citation.get("segmentKey") or citation.get("segment_key")
            key = str(raw_key) if raw_key is not None else ""
            if key and key not in keys:
                keys.append(key)
    return keys


def _segment_source_key(segment: CourseSegment) -> str:
    return f"segment-{segment.id}"


def _segment_id_from_source_key(value: str) -> int | None:
    prefix = "segment-"
    if not value.startswith(prefix):
        return None
    raw_id = value[len(prefix) :]
    if not raw_id.isdigit():
        return None
    return int(raw_id)


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


def _optional_int(message: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = message.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            raise QuizTaskInputError(f"Invalid integer field: {key}") from None
    return None
