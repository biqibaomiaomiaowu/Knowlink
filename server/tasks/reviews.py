from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.ai.review_strategy import build_review_task_refs, generate_review_tasks
from server.infra.db.base import utcnow
from server.infra.db.models import (
    AsyncTask,
    Course,
    CourseResource,
    CourseSegment,
    HandoutBlock,
    HandoutVersion,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    ReviewTaskRun,
)
from server.infra.db.session import create_session
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


LOGGER = logging.getLogger(__name__)


class ReviewTaskInputError(ValueError):
    pass


def run_review_refresh(
    message: Mapping[str, Any],
    *,
    session_factory: Callable[[], Session] = create_session,
    generate_review_tasks_func: Callable[..., dict[str, Any]] = generate_review_tasks,
) -> dict[str, Any]:
    task_id = _required_int(message, "taskId", "task_id")
    course_id = _required_int(message, "courseId", "course_id")
    review_task_run_id = _required_int(message, "reviewTaskRunId", "review_task_run_id")

    session = session_factory()
    try:
        result = _run_review_refresh_with_session(
            session=session,
            task_id=task_id,
            course_id=course_id,
            review_task_run_id=review_task_run_id,
            generate_review_tasks_func=generate_review_tasks_func,
        )
        LOGGER.info(
            "review refresh task finished",
            extra={
                "task_id": task_id,
                "task_type": "review_refresh",
                "course_id": course_id,
                "review_task_run_id": review_task_run_id,
                "task_status": result.get("taskStatus") or result.get("status"),
            },
        )
        return result
    except Exception as exc:
        session.rollback()
        LOGGER.exception(
            "review refresh task failed",
            extra={
                "task_id": task_id,
                "task_type": "review_refresh",
                "course_id": course_id,
                "review_task_run_id": review_task_run_id,
            },
        )
        return _mark_review_refresh_failed(
            session=session,
            task_id=task_id,
            review_task_run_id=review_task_run_id,
            error_message=str(exc),
        )
    finally:
        session.close()


def _run_review_refresh_with_session(
    *,
    session: Session,
    task_id: int,
    course_id: int,
    review_task_run_id: int,
    generate_review_tasks_func: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    task = _require_model(session, AsyncTask, task_id, "async_task.not_found")
    course = _require_model(session, Course, course_id, "course.not_found")
    run = _require_model(session, ReviewTaskRun, review_task_run_id, "review.run_not_found")
    _validate_review_refresh_task_ownership(task=task, course=course, run=run)

    if task.status in {"succeeded", "failed", "canceled", "skipped"}:
        return _terminal_review_task_result(task=task, run=run)

    attempt = _source_attempt(session, run)
    if attempt is None:
        raise ReviewTaskInputError("review refresh requires a quiz attempt")
    quiz = _require_model(session, Quiz, attempt.quiz_id, "quiz.not_found")
    version = _optional_handout_version(session, quiz)
    if task.parse_run_id != quiz.source_parse_run_id:
        raise ReviewTaskInputError("review task does not match source parse run")
    if version is not None and task.parse_run_id != version.source_parse_run_id:
        raise ReviewTaskInputError("review task does not match source parse run")
    if not _review_refresh_targets_current_context(session=session, course=course, quiz=quiz, version=version):
        raise ReviewTaskInputError("review refresh does not match the active course parse/handout context")

    now = utcnow()
    task.status = "running"
    task.progress_pct = 50
    task.started_at = task.started_at or now
    task.error_code = None
    task.error_message = None
    run.status = "running"
    session.commit()

    quiz_payload = _quiz_payload(session, quiz)
    result_json = dict(attempt.result_json or {})
    mastery_updates = result_json.get("masteryUpdates")
    blocks = _source_blocks_for_review(session=session, course=course, quiz=quiz, version=version)
    if not blocks:
        raise ReviewTaskInputError("review refresh has no ready source blocks")
    block_payloads = blocks
    segments = _segments_for_review(session, course_id=course.id, parse_run_id=quiz.source_parse_run_id)
    segment_payloads = [_segment_payload(segment) for segment in segments]

    review_payload = generate_review_tasks_func(
        result_json,
        quiz_payload=quiz_payload,
        handout_blocks=block_payloads,
        mastery_updates=mastery_updates if isinstance(mastery_updates, list) else None,
    )
    refs = build_review_task_refs(
        review_payload,
        handout_blocks=block_payloads,
        segments=segment_payloads,
    )
    saved = SqlAlchemyRuntimeRepository(session, user_id=course.user_id).save_review_task_run_result(
        run.id,
        review_payload,
        refs,
    )
    if saved is None:
        raise ReviewTaskInputError("review task result was rejected by repository")

    if saved.get("status") == "skipped":
        finished_at = utcnow()
        task.status = "skipped"
        task.progress_pct = 100
        task.result_json = {
            "courseId": course.id,
            "reviewTaskRunId": run.id,
            "status": "skipped",
            "generatedCount": saved["generatedCount"],
        }
        task.finished_at = finished_at
        session.commit()
        return {
            "taskId": task.id,
            "courseId": course.id,
            "reviewTaskRunId": run.id,
            "status": "skipped",
            "generatedCount": saved["generatedCount"],
        }

    finished_at = utcnow()
    task.status = "succeeded"
    task.progress_pct = 100
    task.result_json = {
        "courseId": course.id,
        "reviewTaskRunId": run.id,
        "status": "ready",
        "generatedCount": saved["generatedCount"],
    }
    task.finished_at = finished_at
    session.commit()

    return {
        "taskId": task.id,
        "courseId": course.id,
        "reviewTaskRunId": run.id,
        "status": "ready",
        "generatedCount": saved["generatedCount"],
    }


def _validate_review_refresh_task_ownership(
    *,
    task: AsyncTask,
    course: Course,
    run: ReviewTaskRun,
) -> None:
    if task.course_id != course.id or run.course_id != course.id:
        raise ReviewTaskInputError("review task message does not match task/course/run ownership")
    if task.task_type != "review_refresh":
        raise ReviewTaskInputError(f"async task is not review_refresh: {task.task_type}")
    if task.target_type != "review_task_run" or task.target_id != run.id:
        raise ReviewTaskInputError("review task target does not match review run")
    if task.parse_run_id is None:
        raise ReviewTaskInputError("review task missing source parse run")


def _optional_handout_version(session: Session, quiz: Quiz) -> HandoutVersion | None:
    if quiz.handout_version_id is None:
        return None
    return _require_model(session, HandoutVersion, quiz.handout_version_id, "handout.not_found")


def _review_refresh_targets_current_context(
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
            return course.active_handout_version_id is None
        if quiz.scope_type == "lesson":
            latest = _latest_lesson_handout_version(
                session,
                course_id=course.id,
                lesson_id=quiz.lesson_id,
                parse_run_id=quiz.source_parse_run_id,
            )
            return quiz.lesson_id is not None and latest is None
        return False
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


def _source_attempt(session: Session, run: ReviewTaskRun) -> QuizAttempt | None:
    if run.source_quiz_attempt_id is not None:
        return session.get(QuizAttempt, run.source_quiz_attempt_id)
    return session.scalars(
        select(QuizAttempt)
        .where(
            QuizAttempt.user_id == run.user_id,
            QuizAttempt.course_id == run.course_id,
        )
        .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
    ).first()


def _quiz_payload(session: Session, quiz: Quiz) -> dict[str, Any]:
    questions = session.scalars(
        select(QuizQuestion)
        .where(QuizQuestion.quiz_id == quiz.id)
        .order_by(QuizQuestion.sort_no.asc(), QuizQuestion.id.asc())
    ).all()
    return {
        "quizType": quiz.quiz_type,
        "questions": [
            {
                "questionId": question.id,
                "questionKey": question.question_key,
                "questionType": question.question_type,
                "stemMd": question.stem_md,
                "options": list(question.options_json or []),
                "correctAnswer": question.correct_answer,
                "explanationMd": question.explanation_md,
                "difficultyLevel": question.difficulty_level,
                "knowledgePointKey": question.knowledge_point_key,
                "knowledgePointName": question.knowledge_point_name,
                "sourceBlockKey": question.source_block_key,
                "sourceSegmentKeys": list(question.source_segment_keys_json or []),
            }
            for question in questions
        ],
    }


def _ready_handout_blocks(session: Session, version: HandoutVersion) -> list[HandoutBlock]:
    return list(
        session.scalars(
            select(HandoutBlock)
            .where(HandoutBlock.handout_version_id == version.id, HandoutBlock.status == "ready")
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
    )


def _source_blocks_for_review(
    *,
    session: Session,
    course: Course,
    quiz: Quiz,
    version: HandoutVersion | None,
) -> list[dict[str, Any]]:
    if version is not None:
        return [_handout_block_payload(block) for block in _ready_handout_blocks(session, version)]
    if quiz.scope_type == "course":
        blocks: list[dict[str, Any]] = []
        for lesson_version in _latest_lesson_handout_versions_for_review(
            session,
            course_id=course.id,
            parse_run_id=quiz.source_parse_run_id,
        ):
            blocks.extend(_handout_block_payload(block) for block in _ready_handout_blocks(session, lesson_version))
        if blocks:
            return blocks
        return _resource_segment_source_blocks(
            session,
            course_id=course.id,
            parse_run_id=quiz.source_parse_run_id,
            scope_type="course",
            lesson_id=None,
        )
    if quiz.scope_type == "lesson":
        latest = _latest_lesson_handout_version(
            session,
            course_id=course.id,
            lesson_id=quiz.lesson_id,
            parse_run_id=quiz.source_parse_run_id,
        )
        if latest is not None:
            return [_handout_block_payload(block) for block in _ready_handout_blocks(session, latest)]
        return _resource_segment_source_blocks(
            session,
            course_id=course.id,
            parse_run_id=quiz.source_parse_run_id,
            scope_type="lesson",
            lesson_id=quiz.lesson_id,
        )
    return []


def _latest_lesson_handout_version(
    session: Session,
    *,
    course_id: int,
    lesson_id: int | None,
    parse_run_id: int | None,
) -> HandoutVersion | None:
    if lesson_id is None:
        return None
    versions = _latest_lesson_handout_versions_for_review(
        session,
        course_id=course_id,
        parse_run_id=parse_run_id,
    )
    for version in versions:
        if version.lesson_id == lesson_id:
            return version
    return None


def _latest_lesson_handout_versions_for_review(
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
    segment_key = f"segment-{segment.id}"
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


def _segments_for_review(session: Session, *, course_id: int, parse_run_id: int | None) -> list[CourseSegment]:
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


def _terminal_review_task_result(*, task: AsyncTask, run: ReviewTaskRun) -> dict[str, Any]:
    return {
        "taskId": task.id,
        "courseId": run.course_id,
        "reviewTaskRunId": run.id,
        "status": run.status if task.status == "succeeded" else task.status,
        "taskStatus": task.status,
        "generatedCount": run.generated_count,
    }


def _mark_review_refresh_failed(
    *,
    session: Session,
    task_id: int,
    review_task_run_id: int,
    error_message: str,
) -> dict[str, Any]:
    task = session.get(AsyncTask, task_id)
    run = session.get(ReviewTaskRun, review_task_run_id)
    finished_at = utcnow()
    if task is not None:
        task.status = "failed"
        task.progress_pct = 100
        task.error_code = "review.refresh_failed"
        task.error_message = error_message
        task.finished_at = finished_at
    if run is not None:
        run.status = "failed"
        run.error_code = "review.refresh_failed"
        run.error_message = error_message
        run.finished_at = finished_at
    session.commit()
    return {
        "taskId": task_id,
        "reviewTaskRunId": review_task_run_id,
        "status": "failed",
        "errorMessage": error_message,
    }


def _require_model(session: Session, model: type[Any], item_id: int, error_code: str) -> Any:
    row = session.get(model, item_id)
    if row is None:
        raise ReviewTaskInputError(error_code)
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
    raise ReviewTaskInputError(f"Missing required integer field: {'/'.join(keys)}")
