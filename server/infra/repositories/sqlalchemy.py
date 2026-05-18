from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
import re
from typing import Any, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.parsers.base import clean_text
from server.infra.db.base import utcnow
from server.infra.db.models import (
    AsyncTask,
    BilibiliAuthSession,
    BilibiliImportRun,
    BilibiliQrSession,
    Course,
    CourseResource,
    CourseSegment,
    HandoutBlock,
    HandoutBlockRef,
    HandoutOutline,
    HandoutVersion,
    IdempotencyRecord,
    LearningPreference,
    ParseRun,
    QaMessage,
    QaMessageRef,
    QaSession,
    Quiz,
    QuizAttempt,
    QuizAttemptItem,
    QuizQuestion,
    QuizQuestionRef,
    MasteryRecord,
    ReviewTask,
    ReviewTaskRef,
    ReviewTaskRun,
    UserCourseProgress,
    VectorDocument,
)


T = TypeVar("T")


GRANULARITY_MAP = {
    "quick": ("low", "low"),
    "balanced": ("medium", "medium"),
    "detailed": ("high", "high"),
}

OUTLINE_DOCUMENT_CONTEXT_TYPES = {
    "pdf_page_text",
    "ppt_slide_text",
    "docx_block_text",
    "ocr_text",
    "formula",
    "image_caption",
}

_BILIBILI_QR_CHANGE_FIELDS = {
    "status": "status",
    "poll_payload_json": "poll_payload_json",
    "pollPayloadJson": "poll_payload_json",
    "error_code": "error_code",
    "errorCode": "error_code",
    "failure_reason": "failure_reason",
    "failureReason": "failure_reason",
    "scanned_at": "scanned_at",
    "scannedAt": "scanned_at",
    "confirmed_at": "confirmed_at",
    "confirmedAt": "confirmed_at",
    "expires_at": "expires_at",
    "expiresAt": "expires_at",
}

_BILIBILI_IMPORT_RUN_CHANGE_FIELDS = {
    "status": "status",
    "stage": "stage",
    "progress_pct": "progress_pct",
    "progressPct": "progress_pct",
    "task_id": "task_id",
    "taskId": "task_id",
    "preview": "preview_json",
    "preview_json": "preview_json",
    "selection": "selection_json",
    "selection_json": "selection_json",
    "resource_ids": "resource_ids_json",
    "resourceIds": "resource_ids_json",
    "recoverable": "recoverable",
    "temp_dir": "temp_dir",
    "tempDir": "temp_dir",
    "error_code": "error_code",
    "errorCode": "error_code",
    "failure_reason": "failure_reason",
    "failureReason": "failure_reason",
    "started_at": "started_at",
    "startedAt": "started_at",
    "finished_at": "finished_at",
    "finishedAt": "finished_at",
}


class SqlAlchemyRuntimeRepository:
    def __init__(self, session: Session, *, user_id: int = 1) -> None:
        self.session = session
        self.user_id = user_id
        self._idempotency_depth = 0

    def run_idempotent(self, action: str, key: str | None, factory: Callable[[], T]) -> T:
        if not key:
            return factory()

        existing = self.session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.action == action,
                IdempotencyRecord.key == key,
            )
        )
        if existing is not None:
            return existing.result_json  # type: ignore[return-value]

        self._idempotency_depth += 1
        try:
            value = factory()
            self.session.add(
                IdempotencyRecord(
                    action=action,
                    key=key,
                    result_json=_json_ready(value),
                )
            )
            self.session.commit()
            return value
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.action == action,
                    IdempotencyRecord.key == key,
                )
            )
            if existing is not None:
                return existing.result_json  # type: ignore[return-value]
            raise
        except Exception:
            self.session.rollback()
            raise
        finally:
            self._idempotency_depth -= 1

    def get_idempotency_result(self, action: str, key: str | None) -> Any | None:
        if not key:
            return None
        existing = self.session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.action == action,
                IdempotencyRecord.key == key,
            )
        )
        if existing is None:
            return None
        return existing.result_json

    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
        exam_at: datetime | None = None,
    ) -> dict[str, Any]:
        course = Course(
            user_id=self.user_id,
            title=title,
            entry_type=entry_type,
            catalog_id=catalog_id,
            goal_text=goal_text,
            exam_at=_normalize_utc_datetime(exam_at),
            preferred_style=preferred_style,
            lifecycle_status="draft",
            pipeline_stage="idle",
            pipeline_status="idle",
        )
        self.session.add(course)
        self._commit_or_flush()
        return _course_dict(course)

    def list_recent_courses(self) -> list[dict[str, Any]]:
        courses = self.session.scalars(
            select(Course)
            .where(Course.user_id == self.user_id)
            .order_by(Course.updated_at.desc(), Course.id.desc())
        ).all()
        return [_course_dict(course) for course in courses]

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        course = self._get_course_model(course_id)
        if course is None:
            return None
        return _course_dict(course)

    def create_bilibili_qr_session(
        self,
        *,
        qr_key: str,
        qr_url: str,
        status: str = "pending_scan",
        poll_payload_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        qr_session = BilibiliQrSession(
            qr_key=qr_key,
            qr_url=qr_url,
            status=status,
            poll_payload_json=poll_payload_json,
            expires_at=_normalize_utc_datetime(expires_at),
        )
        self.session.add(qr_session)
        self._commit_or_flush()
        return _bilibili_qr_session_dict(qr_session)

    def get_bilibili_qr_session(self, qr_key: str) -> dict[str, Any] | None:
        qr_session = self.session.scalar(
            select(BilibiliQrSession).where(BilibiliQrSession.qr_key == qr_key)
        )
        if qr_session is None:
            return None
        return _bilibili_qr_session_dict(qr_session)

    def update_bilibili_qr_session(self, qr_key: str, **changes: Any) -> dict[str, Any] | None:
        qr_session = self.session.scalar(
            select(BilibiliQrSession).where(BilibiliQrSession.qr_key == qr_key)
        )
        if qr_session is None:
            return None
        for key, value in changes.items():
            column_name = _BILIBILI_QR_CHANGE_FIELDS.get(key)
            if column_name is not None:
                setattr(qr_session, column_name, _normalize_datetime_change(column_name, value))
        self._commit_or_flush()
        return _bilibili_qr_session_dict(qr_session)

    def save_bilibili_auth_session(
        self,
        *,
        cookies_json: dict[str, Any],
        csrf: str | None = None,
        expires_at: datetime | None = None,
        status: str = "valid",
    ) -> dict[str, Any]:
        auth_session = self.session.scalar(
            select(BilibiliAuthSession).where(BilibiliAuthSession.user_id == self.user_id)
        )
        now = utcnow()
        if auth_session is None:
            auth_session = BilibiliAuthSession(
                user_id=self.user_id,
                status=status,
                cookies_json=cookies_json,
                csrf=csrf,
                expires_at=_normalize_utc_datetime(expires_at),
                last_verified_at=now,
            )
            self.session.add(auth_session)
        else:
            auth_session.status = status
            auth_session.cookies_json = cookies_json
            auth_session.csrf = csrf
            auth_session.expires_at = _normalize_utc_datetime(expires_at)
            auth_session.last_verified_at = now
            auth_session.error_code = None
            auth_session.failure_reason = None
        self._commit_or_flush()
        return _bilibili_auth_session_dict(auth_session)

    def get_bilibili_auth_session(self) -> dict[str, Any] | None:
        auth_session = self.session.scalar(
            select(BilibiliAuthSession).where(BilibiliAuthSession.user_id == self.user_id)
        )
        if auth_session is None:
            return None
        return _bilibili_auth_session_dict(auth_session)

    def delete_bilibili_auth_session(self) -> bool:
        result = self.session.execute(
            delete(BilibiliAuthSession).where(BilibiliAuthSession.user_id == self.user_id)
        )
        deleted = result.rowcount != 0
        self._commit_or_flush()
        return deleted

    def create_bilibili_import_run(
        self,
        *,
        course_id: int,
        source_url: str,
        source_type: str,
        preview: dict[str, Any] | None = None,
        selection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        import_run = BilibiliImportRun(
            course_id=course_id,
            source_url=source_url,
            source_type=source_type,
            status="pending",
            stage="queued",
            progress_pct=0,
            preview_json=preview,
            selection_json=selection,
            resource_ids_json=[],
            recoverable=False,
            started_at=now,
        )
        self.session.add(import_run)
        self._commit_or_flush()
        return _bilibili_import_run_dict(import_run)

    def get_bilibili_import_run(self, import_run_id: int) -> dict[str, Any] | None:
        import_run = self.session.scalar(
            select(BilibiliImportRun).where(BilibiliImportRun.id == import_run_id)
        )
        if import_run is None:
            return None
        return _bilibili_import_run_dict(import_run)

    def list_bilibili_import_runs(self, course_id: int) -> list[dict[str, Any]]:
        import_runs = self.session.scalars(
            select(BilibiliImportRun)
            .where(BilibiliImportRun.course_id == course_id)
            .order_by(BilibiliImportRun.created_at.desc(), BilibiliImportRun.id.desc())
        ).all()
        return [_bilibili_import_run_dict(import_run) for import_run in import_runs]

    def update_bilibili_import_run(self, import_run_id: int, **changes: Any) -> dict[str, Any] | None:
        import_run = self.session.scalar(
            select(BilibiliImportRun).where(BilibiliImportRun.id == import_run_id)
        )
        if import_run is None:
            return None
        for key, value in changes.items():
            column_name = _BILIBILI_IMPORT_RUN_CHANGE_FIELDS.get(key)
            if column_name is not None:
                setattr(import_run, column_name, _normalize_datetime_change(column_name, value))
        if (
            import_run.status in {"imported", "failed", "recoverable", "canceled"}
            and "finished_at" not in changes
            and "finishedAt" not in changes
            and import_run.finished_at is None
        ):
            import_run.finished_at = utcnow()
        self._commit_or_flush()
        return _bilibili_import_run_dict(import_run)

    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        sort_order = (
            self.session.scalar(
                select(func.count(CourseResource.id)).where(CourseResource.course_id == course_id)
            )
            or 0
        )
        resource = CourseResource(
            course_id=course_id,
            resource_type=_payload_value(payload, "resourceType", "resource_type"),
            source_type=_payload_value(payload, "sourceType", "source_type", default="upload"),
            origin_url=_payload_value(payload, "originUrl", "origin_url"),
            object_key=_payload_value(payload, "objectKey", "object_key"),
            preview_key=_payload_value(payload, "previewKey", "preview_key"),
            original_name=_payload_value(payload, "originalName", "original_name"),
            mime_type=_payload_value(payload, "mimeType", "mime_type"),
            size_bytes=_payload_value(payload, "sizeBytes", "size_bytes"),
            checksum=_payload_value(payload, "checksum"),
            ingest_status="ready",
            validation_status="passed",
            processing_status="pending",
            parse_policy_json=_payload_value(payload, "parsePolicyJson", "parse_policy_json"),
            sort_order=int(sort_order),
        )
        self.session.add(resource)
        self._commit_or_flush()
        return _resource_dict(resource)

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        resources = self.session.scalars(
            select(CourseResource)
            .where(CourseResource.course_id == course_id)
            .order_by(CourseResource.sort_order.asc(), CourseResource.id.asc())
        ).all()
        return [_resource_dict(resource) for resource in resources]

    def get_resource(self, resource_id: int) -> dict[str, Any] | None:
        resource = self.session.scalar(
            select(CourseResource)
            .join(Course, Course.id == CourseResource.course_id)
            .where(
                CourseResource.id == resource_id,
                Course.user_id == self.user_id,
            )
        )
        if resource is None:
            return None
        return _resource_dict(resource)

    def get_resource_delete_blockers(self, course_id: int, resource_id: int) -> dict[str, int]:
        resource_exists = self.session.scalar(
            select(CourseResource.id).where(
                CourseResource.course_id == course_id,
                CourseResource.id == resource_id,
            )
        )
        if resource_exists is None:
            return {}

        checks = (
            ("asyncTasks", AsyncTask, AsyncTask.resource_id),
            ("courseSegments", CourseSegment, CourseSegment.resource_id),
            ("vectorDocuments", VectorDocument, VectorDocument.resource_id),
            ("handoutBlockRefs", HandoutBlockRef, HandoutBlockRef.resource_id),
            ("qaMessageRefs", QaMessageRef, QaMessageRef.resource_id),
            ("quizQuestionRefs", QuizQuestionRef, QuizQuestionRef.resource_id),
            ("reviewTaskRefs", ReviewTaskRef, ReviewTaskRef.resource_id),
            ("userProgressVideo", UserCourseProgress, UserCourseProgress.last_video_resource_id),
            ("userProgressDocument", UserCourseProgress, UserCourseProgress.last_doc_resource_id),
        )
        blockers: dict[str, int] = {}
        for name, model, column in checks:
            count = self.session.scalar(select(func.count()).select_from(model).where(column == resource_id)) or 0
            if count:
                blockers[name] = int(count)
        return blockers

    def delete_resource(self, course_id: int, resource_id: int) -> bool:
        result = self.session.execute(
            delete(CourseResource).where(
                CourseResource.course_id == course_id,
                CourseResource.id == resource_id,
            )
        )
        deleted = result.rowcount != 0
        self._commit_or_flush()
        return deleted

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        now = utcnow()
        parse_run = ParseRun(
            course_id=course_id,
            status="queued",
            trigger_type="user_action",
            progress_pct=0,
        )
        self.session.add(parse_run)
        self.session.flush()

        resource_types = sorted({
            str(resource_type)
            for resource_type in self.session.scalars(
                select(CourseResource.resource_type).where(
                    CourseResource.course_id == course_id,
                    CourseResource.resource_type.is_not(None),
                )
            ).all()
        })
        task = AsyncTask(
            course_id=course_id,
            parse_run_id=parse_run.id,
            task_type="parse_pipeline",
            status="queued",
            target_type="parse_run",
            target_id=parse_run.id,
            progress_pct=0,
            payload_json={
                "courseId": course_id,
                "parseRunId": parse_run.id,
                "resourceTypes": resource_types,
            },
        )
        self.session.add(task)

        course = self._get_course_model(course_id)
        if course is not None:
            course.pipeline_stage = "parse"
            course.pipeline_status = "queued"
            course.updated_at = now

        self._commit_or_flush()
        return _parse_run_dict(parse_run), _async_trigger_dict(task, "parse_run", parse_run.id)

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        parse_run = self.session.get(ParseRun, parse_run_id)
        if parse_run is None:
            return None
        return _parse_run_dict(parse_run)

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        course = self._get_course_model(course_id)
        if course and course.active_parse_run_id is not None:
            active = self.session.get(ParseRun, course.active_parse_run_id)
            if active is not None:
                return _parse_run_dict(active)
        parse_run = self.session.scalars(
            select(ParseRun)
            .where(ParseRun.course_id == course_id)
            .order_by(ParseRun.created_at.desc(), ParseRun.id.desc())
        ).first()
        if parse_run is None:
            return None
        return _parse_run_dict(parse_run)

    def create_async_task(
        self,
        *,
        course_id: int,
        task_type: str,
        status: str = "queued",
        progress_pct: int = 0,
        parse_run_id: int | None = None,
        resource_id: int | None = None,
        parent_task_id: int | None = None,
        target_type: str | None = None,
        target_id: int | None = None,
        step_code: str | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = AsyncTask(
            course_id=course_id,
            parse_run_id=parse_run_id,
            resource_id=resource_id,
            parent_task_id=parent_task_id,
            task_type=task_type,
            status=status,
            target_type=target_type,
            target_id=target_id,
            step_code=step_code,
            progress_pct=progress_pct,
            payload_json=payload_json,
        )
        self.session.add(task)
        self._commit_or_flush()
        return _async_task_dict(task)

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        task = self.session.get(AsyncTask, task_id)
        if task is None:
            return None
        return _async_task_dict(task)

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(AsyncTask).where(AsyncTask.course_id == course_id)
        if parse_run_id is not None:
            stmt = stmt.where(AsyncTask.parse_run_id == parse_run_id)
        tasks = self.session.scalars(stmt.order_by(AsyncTask.id.asc())).all()
        return [_async_task_dict(task) for task in tasks]

    def update_async_task(self, task_id: int, **changes: Any) -> dict[str, Any] | None:
        task = self.session.get(AsyncTask, task_id)
        if task is None:
            return None
        if changes.pop("clear_error", False):
            task.error_code = None
            task.error_message = None
        for attr, value in _async_task_changes(changes).items():
            setattr(task, attr, value)
        self._commit_or_flush()
        return _async_task_dict(task)

    def mark_parse_run_succeeded(
        self,
        parse_run_id: int,
        *,
        summary_json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        parse_run = self.session.get(ParseRun, parse_run_id)
        if parse_run is None:
            return None
        now = utcnow()
        parse_run.status = "succeeded"
        parse_run.progress_pct = 100
        parse_run.summary_json = summary_json
        parse_run.finished_at = now

        course = self._get_course_model(parse_run.course_id)
        if course is not None:
            course.lifecycle_status = "inquiry_ready"
            course.pipeline_stage = "parse"
            course.pipeline_status = "succeeded"
            course.active_parse_run_id = parse_run.id
            active_handout = (
                self.session.get(HandoutVersion, course.active_handout_version_id)
                if course.active_handout_version_id is not None
                else None
            )
            if active_handout is not None and active_handout.source_parse_run_id != parse_run.id:
                course.active_handout_version_id = None
                self._clear_course_progress_handout_refs(course.id)
            course.updated_at = now

        self._commit_or_flush()
        return _parse_run_dict(parse_run)

    def save_inquiry_answers(
        self,
        course_id: int,
        answers: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        course = self._get_course_model(course_id)
        answer_values = {
            str(answer.get("key")): answer.get("value")
            for answer in answers
            if answer.get("key") is not None
        }
        granularity = str(answer_values.get("explanation_granularity") or "balanced")
        formula_detail_level, example_density = GRANULARITY_MAP.get(granularity, ("medium", "medium"))
        confirmed_at = utcnow()
        preference = self.session.scalar(
            select(LearningPreference).where(
                LearningPreference.user_id == self.user_id,
                LearningPreference.course_id == course_id,
            )
        )
        snapshot = {
            "version": 1,
            "answers": list(answers),
            "activeParseRunId": course.active_parse_run_id if course is not None else None,
            "derived": {
                "formulaDetailLevel": formula_detail_level,
                "exampleDensity": example_density,
            },
        }
        fields = {
            "user_id": self.user_id,
            "course_id": course_id,
            "goal_type": str(answer_values.get("goal_type") or "final_review"),
            "self_level": str(answer_values.get("mastery_level") or "intermediate"),
            "time_budget_minutes": int(answer_values.get("time_budget_minutes") or 60),
            "exam_at": _normalize_utc_datetime(course.exam_at) if course is not None else None,
            "preferred_style": str(
                answer_values.get("handout_style")
                or (course.preferred_style if course is not None else "balanced")
            ),
            "example_density": example_density,
            "formula_detail_level": formula_detail_level,
            "language_style": str(answer_values.get("language_style") or "friendly"),
            "focus_knowledge_json": answer_values.get("focus_knowledge_points") or [],
            "inquiry_answers_json": _json_ready(snapshot),
            "confirmed_at": confirmed_at,
        }
        if preference is None:
            preference = LearningPreference(**fields)
            self.session.add(preference)
        else:
            for attr, value in fields.items():
                setattr(preference, attr, value)

        if course is not None:
            course.pipeline_stage = "inquiry"
            course.updated_at = confirmed_at

        self._commit_or_flush()
        return {"saved": True, "answerCount": len(answers)}

    def create_course_segments(
        self,
        *,
        course_id: int,
        resource_id: int,
        parse_run_id: int,
        segments: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[CourseSegment] = []
        for index, segment in enumerate(segments):
            row = CourseSegment(
                course_id=course_id,
                resource_id=resource_id,
                parse_run_id=parse_run_id,
                segment_type=_payload_value(segment, "segmentType", "segment_type"),
                title=_payload_value(segment, "title"),
                section_path=_payload_value(segment, "sectionPath", "section_path", default=[]),
                text_content=_payload_value(segment, "textContent", "text_content", default=""),
                plain_text=_payload_value(segment, "plainText", "plain_text", default=""),
                start_sec=_payload_value(segment, "startSec", "start_sec"),
                end_sec=_payload_value(segment, "endSec", "end_sec"),
                page_no=_payload_value(segment, "pageNo", "page_no"),
                slide_no=_payload_value(segment, "slideNo", "slide_no"),
                image_key=_payload_value(segment, "imageKey", "image_key"),
                formula_text=_payload_value(segment, "formulaText", "formula_text"),
                bbox_json=_payload_value(segment, "bboxJson", "bbox_json"),
                order_no=int(_payload_value(segment, "orderNo", "order_no", default=index)),
                token_count=int(_payload_value(segment, "tokenCount", "token_count", default=0)),
                is_active=bool(_payload_value(segment, "isActive", "is_active", default=True)),
            )
            self.session.add(row)
            rows.append(row)
        self._commit_or_flush()
        return [_course_segment_dict(row) for row in rows]

    def list_course_segments(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        stmt = select(CourseSegment).where(CourseSegment.course_id == course_id)
        if parse_run_id is not None:
            stmt = stmt.where(CourseSegment.parse_run_id == parse_run_id)
        if active_only:
            stmt = stmt.where(CourseSegment.is_active.is_(True))
        rows = self.session.scalars(stmt.order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())).all()
        return [_course_segment_dict(row) for row in rows]

    def create_handout(
        self,
        course_id: int,
        *,
        outline: dict[str, Any] | None = None,
        outline_meta: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        course = self._get_course_model(course_id)
        if course is None:
            raise ValueError(f"Course {course_id} was not found.")

        source_parse_run_id = course.active_parse_run_id
        outline_payload = outline
        outline_items = _outline_child_items(outline_payload or {})

        if outline_payload is None or not outline_items:
            status = "failed"
            outline_status = "failed"
            title = course.title
            summary = "没有可用的视频字幕片段，未生成视频时间轴目录。"
            error_code = error_code or "handout_outline.no_video_caption"
            error_message = error_message or "Active parse run has no usable video_caption segments."
            outline_items = []
        else:
            status = "outline_ready"
            outline_status = "ready"
            title = str(outline_payload["title"])
            summary = str(outline_payload["summary"])
            error_code = None
            error_message = None

        version = HandoutVersion(
            course_id=course_id,
            source_parse_run_id=source_parse_run_id,
            title=title,
            summary=summary,
            status=status,
            outline_status=outline_status,
            total_blocks=len(outline_items),
            ready_blocks=0,
            pending_blocks=len(outline_items),
            error_code=error_code,
            error_message=error_message,
            meta_json=_json_ready(outline_meta) if outline_meta else None,
        )
        self.session.add(version)
        self.session.flush()

        blocks: list[HandoutBlock] = []
        if status == "outline_ready" and outline_payload is not None:
            self.session.add(
                HandoutOutline(
                    handout_version_id=version.id,
                    course_id=course_id,
                    source_parse_run_id=source_parse_run_id,
                    status="ready",
                    title=title,
                    summary=summary,
                    item_count=len(outline_items),
                    outline_json=_json_ready(outline_payload),
                )
            )
            for item in outline_items:
                block = HandoutBlock(
                    handout_version_id=version.id,
                    outline_key=str(item["outlineKey"]),
                    title=str(item["title"]),
                    summary=str(item["summary"]),
                    status=str(item.get("generationStatus") or "pending"),
                    content_md=None,
                    start_sec=int(item["startSec"]),
                    end_sec=int(item["endSec"]),
                    sort_no=int(item["sortNo"]),
                    source_segment_keys_json=list(item["sourceSegmentKeys"]),
                    knowledge_points_json=None,
                    citations_json=[],
                )
                self.session.add(block)
                blocks.append(block)

        now = utcnow()
        task_status = "queued" if status == "outline_ready" else "failed"
        task = AsyncTask(
            course_id=course_id,
            parse_run_id=source_parse_run_id,
            task_type="handout_generate",
            status=task_status,
            target_type="handout_version",
            target_id=version.id,
            progress_pct=0 if task_status == "queued" else 100,
            payload_json={
                "courseId": course_id,
                "handoutVersionId": version.id,
                "sourceParseRunId": source_parse_run_id,
            },
            error_code=error_code,
            error_message=error_message,
            finished_at=now if task_status == "failed" else None,
        )
        self.session.add(task)

        course.active_handout_version_id = version.id
        course.pipeline_stage = "handout"
        course.pipeline_status = "succeeded" if status == "outline_ready" else "failed"
        if status == "outline_ready":
            course.lifecycle_status = "learning_ready"
            course.last_error = None
        else:
            course.last_error = error_message
        course.updated_at = now

        self._commit_or_flush()
        block_dicts = [_handout_block_dict(block) for block in blocks]
        return (
            _handout_version_dict(version, blocks=block_dicts),
            _async_trigger_dict(task, "handout_version", version.id),
            block_dicts,
        )

    def get_handout(self, handout_version_id: int) -> dict[str, Any] | None:
        version = self._get_handout_version_model(handout_version_id)
        if version is None:
            return None
        course = self._get_course_model(version.course_id)
        if (
            course is None
            or course.active_handout_version_id != version.id
            or course.active_parse_run_id != version.source_parse_run_id
        ):
            return None
        return _handout_version_dict(version, blocks=self._list_handout_blocks(version.id))

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None:
        version = self._get_latest_handout_version_model(course_id)
        if version is None:
            return None
        return _handout_version_dict(version, blocks=self._list_handout_blocks(version.id))

    def get_latest_outline(self, course_id: int) -> dict[str, Any] | None:
        version = self._get_latest_handout_version_model(course_id)
        if version is None:
            return None
        outline = self.session.scalar(
            select(HandoutOutline).where(HandoutOutline.handout_version_id == version.id)
        )
        if outline is None:
            return None
        blocks = self.session.scalars(
            select(HandoutBlock)
            .where(HandoutBlock.handout_version_id == version.id)
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
        return _handout_outline_dict(version, outline, blocks)

    def get_block_jump_target(self, block_id: int) -> dict[str, Any] | None:
        block = self._get_active_handout_block(block_id)
        if block is None:
            return None

        video_resource_id = None
        for source_key in block.source_segment_keys_json or []:
            segment_id = _segment_id_from_source_key(str(source_key))
            if segment_id is None:
                continue
            segment = self.session.get(CourseSegment, segment_id)
            if segment is not None:
                video_resource_id = segment.resource_id
                break

        doc_ref = self.session.scalars(
            select(HandoutBlockRef)
            .where(
                HandoutBlockRef.handout_block_id == block.id,
                (
                    HandoutBlockRef.page_no.is_not(None)
                    | HandoutBlockRef.slide_no.is_not(None)
                    | HandoutBlockRef.anchor_key.is_not(None)
                ),
            )
            .order_by(HandoutBlockRef.sort_no.asc(), HandoutBlockRef.id.asc())
        ).first()

        return {
            "blockId": block.id,
            "outlineKey": block.outline_key,
            "videoResourceId": video_resource_id,
            "startSec": block.start_sec,
            "endSec": block.end_sec,
            "docResourceId": doc_ref.resource_id if doc_ref is not None else None,
            "pageNo": doc_ref.page_no if doc_ref is not None else None,
            "slideNo": doc_ref.slide_no if doc_ref is not None else None,
            "anchorKey": doc_ref.anchor_key if doc_ref is not None else None,
        }

    def get_handout_block_status(self, block_id: int) -> dict[str, Any] | None:
        block = self._get_active_handout_block(block_id)
        if block is None:
            return None
        task = self._current_handout_block_task(block)
        status = _handout_block_status_dict(block)
        if task is not None:
            status["taskId"] = task.id
            status["taskStatus"] = task.status
        return status

    def get_current_handout_block(self, course_id: int, current_sec: int) -> dict[str, Any] | None:
        version = self._get_latest_handout_version_model(course_id)
        if version is None:
            return None
        blocks = self.session.scalars(
            select(HandoutBlock)
            .where(HandoutBlock.handout_version_id == version.id)
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
        current: HandoutBlock | None = None
        for index, block in enumerate(blocks):
            if block.start_sec is None or block.end_sec is None:
                continue
            is_last = index == len(blocks) - 1
            if block.start_sec <= current_sec < block.end_sec or (is_last and current_sec == block.end_sec):
                current = block
                break
        if current is None:
            return None
        prefetch_block_id = None
        if current.end_sec is not None and current.end_sec - current_sec <= 30:
            current_index = blocks.index(current)
            if current_index + 1 < len(blocks):
                next_block = blocks[current_index + 1]
                if next_block.status == "pending":
                    prefetch_block_id = next_block.id
        return {
            "blockId": current.id,
            "outlineKey": current.outline_key,
            "startSec": current.start_sec,
            "endSec": current.end_sec,
            "status": current.status,
            "generationStatus": current.status,
            "prefetchBlockId": prefetch_block_id,
        }

    def prepare_handout_block_generation(
        self,
        block_id: int,
    ) -> tuple[dict[str, Any], tuple[int, dict[str, Any]] | None] | None:
        block = self._get_active_handout_block(block_id)
        if block is None:
            return None
        version = self.session.get(HandoutVersion, block.handout_version_id)
        if version is None:
            return None
        course = self.session.get(Course, version.course_id)
        if course is None:
            return None

        current_task = self._current_handout_block_task(block)
        if block.status == "ready":
            return _handout_block_status_dict(block), None
        if current_task is not None:
            return _async_trigger_dict(current_task, "handout_block", block.id), None

        claim = self.session.execute(
            update(HandoutBlock)
            .where(
                HandoutBlock.id == block.id,
                HandoutBlock.status.in_(("pending", "failed")),
            )
            .values(status="generating")
            .execution_options(synchronize_session=False)
        )
        if (claim.rowcount or 0) != 1:
            self.session.flush()
            self.session.expire_all()
            block = self._get_active_handout_block(block_id)
            if block is None:
                return None
            if block.status == "ready":
                return _handout_block_status_dict(block), None
            current_task = self._current_handout_block_task(block)
            if current_task is not None:
                return _async_trigger_dict(current_task, "handout_block", block.id), None
            if block.status == "generating":
                return _handout_block_status_dict(block), None
        else:
            block.status = "generating"

        block.status = "generating"
        payload = {
            "courseId": version.course_id,
            "handoutVersionId": version.id,
            "handoutBlockId": block.id,
            "sourceParseRunId": version.source_parse_run_id,
        }
        task = AsyncTask(
            course_id=version.course_id,
            parse_run_id=version.source_parse_run_id,
            task_type="handout_block_generate",
            status="queued",
            target_type="handout_block",
            target_id=block.id,
            progress_pct=0,
            payload_json=payload,
        )
        self.session.add(task)
        course.pipeline_stage = "handout"
        course.pipeline_status = "running"
        course.updated_at = utcnow()
        self._refresh_handout_version_status(version)
        self._commit_or_flush()
        return _async_trigger_dict(task, "handout_block", block.id), (task.id, payload)

    def save_handout_block_result(
        self,
        block_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        block = self.session.scalar(
            select(HandoutBlock)
            .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
            .join(Course, Course.id == HandoutVersion.course_id)
            .where(
                HandoutBlock.id == block_id,
                Course.user_id == self.user_id,
                Course.active_handout_version_id == HandoutBlock.handout_version_id,
            )
        )
        if block is None:
            return None
        version = self.session.get(HandoutVersion, block.handout_version_id)
        if version is None:
            return None

        generation_metadata = _generation_metadata_from_response(payload)
        normalized_refs = self._normalize_handout_block_refs(block=block, version=version, payload=payload)
        block.title = str(_payload_value(payload, "title", default=block.title))
        block.summary = str(_payload_value(payload, "summary", default=block.summary))
        block.content_md = str(_payload_value(payload, "contentMd", "content_md", default=""))
        block.status = "ready"
        block.source_segment_keys_json = list(block.source_segment_keys_json or [])
        block.knowledge_points_json = list(_payload_value(payload, "knowledgePoints", "knowledge_points", default=[]) or [])
        block.citations_json = [_json_ready(ref) for ref in normalized_refs]
        block.generation_metadata_json = _json_ready(generation_metadata) if generation_metadata else None

        self.session.execute(delete(HandoutBlockRef).where(HandoutBlockRef.handout_block_id == block.id))
        for ref in normalized_refs:
            self.session.add(
                HandoutBlockRef(
                    handout_block_id=block.id,
                    resource_id=int(ref["resourceId"]),
                    segment_id=ref.get("segmentId"),
                    ref_type=str(ref["refType"]),
                    quote_text=ref.get("quoteText"),
                    page_no=ref.get("pageNo"),
                    slide_no=ref.get("slideNo"),
                    anchor_key=ref.get("anchorKey"),
                    start_sec=ref.get("startSec"),
                    end_sec=ref.get("endSec"),
                    bbox_json=ref.get("bboxJson"),
                    ref_label=str(ref["refLabel"]),
                    sort_no=int(ref["sortNo"]),
                )
            )

        self._refresh_handout_version_status(version)
        self._commit_or_flush()
        result = _handout_block_dict(block)
        if generation_metadata:
            result["generationMetadata"] = generation_metadata
        return result

    def create_vector_document(
        self,
        *,
        course_id: int,
        owner_type: str,
        owner_id: int,
        content_text: str,
        metadata_json: dict[str, Any],
        parse_run_id: int | None = None,
        handout_version_id: int | None = None,
        resource_id: int | None = None,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        document = VectorDocument(
            course_id=course_id,
            parse_run_id=parse_run_id,
            handout_version_id=handout_version_id,
            owner_type=owner_type,
            owner_id=owner_id,
            resource_id=resource_id,
            content_text=content_text,
            metadata_json=metadata_json,
            embedding=embedding,
        )
        self.session.add(document)
        self._commit_or_flush()
        return _vector_document_dict(document)

    def get_handout_outline_context(self, course_id: int) -> dict[str, Any] | None:
        course = self._get_course_model(course_id)
        if course is None or course.active_parse_run_id is None:
            return None
        parse_run_id = int(course.active_parse_run_id)
        caption_segments = [
            _course_segment_dict(segment)
            for segment in self._list_active_video_caption_segments(
                course_id=course_id,
                parse_run_id=parse_run_id,
            )
        ]
        document_segments = self._list_active_outline_document_segments(
            course_id=course_id,
            parse_run_id=parse_run_id,
        )
        return {
            "courseId": course_id,
            "activeParseRunId": parse_run_id,
            "title": course.title or "视频时间轴目录",
            "summary": "基于视频字幕和配套资料生成的语义讲义目录。",
            "captionSegments": caption_segments,
            "documentContext": _document_context_from_segments(document_segments),
        }

    def get_qa_context(self, course_id: int, handout_block_id: int) -> dict[str, Any] | None:
        course = self._get_course_model(course_id)
        if course is None or course.active_parse_run_id is None or course.active_handout_version_id is None:
            return None
        block = self._get_active_handout_block(handout_block_id)
        if block is None:
            return None
        version = self.session.get(HandoutVersion, block.handout_version_id)
        if (
            version is None
            or version.id != course.active_handout_version_id
            or version.course_id != course.id
            or version.source_parse_run_id != course.active_parse_run_id
        ):
            return None

        segments = self._qa_segments(course_id=course.id, parse_run_id=course.active_parse_run_id)
        current_block = self._qa_block_payload(block, course=course, version=version)
        active_block_vectors = self._active_handout_block_vectors(course=course, version=version)
        adjacent_blocks = self._qa_adjacent_blocks(
            block,
            course=course,
            version=version,
            vector_documents=active_block_vectors,
        )
        return {
            "courseId": course.id,
            "activeCourseId": course.id,
            "activeParseRunId": course.active_parse_run_id,
            "activeHandoutVersionId": version.id,
            "handoutBlockId": block.id,
            "currentBlock": current_block,
            "segments": segments,
            "knowledgePointEvidences": [],
            "adjacentBlocks": adjacent_blocks,
        }

    def save_qa_exchange(
        self,
        context: dict[str, Any],
        question: str,
        response: dict[str, Any],
        refs: list[dict[str, Any]],
        candidate_count: int,
    ) -> dict[str, Any]:
        course_id = _as_positive_int(_payload_value(context, "courseId", "activeCourseId"))
        parse_run_id = _as_positive_int(_payload_value(context, "activeParseRunId"))
        handout_version_id = _as_positive_int(_payload_value(context, "activeHandoutVersionId"))
        handout_block_id = _as_positive_int(_payload_value(context, "handoutBlockId"))
        if (
            course_id is None
            or parse_run_id is None
            or handout_version_id is None
            or handout_block_id is None
            or not self._qa_context_is_active(
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
                handout_block_id=handout_block_id,
            )
        ):
            raise RuntimeError("Cannot save QA exchange for stale or invalid context.")

        now = utcnow()
        generation_metadata = _generation_metadata_from_response(response)
        qa_session = QaSession(
            user_id=self.user_id,
            course_id=course_id,
            handout_version_id=handout_version_id,
            handout_block_id=handout_block_id,
            status="active",
            context_snapshot_json={
                "courseId": course_id,
                "activeParseRunId": parse_run_id,
                "activeHandoutVersionId": handout_version_id,
                "handoutBlockId": handout_block_id,
                "candidateCount": candidate_count,
                "generationMetadata": generation_metadata,
            },
            message_count=0,
            last_message_at=now,
        )
        self.session.add(qa_session)
        self.session.flush()

        user_message = QaMessage(
            session_id=qa_session.id,
            role="user",
            content_md=question,
            content_text=clean_text(question),
            answer_type=None,
        )
        self.session.add(user_message)
        self.session.flush()

        assistant_message = QaMessage(
            session_id=qa_session.id,
            role="assistant",
            content_md=str(response["answerMd"]),
            content_text=clean_text(str(response["answerMd"])),
            answer_type=str(response.get("answerType") or "direct_answer"),
        )
        self.session.add(assistant_message)
        self.session.flush()

        for ref in refs:
            self.session.add(
                QaMessageRef(
                    qa_message_id=assistant_message.id,
                    resource_id=int(ref["resourceId"]),
                    segment_id=ref.get("segmentId"),
                    ref_type=str(ref["refType"]),
                    quote_text=ref.get("quoteText"),
                    page_no=ref.get("pageNo"),
                    slide_no=ref.get("slideNo"),
                    anchor_key=ref.get("anchorKey"),
                    start_sec=ref.get("startSec"),
                    end_sec=ref.get("endSec"),
                    bbox_json=ref.get("bboxJson"),
                    ref_label=str(ref["refLabel"]),
                    sort_no=int(ref["sortNo"]),
                    rank=ref.get("rank"),
                )
        )

        qa_session.message_count = 2
        qa_session.last_message_at = now
        self._commit_or_flush()
        citations = [] if response.get("answerType") == "insufficient_evidence" else list(response.get("citations") or [])
        result = {
            "sessionId": qa_session.id,
            "messageId": assistant_message.id,
            "answerMd": response["answerMd"],
            "answerType": response.get("answerType"),
            "citations": citations,
        }
        if generation_metadata:
            result["generationMetadata"] = generation_metadata
        return result

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]] | None:
        qa_session = self.session.scalar(
            select(QaSession)
            .join(Course, Course.id == QaSession.course_id)
            .join(HandoutVersion, HandoutVersion.id == QaSession.handout_version_id)
            .where(
                QaSession.id == session_id,
                QaSession.user_id == self.user_id,
                Course.user_id == self.user_id,
                Course.active_handout_version_id == QaSession.handout_version_id,
                HandoutVersion.source_parse_run_id == Course.active_parse_run_id,
            )
        )
        if qa_session is None:
            return None
        messages = self.session.scalars(
            select(QaMessage)
            .where(QaMessage.session_id == session_id)
            .order_by(QaMessage.created_at.asc(), QaMessage.id.asc())
        ).all()
        generation_metadata = _generation_metadata_from_response(qa_session.context_snapshot_json or {})
        return [self._qa_message_dict(message, generation_metadata=generation_metadata) for message in messages]

    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        course = self._get_course_model(course_id)
        version = self._get_latest_handout_version_model(course_id)
        if course is None:
            raise ValueError(f"Course {course_id} was not found.")
        if version is None:
            raise ValueError("Course has no active handout version for quiz generation.")

        quiz = Quiz(
            course_id=course_id,
            handout_version_id=version.id,
            source_parse_run_id=version.source_parse_run_id,
            quiz_type="chapter_review",
            status="queued",
            question_count=0,
            payload_json=None,
        )
        self.session.add(quiz)
        self.session.flush()

        payload = {
            "courseId": course_id,
            "quizId": quiz.id,
            "handoutVersionId": version.id,
            "sourceParseRunId": version.source_parse_run_id,
            "questionCountLevel": question_count_level,
        }
        task = AsyncTask(
            course_id=course_id,
            parse_run_id=version.source_parse_run_id,
            task_type="quiz_generate",
            status="queued",
            target_type="quiz",
            target_id=quiz.id,
            progress_pct=0,
            payload_json=payload,
        )
        self.session.add(task)

        course.pipeline_stage = "quiz"
        course.pipeline_status = "queued"
        course.updated_at = utcnow()

        self._commit_or_flush()
        return _quiz_dict(quiz, questions=[]), _async_trigger_dict(task, "quiz", quiz.id)

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None:
        quiz = self._get_active_quiz_model(quiz_id)
        if quiz is None:
            return None
        questions = self.session.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.sort_no.asc(), QuizQuestion.id.asc())
        ).all()
        return _quiz_dict(quiz, questions=[_quiz_question_public_dict(question) for question in questions])

    def save_quiz_generation_result(
        self,
        quiz_id: int,
        payload: dict[str, Any],
        refs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        quiz = self._get_active_quiz_model(quiz_id)
        if quiz is None:
            return None

        existing_question_ids = [
            row_id
            for row_id in self.session.scalars(
                select(QuizQuestion.id).where(QuizQuestion.quiz_id == quiz.id)
            ).all()
        ]
        if existing_question_ids:
            self.session.execute(
                delete(QuizQuestionRef).where(QuizQuestionRef.quiz_question_id.in_(existing_question_ids))
            )
            self.session.execute(delete(QuizQuestion).where(QuizQuestion.id.in_(existing_question_ids)))
            self.session.flush()

        question_rows: dict[str, QuizQuestion] = {}
        for index, question in enumerate(_mapping_list(payload.get("questions")), start=1):
            question_key = _stable_key(_payload_value(question, "questionKey", "question_key")) or f"q{index}"
            row = QuizQuestion(
                quiz_id=quiz.id,
                question_key=question_key,
                question_type=str(_payload_value(question, "questionType", "question_type", default="single_choice")),
                stem_md=str(_payload_value(question, "stemMd", "stem_md", default="")),
                options_json=list(_payload_value(question, "options", default=[]) or []),
                correct_answer=str(_payload_value(question, "correctAnswer", "correct_answer", default="A")),
                explanation_md=str(_payload_value(question, "explanationMd", "explanation_md", default="")),
                difficulty_level=str(_payload_value(question, "difficultyLevel", "difficulty_level", default="medium")),
                knowledge_point_key=str(
                    _payload_value(question, "knowledgePointKey", "knowledge_point_key", default=question_key)
                ),
                knowledge_point_name=str(
                    _payload_value(question, "knowledgePointName", "knowledge_point_name", default=question_key)
                ),
                source_block_key=str(_payload_value(question, "sourceBlockKey", "source_block_key", default="")),
                source_segment_keys_json=list(
                    _payload_value(question, "sourceSegmentKeys", "source_segment_keys", default=[]) or []
                ),
                sort_no=index,
            )
            self.session.add(row)
            question_rows[question_key] = row
        self.session.flush()

        for ref in refs:
            question_key = _stable_key(_payload_value(ref, "questionKey", "question_key"))
            question = question_rows.get(question_key)
            if question is None:
                continue
            self.session.add(
                QuizQuestionRef(
                    quiz_question_id=question.id,
                    resource_id=int(ref["resourceId"]),
                    segment_id=ref.get("segmentId"),
                    ref_type=str(ref["refType"]),
                    quote_text=ref.get("quoteText"),
                    page_no=ref.get("pageNo"),
                    slide_no=ref.get("slideNo"),
                    anchor_key=ref.get("anchorKey"),
                    start_sec=ref.get("startSec"),
                    end_sec=ref.get("endSec"),
                    bbox_json=ref.get("bboxJson"),
                    ref_label=str(ref.get("refLabel") or ref.get("segmentKey") or "来源片段"),
                    sort_no=int(ref["sortNo"]),
                )
            )

        quiz.quiz_type = str(_payload_value(payload, "quizType", "quiz_type", default=quiz.quiz_type))
        quiz.status = "ready"
        quiz.question_count = len(question_rows)
        quiz.payload_json = _json_ready(payload)
        quiz.error_code = None
        quiz.error_message = None

        course = self._get_course_model(quiz.course_id)
        if course is not None:
            course.pipeline_stage = "quiz"
            course.pipeline_status = "succeeded"
            course.last_error = None
            course.updated_at = utcnow()

        self._commit_or_flush()
        return self.get_quiz(quiz.id)

    def get_quiz_submission_context(self, quiz_id: int) -> dict[str, Any] | None:
        quiz = self._get_active_quiz_model(quiz_id)
        if quiz is None:
            return None
        questions = self.session.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.sort_no.asc(), QuizQuestion.id.asc())
        ).all()
        return {
            "quizPayload": {
                "quizType": quiz.quiz_type,
                "questions": [_quiz_question_private_dict(question) for question in questions],
            },
            "masteryRecords": self._list_mastery_record_dicts(course_id=quiz.course_id),
        }

    def save_quiz_attempt_result(
        self,
        quiz_id: int,
        *,
        quiz_attempt_result: dict[str, Any],
        mastery_updates: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        quiz = self._get_active_quiz_model(quiz_id)
        if quiz is None:
            raise ValueError(f"Quiz {quiz_id} was not found.")
        questions = self.session.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.sort_no.asc(), QuizQuestion.id.asc())
        ).all()
        result = dict(quiz_attempt_result)
        mastery_updates = list(mastery_updates)
        attempt = QuizAttempt(
            user_id=self.user_id,
            course_id=quiz.course_id,
            quiz_id=quiz.id,
            review_task_run_id=None,
            score=int(result["score"]),
            total_score=int(result["totalScore"]),
            accuracy=float(result["accuracy"]),
            result_json=_json_ready(result | {"masteryUpdates": mastery_updates}),
        )
        self.session.add(attempt)
        self.session.flush()

        questions_by_key = {question.question_key: question for question in questions}
        for index, item in enumerate(_mapping_list(result.get("items")), start=1):
            question_key = str(_payload_value(item, "questionKey", "question_key", default=f"q{index}"))
            question = questions_by_key.get(question_key)
            self.session.add(
                QuizAttemptItem(
                    attempt_id=attempt.id,
                    quiz_question_id=question.id if question is not None else None,
                    question_key=question_key,
                    selected_option=str(_payload_value(item, "selectedOption", "selected_option", default="")),
                    correct_answer=str(_payload_value(item, "correctAnswer", "correct_answer", default="")),
                    is_correct=bool(_payload_value(item, "isCorrect", "is_correct", default=False)),
                    obtained_score=int(_payload_value(item, "obtainedScore", "obtained_score", default=0)),
                    explanation_md=str(_payload_value(item, "explanationMd", "explanation_md", default="")),
                    knowledge_point_key=str(
                        _payload_value(item, "knowledgePointKey", "knowledge_point_key", default="")
                    ),
                    source_block_key=str(_payload_value(item, "sourceBlockKey", "source_block_key", default="")),
                    sort_no=index,
                )
            )

        self._upsert_mastery_records(
            course_id=quiz.course_id,
            attempt_id=attempt.id,
            updates=mastery_updates,
            result_items=_mapping_list(result.get("items")),
        )
        review_run = ReviewTaskRun(
            user_id=self.user_id,
            course_id=quiz.course_id,
            source_quiz_attempt_id=attempt.id,
            status="queued",
            generated_count=0,
            payload_json={
                "quizId": quiz.id,
                "quizAttemptId": attempt.id,
            },
        )
        self.session.add(review_run)
        self.session.flush()
        attempt.review_task_run_id = review_run.id
        payload = {
            "courseId": quiz.course_id,
            "reviewTaskRunId": review_run.id,
        }
        task = AsyncTask(
            course_id=quiz.course_id,
            parse_run_id=quiz.source_parse_run_id,
            task_type="review_refresh",
            status="queued",
            target_type="review_task_run",
            target_id=review_run.id,
            progress_pct=0,
            payload_json=payload,
        )
        self.session.add(task)

        self._commit_or_flush()
        return {
            "attemptId": attempt.id,
            "score": attempt.score,
            "totalScore": attempt.total_score,
            "accuracy": attempt.accuracy,
            "reviewTaskRunId": review_run.id,
            "masteryDelta": result.get("masteryDelta", []),
            "recommendedReviewAction": result.get("recommendedReviewAction"),
            "_reviewRefreshTask": {
                "taskId": task.id,
                "payload": payload,
            },
        }

    def next_task_id(self) -> int:
        return self.session.scalar(select(func.coalesce(func.max(AsyncTask.id), 0))) + 1

    def create_review_run(self, course_id: int) -> dict[str, Any]:
        course = self._get_course_model(course_id)
        if course is None:
            raise ValueError(f"Course {course_id} was not found.")
        latest_attempt = self.session.scalars(
            select(QuizAttempt)
            .where(
                QuizAttempt.user_id == self.user_id,
                QuizAttempt.course_id == course_id,
            )
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id.desc())
        ).first()
        review_run = ReviewTaskRun(
            user_id=self.user_id,
            course_id=course_id,
            source_quiz_attempt_id=latest_attempt.id if latest_attempt is not None else None,
            status="queued",
            generated_count=0,
            payload_json={
                "quizAttemptId": latest_attempt.id if latest_attempt is not None else None,
            },
        )
        self.session.add(review_run)
        self.session.flush()
        self._supersede_pending_review_tasks_before(run_id=review_run.id, course_id=course_id)
        payload = {
            "courseId": course_id,
            "reviewTaskRunId": review_run.id,
        }
        task = AsyncTask(
            course_id=course_id,
            parse_run_id=course.active_parse_run_id,
            task_type="review_refresh",
            status="queued",
            target_type="review_task_run",
            target_id=review_run.id,
            progress_pct=0,
            payload_json=payload,
        )
        self.session.add(task)
        self._commit_or_flush()
        return _review_run_dict(review_run) | {
            "_reviewRefreshTask": {
                "taskId": task.id,
                "payload": payload,
            }
        }

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        latest_run_id = self._latest_active_review_run_id(course_id, statuses=("queued", "running", "ready"))
        if latest_run_id is None:
            return []
        run = self._latest_active_review_run(course_id)
        if run is None or run.id != latest_run_id:
            return []
        rows = self.session.scalars(
            select(ReviewTask)
            .where(
                ReviewTask.review_task_run_id == run.id,
                ReviewTask.status == "pending",
            )
            .order_by(ReviewTask.review_order.asc(), ReviewTask.priority_score.desc(), ReviewTask.id.asc())
        ).all()
        return [_review_task_dict(row) for row in rows]

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None:
        run = self.session.scalar(
            select(ReviewTaskRun)
            .join(Course, Course.id == ReviewTaskRun.course_id)
            .where(
                ReviewTaskRun.id == review_task_run_id,
                ReviewTaskRun.user_id == self.user_id,
                Course.user_id == self.user_id,
            )
        )
        if run is None:
            return None
        return _review_run_dict(run)

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]:
        task = self.session.scalar(
            select(ReviewTask)
            .join(Course, Course.id == ReviewTask.course_id)
            .join(ReviewTaskRun, ReviewTaskRun.id == ReviewTask.review_task_run_id)
            .join(QuizAttempt, QuizAttempt.id == ReviewTaskRun.source_quiz_attempt_id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                ReviewTask.id == review_task_id,
                ReviewTask.status == "pending",
                ReviewTaskRun.status == "ready",
                Course.user_id == self.user_id,
                Course.active_parse_run_id == Quiz.source_parse_run_id,
                Course.active_handout_version_id == Quiz.handout_version_id,
            )
        )
        latest_run_id = (
            self._latest_active_review_run_id(task.course_id, statuses=("queued", "running", "ready"))
            if task is not None
            else None
        )
        if task is None or task.review_task_run_id != latest_run_id:
            return {"reviewTaskId": review_task_id, "completed": False}
        task.status = "completed"
        task.completed_at = utcnow()
        self._commit_or_flush()
        return {"reviewTaskId": review_task_id, "completed": True}

    def save_review_task_run_result(
        self,
        review_task_run_id: int,
        payload: dict[str, Any],
        refs: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        run = self.session.scalar(
            select(ReviewTaskRun)
            .join(Course, Course.id == ReviewTaskRun.course_id)
            .where(
                ReviewTaskRun.id == review_task_run_id,
                ReviewTaskRun.user_id == self.user_id,
                Course.user_id == self.user_id,
            )
        )
        if run is None:
            return None
        if not self._review_run_can_publish(run):
            run.status = "skipped"
            run.error_code = "review.run_stale"
            run.error_message = "Review run no longer matches the active course context."
            run.finished_at = utcnow()
            self._commit_or_flush()
            return _review_run_dict(run)

        old_task_ids = [
            row_id
            for row_id in self.session.scalars(
                select(ReviewTask.id).where(ReviewTask.review_task_run_id == run.id)
            ).all()
        ]
        if old_task_ids:
            self.session.execute(delete(ReviewTaskRef).where(ReviewTaskRef.review_task_id.in_(old_task_ids)))
            self.session.execute(delete(ReviewTask).where(ReviewTask.id.in_(old_task_ids)))
            self.session.flush()

        self._supersede_pending_review_tasks_before(run_id=run.id, course_id=run.course_id)

        active_blocks = self._active_handout_blocks_for_course(run.course_id)
        blocks_by_key = _blocks_by_strategy_key(active_blocks)
        task_rows: dict[str, ReviewTask] = {}
        for item in _mapping_list(payload.get("tasks")):
            task_key = _stable_key(_payload_value(item, "taskKey", "task_key"))
            if not task_key:
                continue
            source_block_key = _stable_key(_payload_value(item, "sourceBlockKey", "source_block_key"))
            block = blocks_by_key.get(source_block_key)
            row = ReviewTask(
                review_task_run_id=run.id,
                course_id=run.course_id,
                task_key=task_key,
                task_type=str(_payload_value(item, "taskType", "task_type", default="revisit_block")),
                priority_score=int(_payload_value(item, "priorityScore", "priority_score", default=0)),
                reason_text=str(_payload_value(item, "reasonText", "reason_text", default="建议复习该知识点。")),
                recommended_minutes=int(_payload_value(item, "recommendedMinutes", "recommended_minutes", default=10)),
                knowledge_point_key=_stable_key(_payload_value(item, "knowledgePointKey", "knowledge_point_key")) or None,
                source_block_key=source_block_key or None,
                source_question_keys_json=list(
                    _payload_value(item, "sourceQuestionKeys", "source_question_keys", default=[]) or []
                ),
                source_segment_keys_json=list(
                    _payload_value(item, "sourceSegmentKeys", "source_segment_keys", default=[]) or []
                ),
                recommended_action_json=_payload_value(item, "recommendedAction", "recommended_action"),
                recommended_segment_json=_recommended_segment(block),
                practice_entry_json=self._practice_entry_for_review_run(run),
                review_order=int(_payload_value(item, "reviewOrder", "review_order", default=len(task_rows) + 1)),
                intensity=_intensity(int(_payload_value(item, "priorityScore", "priority_score", default=0))),
                status="pending",
            )
            self.session.add(row)
            task_rows[task_key] = row
        self.session.flush()

        for ref in refs:
            task_key = _stable_key(_payload_value(ref, "taskKey", "task_key"))
            task = task_rows.get(task_key)
            if task is None:
                continue
            self.session.add(
                ReviewTaskRef(
                    review_task_id=task.id,
                    resource_id=int(ref["resourceId"]),
                    segment_id=ref.get("segmentId"),
                    ref_type=str(ref["refType"]),
                    quote_text=ref.get("quoteText"),
                    page_no=ref.get("pageNo"),
                    slide_no=ref.get("slideNo"),
                    anchor_key=ref.get("anchorKey"),
                    start_sec=ref.get("startSec"),
                    end_sec=ref.get("endSec"),
                    bbox_json=ref.get("bboxJson"),
                    ref_label=str(ref.get("refLabel") or ref.get("segmentKey") or "来源片段"),
                    sort_no=int(ref["sortNo"]),
                )
            )

        run.status = "ready"
        run.generated_count = len(task_rows)
        run.payload_json = _json_ready(payload)
        run.error_code = None
        run.error_message = None
        run.finished_at = utcnow()
        self._commit_or_flush()
        return _review_run_dict(run)

    def list_daily_recommended_knowledge_points(self, *, limit: int = 3) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(MasteryRecord)
            .join(Course, Course.id == MasteryRecord.course_id)
            .where(MasteryRecord.user_id == self.user_id, Course.user_id == self.user_id)
            .order_by(MasteryRecord.review_priority.desc(), MasteryRecord.updated_at.desc(), MasteryRecord.id.desc())
            .limit(limit)
        ).all()
        return [
            {
                "knowledgePoint": row.knowledge_point,
                "reason": _mastery_recommendation_reason(row),
                "targetCourseId": row.course_id,
            }
            for row in rows
        ]

    def get_learning_stats(self) -> dict[str, Any]:
        completed_courses = self.session.scalar(
            select(func.count(Course.id)).where(
                Course.user_id == self.user_id,
                Course.lifecycle_status.in_(("learning_ready", "completed")),
            )
        ) or 0
        review_tasks_completed = self.session.scalar(
            select(func.count(ReviewTask.id))
            .join(Course, Course.id == ReviewTask.course_id)
            .where(Course.user_id == self.user_id, ReviewTask.status == "completed")
        ) or 0
        completed_review_minutes = self.session.scalar(
            select(func.coalesce(func.sum(ReviewTask.recommended_minutes), 0))
            .join(Course, Course.id == ReviewTask.course_id)
            .where(Course.user_id == self.user_id, ReviewTask.status == "completed")
        ) or 0
        progress_positions_sec = self.session.scalar(
            select(func.coalesce(func.sum(UserCourseProgress.last_position_sec), 0))
            .join(Course, Course.id == UserCourseProgress.course_id)
            .where(UserCourseProgress.user_id == self.user_id, Course.user_id == self.user_id)
        ) or 0
        activity_times = self.session.scalars(
            select(UserCourseProgress.last_activity_at)
            .join(Course, Course.id == UserCourseProgress.course_id)
            .where(UserCourseProgress.user_id == self.user_id, Course.user_id == self.user_id)
            .order_by(UserCourseProgress.last_activity_at.desc())
        ).all()
        return {
            "streakDays": _learning_streak(activity_times),
            "completedCourses": int(completed_courses),
            "reviewTasksCompleted": int(review_tasks_completed),
            "totalLearningMinutes": int(completed_review_minutes) + int(progress_positions_sec // 60),
        }

    def get_progress(self, course_id: int) -> dict[str, Any]:
        progress = self.session.scalar(
            select(UserCourseProgress)
            .join(Course, Course.id == UserCourseProgress.course_id)
            .where(
                UserCourseProgress.user_id == self.user_id,
                UserCourseProgress.course_id == course_id,
                Course.user_id == self.user_id,
            )
        )
        if progress is None:
            return {"courseId": course_id, "lastActivityAt": utcnow()}
        return _progress_dict(progress)

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        course = self._get_course_model(course_id)
        if course is None:
            raise ValueError(f"Course {course_id} was not found.")
        progress = self.session.scalar(
            select(UserCourseProgress).where(
                UserCourseProgress.user_id == self.user_id,
                UserCourseProgress.course_id == course_id,
            )
        )
        now = utcnow()
        changes = _progress_changes(payload)
        self._validate_progress_references(course_id=course_id, changes=changes)
        if progress is None:
            progress = UserCourseProgress(
                user_id=self.user_id,
                course_id=course_id,
                last_activity_at=now,
                **changes,
            )
            self.session.add(progress)
        else:
            for attr, value in changes.items():
                setattr(progress, attr, value)
            progress.last_activity_at = now
        course.updated_at = now
        self._commit_or_flush()
        return _progress_dict(progress)

    def _validate_progress_references(self, *, course_id: int, changes: dict[str, Any]) -> None:
        checks = (
            ("handout_version_id", self._progress_handout_version_belongs_to_course, "handout version"),
            ("last_handout_block_id", self._progress_handout_block_belongs_to_course, "handout block"),
            ("last_video_resource_id", self._progress_resource_belongs_to_course, "video resource"),
            ("last_doc_resource_id", self._progress_resource_belongs_to_course, "document resource"),
        )
        for attr, belongs_to_course, label in checks:
            if attr not in changes or changes[attr] is None:
                continue
            reference_id = _as_positive_int(changes[attr])
            if reference_id is None or not belongs_to_course(course_id, reference_id):
                raise ValueError(f"Progress {label} does not belong to the course.")
            changes[attr] = reference_id

        version_id = changes.get("handout_version_id")
        block_id = changes.get("last_handout_block_id")
        if version_id is not None and block_id is not None and not self._progress_block_belongs_to_version(
            int(block_id),
            int(version_id),
        ):
            raise ValueError("Progress handout block does not belong to the handout version.")

    def _progress_handout_version_belongs_to_course(self, course_id: int, handout_version_id: int) -> bool:
        return (
            self.session.scalar(
                select(HandoutVersion.id)
                .join(Course, Course.id == HandoutVersion.course_id)
                .where(
                    HandoutVersion.id == handout_version_id,
                    HandoutVersion.course_id == course_id,
                    Course.id == course_id,
                    Course.user_id == self.user_id,
                    Course.active_handout_version_id == HandoutVersion.id,
                    Course.active_parse_run_id == HandoutVersion.source_parse_run_id,
                )
            )
            is not None
        )

    def _progress_handout_block_belongs_to_course(self, course_id: int, handout_block_id: int) -> bool:
        return (
            self.session.scalar(
                select(HandoutBlock.id)
                .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
                .join(Course, Course.id == HandoutVersion.course_id)
                .where(
                    HandoutBlock.id == handout_block_id,
                    HandoutVersion.course_id == course_id,
                    Course.id == course_id,
                    Course.user_id == self.user_id,
                    Course.active_handout_version_id == HandoutBlock.handout_version_id,
                    Course.active_parse_run_id == HandoutVersion.source_parse_run_id,
                )
            )
            is not None
        )

    def _progress_block_belongs_to_version(self, handout_block_id: int, handout_version_id: int) -> bool:
        return (
            self.session.scalar(
                select(HandoutBlock.id)
                .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
                .join(Course, Course.id == HandoutVersion.course_id)
                .where(
                    HandoutBlock.id == handout_block_id,
                    HandoutBlock.handout_version_id == handout_version_id,
                    Course.user_id == self.user_id,
                )
            )
            is not None
        )

    def _progress_resource_belongs_to_course(self, course_id: int, resource_id: int) -> bool:
        return (
            self.session.scalar(
                select(CourseResource.id)
                .join(Course, Course.id == CourseResource.course_id)
                .where(
                    CourseResource.id == resource_id,
                    CourseResource.course_id == course_id,
                    Course.user_id == self.user_id,
                )
            )
            is not None
        )

    def _clear_course_progress_handout_refs(self, course_id: int) -> None:
        rows = self.session.scalars(
            select(UserCourseProgress).where(UserCourseProgress.course_id == course_id)
        ).all()
        for row in rows:
            row.handout_version_id = None
            row.last_handout_block_id = None
            row.last_anchor_key = None

    def _latest_active_review_run(self, course_id: int) -> ReviewTaskRun | None:
        latest_run_id = self._latest_active_review_run_id(course_id, statuses=("ready",))
        if latest_run_id is None:
            return None
        return self.session.get(ReviewTaskRun, latest_run_id)

    def _latest_active_review_run_id(self, course_id: int, *, statuses: tuple[str, ...]) -> int | None:
        if not statuses:
            return None
        return self.session.scalar(
            select(func.max(ReviewTaskRun.id))
            .join(Course, Course.id == ReviewTaskRun.course_id)
            .join(QuizAttempt, QuizAttempt.id == ReviewTaskRun.source_quiz_attempt_id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                ReviewTaskRun.user_id == self.user_id,
                ReviewTaskRun.course_id == course_id,
                ReviewTaskRun.status.in_(statuses),
                Course.user_id == self.user_id,
                Course.active_parse_run_id == Quiz.source_parse_run_id,
                Course.active_handout_version_id == Quiz.handout_version_id,
            )
        )

    def _supersede_pending_review_tasks_before(self, *, run_id: int, course_id: int) -> None:
        previous_tasks = self.session.scalars(
            select(ReviewTask).where(
                ReviewTask.course_id == course_id,
                ReviewTask.review_task_run_id < run_id,
                ReviewTask.status == "pending",
            )
        ).all()
        for previous_task in previous_tasks:
            previous_task.status = "superseded"

    def _review_run_can_publish(self, run: ReviewTaskRun) -> bool:
        latest_run_id = self.session.scalar(
            select(func.max(ReviewTaskRun.id))
            .join(Course, Course.id == ReviewTaskRun.course_id)
            .join(QuizAttempt, QuizAttempt.id == ReviewTaskRun.source_quiz_attempt_id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                ReviewTaskRun.user_id == self.user_id,
                ReviewTaskRun.course_id == run.course_id,
                ReviewTaskRun.id >= run.id,
                Course.user_id == self.user_id,
                Course.active_parse_run_id == Quiz.source_parse_run_id,
                Course.active_handout_version_id == Quiz.handout_version_id,
            )
        )
        return latest_run_id == run.id

    def _list_mastery_record_dicts(self, *, course_id: int) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(MasteryRecord)
            .where(MasteryRecord.user_id == self.user_id, MasteryRecord.course_id == course_id)
            .order_by(MasteryRecord.id.asc())
        ).all()
        return [_mastery_record_dict(row) for row in rows]

    def _upsert_mastery_records(
        self,
        *,
        course_id: int,
        attempt_id: int,
        updates: Sequence[Mapping[str, Any]],
        result_items: Sequence[Mapping[str, Any]],
    ) -> None:
        source_block_by_kp: dict[str, str] = {}
        for item in result_items:
            kp_key = _stable_key(_payload_value(item, "knowledgePointKey", "knowledge_point_key"))
            block_key = _stable_key(_payload_value(item, "sourceBlockKey", "source_block_key"))
            if kp_key and block_key:
                source_block_by_kp.setdefault(kp_key, block_key)

        existing = {
            row.knowledge_point_key: row
            for row in self.session.scalars(
                select(MasteryRecord).where(
                    MasteryRecord.user_id == self.user_id,
                    MasteryRecord.course_id == course_id,
                )
            ).all()
        }
        for update in updates:
            kp_key = _stable_key(_payload_value(dict(update), "knowledgePointKey", "knowledge_point_key"))
            if not kp_key:
                continue
            current = existing.get(kp_key)
            fields = {
                "last_quiz_attempt_id": attempt_id,
                "knowledge_point": str(_payload_value(dict(update), "knowledgePoint", "knowledge_point", default=kp_key)),
                "mastery_score": float(_payload_value(dict(update), "nextMasteryScore", "next_mastery_score", default=0.5)),
                "confidence_score": float(
                    _payload_value(dict(update), "nextConfidenceScore", "next_confidence_score", default=0.3)
                ),
                "correct_count": int(_payload_value(dict(update), "correctCountDelta", "correct_count_delta", default=0)),
                "wrong_count": int(_payload_value(dict(update), "wrongCountDelta", "wrong_count_delta", default=0)),
                "review_priority": int(_payload_value(dict(update), "reviewPriority", "review_priority", default=0)),
                "status": str(_payload_value(dict(update), "status", default="unchanged")),
                "source_question_keys_json": list(
                    _payload_value(dict(update), "sourceQuestionKeys", "source_question_keys", default=[]) or []
                ),
                "source_block_key": source_block_by_kp.get(kp_key),
            }
            if current is None:
                self.session.add(
                    MasteryRecord(
                        user_id=self.user_id,
                        course_id=course_id,
                        knowledge_point_key=kp_key,
                        **fields,
                    )
                )
                continue
            current.last_quiz_attempt_id = attempt_id
            current.knowledge_point = fields["knowledge_point"]
            current.mastery_score = fields["mastery_score"]
            current.confidence_score = fields["confidence_score"]
            current.correct_count += fields["correct_count"]
            current.wrong_count += fields["wrong_count"]
            current.review_priority = fields["review_priority"]
            current.status = fields["status"]
            current.source_question_keys_json = fields["source_question_keys_json"]
            current.source_block_key = fields["source_block_key"] or current.source_block_key

    def _active_handout_blocks_for_course(self, course_id: int) -> list[HandoutBlock]:
        version = self._get_latest_handout_version_model(course_id)
        if version is None:
            return []
        return list(
            self.session.scalars(
                select(HandoutBlock)
                .where(HandoutBlock.handout_version_id == version.id, HandoutBlock.status == "ready")
                .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
            ).all()
        )

    def _practice_entry_for_review_run(self, run: ReviewTaskRun) -> dict[str, object] | None:
        if run.source_quiz_attempt_id is None:
            return None
        attempt = self.session.get(QuizAttempt, run.source_quiz_attempt_id)
        if attempt is None:
            return None
        return {
            "type": "quiz",
            "targetId": attempt.quiz_id,
            "label": "再练 1 题",
        }

    def _get_user_handout_block(self, block_id: int) -> HandoutBlock | None:
        return self.session.scalar(
            select(HandoutBlock)
            .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
            .join(Course, Course.id == HandoutVersion.course_id)
            .where(HandoutBlock.id == block_id, Course.user_id == self.user_id)
        )

    def _get_active_quiz_model(self, quiz_id: int) -> Quiz | None:
        return self.session.scalar(
            select(Quiz)
            .join(Course, Course.id == Quiz.course_id)
            .where(
                Quiz.id == quiz_id,
                Course.user_id == self.user_id,
                Course.active_handout_version_id == Quiz.handout_version_id,
                Course.active_parse_run_id == Quiz.source_parse_run_id,
            )
        )

    def _get_active_handout_block(self, block_id: int) -> HandoutBlock | None:
        return self.session.scalar(
            select(HandoutBlock)
            .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
            .join(Course, Course.id == HandoutVersion.course_id)
            .where(
                HandoutBlock.id == block_id,
                Course.user_id == self.user_id,
                Course.active_handout_version_id == HandoutBlock.handout_version_id,
                HandoutVersion.source_parse_run_id == Course.active_parse_run_id,
            )
        )

    def _qa_context_is_active(
        self,
        *,
        course_id: int,
        parse_run_id: int,
        handout_version_id: int,
        handout_block_id: int,
    ) -> bool:
        return (
            self.session.scalar(
                select(HandoutBlock.id)
                .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
                .join(Course, Course.id == HandoutVersion.course_id)
                .where(
                    Course.id == course_id,
                    Course.user_id == self.user_id,
                    Course.active_parse_run_id == parse_run_id,
                    Course.active_handout_version_id == handout_version_id,
                    HandoutVersion.id == handout_version_id,
                    HandoutVersion.course_id == course_id,
                    HandoutVersion.source_parse_run_id == parse_run_id,
                    HandoutBlock.id == handout_block_id,
                    HandoutBlock.handout_version_id == handout_version_id,
                )
            )
            is not None
        )

    def _current_handout_block_task(self, block: HandoutBlock) -> AsyncTask | None:
        return self.session.scalars(
            select(AsyncTask)
            .where(
                AsyncTask.course_id == self.session.scalar(
                    select(HandoutVersion.course_id).where(HandoutVersion.id == block.handout_version_id)
                ),
                AsyncTask.task_type == "handout_block_generate",
                AsyncTask.target_type == "handout_block",
                AsyncTask.target_id == block.id,
                AsyncTask.status.in_(("queued", "running", "retrying")),
            )
            .order_by(AsyncTask.id.desc())
        ).first()

    def _qa_segments(self, *, course_id: int, parse_run_id: int) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(CourseSegment)
            .where(
                CourseSegment.course_id == course_id,
                CourseSegment.parse_run_id == parse_run_id,
                CourseSegment.is_active.is_(True),
            )
            .order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
        ).all()
        return [_course_segment_dict(row) | {"resourceType": self._resource_type(row.resource_id)} for row in rows]

    def _qa_block_payload(
        self,
        block: HandoutBlock,
        *,
        course: Course,
        version: HandoutVersion,
    ) -> dict[str, Any]:
        return {
            "courseId": course.id,
            "parseRunId": course.active_parse_run_id,
            "handoutVersionId": version.id,
            "handoutBlockId": block.id,
            "outlineKey": block.outline_key,
            "sortNo": block.sort_no,
            "title": block.title,
            "summary": block.summary,
            "contentMd": block.content_md,
            "knowledgePoints": block.knowledge_points_json or [],
            "citations": block.citations_json or [],
        }

    def _qa_adjacent_blocks(
        self,
        block: HandoutBlock,
        *,
        course: Course,
        version: HandoutVersion,
        vector_documents: Sequence[VectorDocument],
    ) -> list[dict[str, Any]]:
        adjacent_sort_nos = {block.sort_no - 1, block.sort_no + 1}
        vector_by_owner_id = {
            int(document.owner_id): document
            for document in vector_documents
            if document.owner_type == "handout_block"
            and document.handout_version_id == version.id
            and document.parse_run_id == course.active_parse_run_id
        }
        rows = self.session.scalars(
            select(HandoutBlock)
            .where(
                HandoutBlock.handout_version_id == version.id,
                HandoutBlock.id != block.id,
                HandoutBlock.sort_no.in_(adjacent_sort_nos),
                HandoutBlock.status == "ready",
            )
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            payload = self._qa_block_payload(row, course=course, version=version)
            vector_document = vector_by_owner_id.get(row.id)
            if vector_document is not None:
                payload["contentMd"] = vector_document.content_text
            payloads.append(payload)
        return payloads

    def _active_handout_block_vectors(self, *, course: Course, version: HandoutVersion) -> list[VectorDocument]:
        if course.active_parse_run_id is None:
            return []
        return list(
            self.session.scalars(
                select(VectorDocument)
                .where(
                    VectorDocument.course_id == course.id,
                    VectorDocument.parse_run_id == course.active_parse_run_id,
                    VectorDocument.handout_version_id == version.id,
                    VectorDocument.owner_type == "handout_block",
                )
                .order_by(VectorDocument.id.asc())
            ).all()
        )

    def _qa_message_dict(self, message: QaMessage, *, generation_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        refs = []
        if message.role == "assistant":
            ref_rows = self.session.scalars(
                select(QaMessageRef)
                .where(QaMessageRef.qa_message_id == message.id)
                .order_by(QaMessageRef.sort_no.asc(), QaMessageRef.id.asc())
            ).all()
            refs = [_qa_public_citation(row) for row in ref_rows]
        payload = {
            "sessionId": message.session_id,
            "messageId": message.id,
            "role": message.role,
            "contentMd": message.content_md,
            "answerMd": message.content_md if message.role == "assistant" else None,
            "answerType": message.answer_type,
            "citations": refs,
        }
        if message.role == "assistant" and generation_metadata:
            payload["generationMetadata"] = generation_metadata
        return payload

    def _resource_type(self, resource_id: int) -> str | None:
        resource = self.session.get(CourseResource, resource_id)
        return resource.resource_type if resource is not None else None

    def _get_course_model(self, course_id: int) -> Course | None:
        return self.session.scalar(
            select(Course).where(Course.id == course_id, Course.user_id == self.user_id)
        )

    def _get_handout_version_model(self, handout_version_id: int) -> HandoutVersion | None:
        return self.session.scalar(
            select(HandoutVersion)
            .join(Course, Course.id == HandoutVersion.course_id)
            .where(HandoutVersion.id == handout_version_id, Course.user_id == self.user_id)
        )

    def _get_latest_handout_version_model(self, course_id: int) -> HandoutVersion | None:
        course = self._get_course_model(course_id)
        if course is None:
            return None
        if course.active_handout_version_id is not None:
            version = self._get_handout_version_model(course.active_handout_version_id)
            if version is not None and version.source_parse_run_id == course.active_parse_run_id:
                return version
        return None

    def _list_active_video_caption_segments(
        self,
        *,
        course_id: int,
        parse_run_id: int,
    ) -> list[CourseSegment]:
        return list(
            self.session.scalars(
                select(CourseSegment)
                .where(
                    CourseSegment.course_id == course_id,
                    CourseSegment.parse_run_id == parse_run_id,
                    CourseSegment.segment_type == "video_caption",
                    CourseSegment.is_active.is_(True),
                )
                .order_by(
                    CourseSegment.start_sec.asc(),
                    CourseSegment.order_no.asc(),
                    CourseSegment.id.asc(),
                )
            ).all()
        )

    def _list_active_outline_document_segments(
        self,
        *,
        course_id: int,
        parse_run_id: int,
    ) -> list[CourseSegment]:
        return list(
            self.session.scalars(
                select(CourseSegment)
                .where(
                    CourseSegment.course_id == course_id,
                    CourseSegment.parse_run_id == parse_run_id,
                    CourseSegment.segment_type.in_(OUTLINE_DOCUMENT_CONTEXT_TYPES),
                    CourseSegment.is_active.is_(True),
                )
                .order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
            ).all()
        )

    def _list_handout_blocks(self, handout_version_id: int) -> list[dict[str, Any]]:
        blocks = self.session.scalars(
            select(HandoutBlock)
            .where(HandoutBlock.handout_version_id == handout_version_id)
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
        return [_handout_block_dict(block) for block in blocks]

    def _normalize_handout_block_refs(
        self,
        *,
        block: HandoutBlock,
        version: HandoutVersion,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raw_citations = _payload_value(payload, "citations", default=[])
        if not isinstance(raw_citations, list):
            return []
        candidate_segment_ids = self._handout_block_candidate_segment_ids(block=block, version=version)
        refs: list[dict[str, Any]] = []
        seen: set[tuple[int, int | None, tuple[tuple[str, Any], ...]]] = set()
        for raw_item in raw_citations:
            if not isinstance(raw_item, dict):
                continue
            segment = self._segment_for_handout_citation(
                raw_item,
                course_id=version.course_id,
                parse_run_id=version.source_parse_run_id,
            )
            if segment is None:
                continue
            if segment.id not in candidate_segment_ids:
                continue
            locator = _locator_for_handout_ref(raw_item, segment, block=block)
            if not locator:
                continue
            resource_id = _as_positive_int(_payload_value(raw_item, "resourceId", "resource_id")) or segment.resource_id
            if resource_id != segment.resource_id:
                continue
            identity = (resource_id, segment.id, _locator_tuple(locator))
            if identity in seen:
                continue
            seen.add(identity)
            refs.append(
                {
                    "resourceId": resource_id,
                    "segmentId": segment.id,
                    "segmentKey": _segment_source_key(segment),
                    "refType": _ref_type(locator),
                    "quoteText": _truncate_text(segment.text_content or segment.plain_text, 300),
                    "refLabel": _ref_label(raw_item, segment, locator),
                    "sortNo": len(refs) + 1,
                    **locator,
                }
            )
        return refs

    def _handout_block_candidate_segment_ids(
        self,
        *,
        block: HandoutBlock,
        version: HandoutVersion,
    ) -> set[int]:
        source_ids = {
            segment_id
            for segment_id in (
                _segment_id_from_source_key(str(source_key))
                for source_key in block.source_segment_keys_json or []
            )
            if segment_id is not None
        }
        if version.source_parse_run_id is None or not source_ids:
            return source_ids

        source_segments = [
            segment
            for segment in (
                self.session.get(CourseSegment, segment_id)
                for segment_id in source_ids
            )
            if segment is not None
            and segment.course_id == version.course_id
            and segment.parse_run_id == version.source_parse_run_id
            and segment.is_active
        ]
        candidate_ids = {segment.id for segment in source_segments}
        if not source_segments:
            return candidate_ids

        min_start = min(
            (segment.start_sec for segment in source_segments if segment.start_sec is not None),
            default=None,
        )
        max_end = max(
            (segment.end_sec for segment in source_segments if segment.end_sec is not None),
            default=None,
        )
        source_tokens = _segment_keyword_tokens(source_segments)

        for segment in self.session.scalars(
            select(CourseSegment)
            .where(
                CourseSegment.course_id == version.course_id,
                CourseSegment.parse_run_id == version.source_parse_run_id,
                CourseSegment.is_active.is_(True),
            )
            .order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
        ).all():
            if segment.id in candidate_ids:
                continue
            if segment.segment_type == "video_caption":
                if _video_segment_near_range(segment, min_start=min_start, max_end=max_end):
                    candidate_ids.add(segment.id)
                continue
            if not source_tokens or source_tokens & _text_tokens(segment.text_content or segment.plain_text):
                candidate_ids.add(segment.id)
        return candidate_ids

    def _segment_for_handout_citation(
        self,
        citation: dict[str, Any],
        *,
        course_id: int,
        parse_run_id: int | None,
    ) -> CourseSegment | None:
        stmt = select(CourseSegment).where(
            CourseSegment.course_id == course_id,
            CourseSegment.is_active.is_(True),
        )
        if parse_run_id is not None:
            stmt = stmt.where(CourseSegment.parse_run_id == parse_run_id)

        segment_id = _as_positive_int(_payload_value(citation, "segmentId", "segment_id"))
        if segment_id is not None:
            return self.session.scalar(stmt.where(CourseSegment.id == segment_id))

        segment_key = _payload_value(citation, "segmentKey", "segment_key")
        if isinstance(segment_key, str):
            parsed_segment_id = _segment_id_from_source_key(segment_key)
            if parsed_segment_id is not None:
                return self.session.scalar(stmt.where(CourseSegment.id == parsed_segment_id))

        resource_id = _as_positive_int(_payload_value(citation, "resourceId", "resource_id"))
        locator = _raw_locator(citation)
        if resource_id is None or not locator:
            return None
        for segment in self.session.scalars(stmt.where(CourseSegment.resource_id == resource_id)).all():
            if _locator_tuple(_segment_locator(segment)) == _locator_tuple(locator):
                return segment
        return None

    def _refresh_handout_version_status(self, version: HandoutVersion) -> None:
        blocks = self.session.scalars(
            select(HandoutBlock).where(HandoutBlock.handout_version_id == version.id)
        ).all()
        ready_blocks = sum(1 for block in blocks if block.status == "ready")
        pending_blocks = sum(1 for block in blocks if block.status in {"pending", "generating"})
        failed_blocks = sum(1 for block in blocks if block.status == "failed")
        version.ready_blocks = ready_blocks
        version.pending_blocks = pending_blocks
        if blocks and ready_blocks == len(blocks):
            version.status = "ready"
        elif failed_blocks and pending_blocks == 0:
            version.status = "partial_success" if ready_blocks else "failed"
        elif version.outline_status == "ready":
            version.status = "outline_ready"

    def _commit_or_flush(self) -> None:
        try:
            self.session.flush()
            if self._idempotency_depth == 0:
                self.session.commit()
        except Exception:
            self.session.rollback()
            raise


def _course_dict(course: Course) -> dict[str, Any]:
    return {
        "courseId": course.id,
        "title": course.title,
        "entryType": course.entry_type,
        "catalogId": course.catalog_id,
        "goalText": course.goal_text,
        "examAt": _normalize_utc_datetime(course.exam_at),
        "preferredStyle": course.preferred_style,
        "lifecycleStatus": course.lifecycle_status,
        "pipelineStage": course.pipeline_stage,
        "pipelineStatus": course.pipeline_status,
        "activeParseRunId": course.active_parse_run_id,
        "activeHandoutVersionId": course.active_handout_version_id,
        "updatedAt": course.updated_at,
    }


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_datetime_change(column_name: str, value: Any) -> Any:
    if column_name.endswith("_at") and isinstance(value, datetime):
        return _normalize_utc_datetime(value)
    return value


def _bilibili_qr_session_dict(qr_session: BilibiliQrSession) -> dict[str, Any]:
    return {
        "qrSessionId": qr_session.id,
        "qrKey": qr_session.qr_key,
        "qrUrl": qr_session.qr_url,
        "status": qr_session.status,
        "pollPayloadJson": qr_session.poll_payload_json,
        "errorCode": qr_session.error_code,
        "failureReason": qr_session.failure_reason,
        "scannedAt": _normalize_utc_datetime(qr_session.scanned_at),
        "confirmedAt": _normalize_utc_datetime(qr_session.confirmed_at),
        "expiresAt": _normalize_utc_datetime(qr_session.expires_at),
        "createdAt": _normalize_utc_datetime(qr_session.created_at),
        "updatedAt": _normalize_utc_datetime(qr_session.updated_at),
    }


def _bilibili_auth_session_dict(auth_session: BilibiliAuthSession) -> dict[str, Any]:
    return {
        "authSessionId": auth_session.id,
        "status": auth_session.status,
        "cookiesJson": auth_session.cookies_json,
        "csrf": auth_session.csrf,
        "expiresAt": _normalize_utc_datetime(auth_session.expires_at),
        "lastVerifiedAt": _normalize_utc_datetime(auth_session.last_verified_at),
        "errorCode": auth_session.error_code,
        "failureReason": auth_session.failure_reason,
        "createdAt": _normalize_utc_datetime(auth_session.created_at),
        "updatedAt": _normalize_utc_datetime(auth_session.updated_at),
    }


def _bilibili_import_run_dict(import_run: BilibiliImportRun) -> dict[str, Any]:
    return {
        "importRunId": import_run.id,
        "courseId": import_run.course_id,
        "taskId": import_run.task_id,
        "sourceUrl": import_run.source_url,
        "sourceType": import_run.source_type,
        "status": import_run.status,
        "stage": import_run.stage,
        "progressPct": import_run.progress_pct,
        "preview": import_run.preview_json,
        "selection": import_run.selection_json,
        "resourceIds": import_run.resource_ids_json or [],
        "recoverable": import_run.recoverable,
        "tempDir": import_run.temp_dir,
        "errorCode": import_run.error_code,
        "failureReason": import_run.failure_reason,
        "startedAt": _normalize_utc_datetime(import_run.started_at),
        "finishedAt": _normalize_utc_datetime(import_run.finished_at),
        "createdAt": _normalize_utc_datetime(import_run.created_at),
        "updatedAt": _normalize_utc_datetime(import_run.updated_at),
    }


def _resource_dict(resource: CourseResource) -> dict[str, Any]:
    return {
        "resourceId": resource.id,
        "courseId": resource.course_id,
        "resourceType": resource.resource_type,
        "sourceType": resource.source_type,
        "originUrl": resource.origin_url,
        "objectKey": resource.object_key,
        "previewKey": resource.preview_key,
        "originalName": resource.original_name,
        "mimeType": resource.mime_type,
        "sizeBytes": resource.size_bytes,
        "checksum": resource.checksum,
        "ingestStatus": resource.ingest_status,
        "validationStatus": resource.validation_status,
        "processingStatus": resource.processing_status,
        "lastParseRunId": resource.last_parse_run_id,
        "lastError": resource.last_error,
        "sortOrder": resource.sort_order,
    }


def _parse_run_dict(parse_run: ParseRun) -> dict[str, Any]:
    return {
        "parseRunId": parse_run.id,
        "courseId": parse_run.course_id,
        "status": parse_run.status,
        "triggerType": parse_run.trigger_type,
        "sourceParseRunId": parse_run.source_parse_run_id,
        "progressPct": parse_run.progress_pct,
        "summaryJson": parse_run.summary_json,
        "startedAt": parse_run.started_at or parse_run.created_at,
        "finishedAt": parse_run.finished_at,
        "createdAt": parse_run.created_at,
    }


def _async_trigger_dict(task: AsyncTask, entity_type: str, entity_id: int) -> dict[str, Any]:
    return {
        "taskId": task.id,
        "status": task.status,
        "nextAction": "poll" if task.status in {"queued", "running"} else "none",
        "entity": {"type": entity_type, "id": entity_id},
    }


def _async_task_dict(task: AsyncTask) -> dict[str, Any]:
    return {
        "taskId": task.id,
        "courseId": task.course_id,
        "parseRunId": task.parse_run_id,
        "resourceId": task.resource_id,
        "taskType": task.task_type,
        "status": task.status,
        "parentTaskId": task.parent_task_id,
        "targetType": task.target_type,
        "targetId": task.target_id,
        "stepCode": task.step_code,
        "progressPct": task.progress_pct,
        "payloadJson": task.payload_json,
        "resultJson": task.result_json,
        "errorCode": task.error_code,
        "errorMessage": task.error_message,
        "retryCount": task.retry_count,
        "startedAt": task.started_at,
        "finishedAt": task.finished_at,
        "createdAt": task.created_at,
        "updatedAt": task.updated_at,
    }


def _quiz_dict(quiz: Quiz, *, questions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "quizId": quiz.id,
        "courseId": quiz.course_id,
        "status": quiz.status,
        "questionCount": quiz.question_count,
        "questions": list(questions),
    }


def _quiz_question_public_dict(question: QuizQuestion) -> dict[str, Any]:
    return {
        "questionId": question.id,
        "stemMd": question.stem_md,
        "options": list(question.options_json or []),
    }


def _quiz_question_private_dict(question: QuizQuestion) -> dict[str, Any]:
    return {
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


def _mastery_record_dict(record: MasteryRecord) -> dict[str, Any]:
    return {
        "knowledgePointKey": record.knowledge_point_key,
        "knowledgePoint": record.knowledge_point,
        "masteryScore": record.mastery_score,
        "confidenceScore": record.confidence_score,
        "correctCount": record.correct_count,
        "wrongCount": record.wrong_count,
        "reviewPriority": record.review_priority,
        "status": record.status,
        "sourceQuestionKeys": list(record.source_question_keys_json or []),
        "sourceBlockKey": record.source_block_key,
    }


def _review_run_dict(run: ReviewTaskRun) -> dict[str, Any]:
    return {
        "reviewTaskRunId": run.id,
        "courseId": run.course_id,
        "status": run.status,
        "generatedCount": run.generated_count,
    }


def _review_task_dict(task: ReviewTask) -> dict[str, Any]:
    return {
        "reviewTaskId": task.id,
        "taskType": task.task_type,
        "priorityScore": task.priority_score,
        "reasonText": task.reason_text,
        "recommendedMinutes": task.recommended_minutes,
        "recommendedSegment": task.recommended_segment_json,
        "practiceEntry": task.practice_entry_json,
        "reviewOrder": task.review_order,
        "intensity": task.intensity,
    }


def _progress_dict(progress: UserCourseProgress) -> dict[str, Any]:
    return {
        "courseId": progress.course_id,
        "handoutVersionId": progress.handout_version_id,
        "lastHandoutBlockId": progress.last_handout_block_id,
        "lastVideoResourceId": progress.last_video_resource_id,
        "lastPositionSec": progress.last_position_sec,
        "lastDocResourceId": progress.last_doc_resource_id,
        "lastPageNo": progress.last_page_no,
        "lastSlideNo": progress.last_slide_no,
        "lastAnchorKey": progress.last_anchor_key,
        "lastActivityAt": _aware_datetime(progress.last_activity_at),
    }


def _progress_changes(payload: dict[str, Any]) -> dict[str, Any]:
    attr_map = {
        "handoutVersionId": "handout_version_id",
        "lastHandoutBlockId": "last_handout_block_id",
        "lastVideoResourceId": "last_video_resource_id",
        "lastPositionSec": "last_position_sec",
        "lastDocResourceId": "last_doc_resource_id",
        "lastPageNo": "last_page_no",
        "lastSlideNo": "last_slide_no",
        "lastAnchorKey": "last_anchor_key",
    }
    allowed = set(attr_map.values())
    changes: dict[str, Any] = {}
    for key, value in payload.items():
        attr = attr_map.get(key, key)
        if attr in allowed:
            changes[attr] = value
    return changes


def _mastery_recommendation_reason(record: MasteryRecord) -> str:
    percent = round(record.mastery_score * 100)
    if record.status in {"needs_review", "weak", "declining"} or record.review_priority >= 80:
        return f"掌握度约 {percent}%，建议今天优先回看。"
    if record.wrong_count > record.correct_count:
        return "最近测验错题较多，适合安排一次巩固练习。"
    return "最近测验建议继续巩固，保持复习节奏。"


def _learning_streak(activity_times: Sequence[datetime]) -> int:
    activity_days = sorted(
        {activity_day for value in activity_times if (activity_day := _activity_date(value)) is not None},
        reverse=True,
    )
    if not activity_days:
        return 0
    expected = min(utcnow().date(), activity_days[0])
    streak = 0
    for activity_day in activity_days:
        if activity_day == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif activity_day < expected:
            break
    return streak


def _activity_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    return _aware_datetime(value).date()


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _blocks_by_strategy_key(blocks: Sequence[HandoutBlock]) -> dict[str, HandoutBlock]:
    result: dict[str, HandoutBlock] = {}
    for index, block in enumerate(blocks, start=1):
        for key in (str(block.id), block.outline_key, f"block-{index}"):
            if key:
                result.setdefault(key, block)
    return result


def _recommended_segment(block: HandoutBlock | None) -> dict[str, object] | None:
    if block is None:
        return None
    return {
        "blockId": block.id,
        "startSec": block.start_sec,
        "endSec": block.end_sec,
        "label": "建议优先回看片段",
    }


def _intensity(priority_score: int) -> str:
    if priority_score >= 85:
        return "high"
    if priority_score >= 65:
        return "medium"
    return "low"


def _course_segment_dict(segment: CourseSegment) -> dict[str, Any]:
    return {
        "segmentId": segment.id,
        "segmentKey": _segment_source_key(segment),
        "courseId": segment.course_id,
        "resourceId": segment.resource_id,
        "parseRunId": segment.parse_run_id,
        "segmentType": segment.segment_type,
        "title": segment.title,
        "sectionPath": segment.section_path or [],
        "textContent": segment.text_content,
        "plainText": segment.plain_text,
        "startSec": segment.start_sec,
        "endSec": segment.end_sec,
        "pageNo": segment.page_no,
        "slideNo": segment.slide_no,
        "imageKey": segment.image_key,
        "formulaText": segment.formula_text,
        "bboxJson": segment.bbox_json,
        "orderNo": segment.order_no,
        "tokenCount": segment.token_count,
        "isActive": segment.is_active,
    }


def _handout_version_dict(
    version: HandoutVersion,
    *,
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "handoutVersionId": version.id,
        "courseId": version.course_id,
        "title": version.title,
        "summary": version.summary,
        "status": version.status,
        "outlineStatus": version.outline_status,
        "totalBlocks": version.total_blocks,
        "readyBlocks": version.ready_blocks,
        "pendingBlocks": version.pending_blocks,
        "sourceParseRunId": version.source_parse_run_id,
        "errorCode": version.error_code,
        "errorMessage": version.error_message,
        "metaJson": version.meta_json or {},
        "blocks": blocks,
    }


def _handout_outline_dict(
    version: HandoutVersion,
    outline: HandoutOutline,
    blocks: Sequence[HandoutBlock],
) -> dict[str, Any]:
    blocks_by_key = {block.outline_key: block for block in blocks}
    payload = dict(outline.outline_json or {})
    items = []
    for raw_item in payload.get("items", []):
        if not isinstance(raw_item, dict):
            continue
        children = raw_item.get("children")
        if isinstance(children, list):
            item = {
                "outlineKey": raw_item.get("outlineKey"),
                "title": raw_item.get("title"),
                "summary": raw_item.get("summary"),
                "startSec": raw_item.get("startSec"),
                "endSec": raw_item.get("endSec"),
                "sortNo": raw_item.get("sortNo"),
                "children": [
                    _outline_child_with_block(child, blocks_by_key)
                    for child in children
                    if isinstance(child, dict)
                ],
            }
            items.append(item)

    return {
        "handoutVersionId": version.id,
        "title": outline.title,
        "summary": outline.summary,
        "items": items,
    }


LEGACY_HANDOUT_BLOCK_GENERATION_METADATA = {"source": "fallback", "reason": "legacy_unknown"}


def _handout_block_generation_metadata(block: HandoutBlock) -> dict[str, Any] | None:
    if block.generation_metadata_json:
        return dict(block.generation_metadata_json)
    if block.status == "ready":
        return dict(LEGACY_HANDOUT_BLOCK_GENERATION_METADATA)
    return None


def _handout_block_dict(block: HandoutBlock) -> dict[str, Any]:
    payload = {
        "blockId": block.id,
        "handoutVersionId": block.handout_version_id,
        "outlineKey": block.outline_key,
        "title": block.title,
        "summary": block.summary,
        "status": block.status,
        "generationStatus": block.status,
        "contentMd": block.content_md,
        "startSec": block.start_sec,
        "endSec": block.end_sec,
        "sourceSegmentKeys": list(block.source_segment_keys_json or []),
        "knowledgePoints": block.knowledge_points_json or [],
        "citations": [_public_citation_from_ref(citation) for citation in block.citations_json or []],
    }
    generation_metadata = _handout_block_generation_metadata(block)
    if generation_metadata:
        payload["generationMetadata"] = generation_metadata
    return payload


def _handout_block_status_dict(block: HandoutBlock) -> dict[str, Any]:
    payload = {
        "blockId": block.id,
        "outlineKey": block.outline_key,
        "status": block.status,
        "generationStatus": block.status,
        "startSec": block.start_sec,
        "endSec": block.end_sec,
    }
    generation_metadata = _handout_block_generation_metadata(block)
    if generation_metadata:
        payload["generationMetadata"] = generation_metadata
    return payload


def _public_citation_from_ref(ref: dict[str, Any]) -> dict[str, Any]:
    citation = {
        "resourceId": ref.get("resourceId"),
        "refLabel": ref.get("refLabel"),
        "pageNo": ref.get("pageNo"),
        "slideNo": ref.get("slideNo"),
        "anchorKey": ref.get("anchorKey"),
        "startSec": ref.get("startSec"),
        "endSec": ref.get("endSec"),
    }
    return {key: value for key, value in citation.items() if value not in (None, "", [])}


def _qa_public_citation(ref: QaMessageRef) -> dict[str, Any]:
    citation = {
        "resourceId": ref.resource_id,
        "refLabel": ref.ref_label,
        "pageNo": ref.page_no,
        "slideNo": ref.slide_no,
        "anchorKey": ref.anchor_key,
        "startSec": ref.start_sec,
        "endSec": ref.end_sec,
    }
    return {key: value for key, value in citation.items() if value not in (None, "", [])}


def _generation_metadata_from_response(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    metadata = _payload_value(payload, "generationMetadata", "generation_metadata")
    if not isinstance(metadata, Mapping):
        return None
    source = metadata.get("source")
    reason = metadata.get("reason")
    if source not in {"model", "fallback"} or not isinstance(reason, str) or not reason.strip():
        return None
    return {"source": source, "reason": reason.strip()}


def _vector_document_dict(document: VectorDocument) -> dict[str, Any]:
    return {
        "vectorDocumentId": document.id,
        "courseId": document.course_id,
        "parseRunId": document.parse_run_id,
        "handoutVersionId": document.handout_version_id,
        "ownerType": document.owner_type,
        "ownerId": document.owner_id,
        "resourceId": document.resource_id,
        "contentText": document.content_text,
        "metadataJson": document.metadata_json,
        "embedding": document.embedding,
    }


def _async_task_changes(changes: dict[str, Any]) -> dict[str, Any]:
    attr_map = {
        "parseRunId": "parse_run_id",
        "resourceId": "resource_id",
        "parentTaskId": "parent_task_id",
        "targetType": "target_type",
        "targetId": "target_id",
        "stepCode": "step_code",
        "progressPct": "progress_pct",
        "payloadJson": "payload_json",
        "resultJson": "result_json",
        "errorCode": "error_code",
        "errorMessage": "error_message",
        "retryCount": "retry_count",
        "startedAt": "started_at",
        "finishedAt": "finished_at",
    }
    allowed = {
        "status",
        "parse_run_id",
        "resource_id",
        "parent_task_id",
        "target_type",
        "target_id",
        "step_code",
        "progress_pct",
        "payload_json",
        "result_json",
        "error_code",
        "error_message",
        "retry_count",
        "started_at",
        "finished_at",
    }
    normalized: dict[str, Any] = {}
    for key, value in changes.items():
        attr = attr_map.get(key, key)
        if attr in allowed:
            normalized[attr] = value
    return normalized


def _payload_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _stable_key(value: Any) -> str:
    return str(value or "").strip()


def _build_outline_from_caption_segments(
    *,
    course: Course,
    captions: Sequence[CourseSegment],
    max_block_duration_sec: int = 180,
) -> dict[str, Any] | None:
    clean_captions = [_caption_payload(segment) for segment in captions]
    clean_captions = [item for item in clean_captions if item is not None]
    clean_captions = _repair_caption_timeline(clean_captions)
    if not clean_captions:
        return None

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_start: int | None = None
    for caption in clean_captions:
        if not current_group:
            current_group = [caption]
            current_start = caption["startSec"]
            continue
        if caption["endSec"] - int(current_start) > max_block_duration_sec:
            groups.append(current_group)
            current_group = [caption]
            current_start = caption["startSec"]
        else:
            current_group.append(caption)
    if current_group:
        groups.append(current_group)

    items = [_outline_item_from_caption_group(group, index) for index, group in enumerate(groups, start=1)]
    items = _repair_outline_timeline(items)
    if not items:
        return None

    return {
        "title": course.title or "视频时间轴目录",
        "summary": "按视频时间线组织的讲义目录",
        "items": items,
    }


def _repair_caption_timeline(captions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    previous_end: int | None = None
    for caption in captions:
        item = dict(caption)
        if previous_end is not None and int(item["startSec"]) < previous_end:
            item["startSec"] = previous_end
        if int(item["endSec"]) <= int(item["startSec"]):
            continue
        repaired.append(item)
        previous_end = int(item["endSec"])
    return repaired


def _repair_outline_timeline(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    previous_end: int | None = None
    for item in items:
        next_item = dict(item)
        start_sec = int(next_item["startSec"])
        end_sec = int(next_item["endSec"])
        if previous_end is not None and start_sec < previous_end:
            start_sec = previous_end
        if end_sec <= start_sec:
            continue
        sort_no = len(repaired) + 1
        next_item["outlineKey"] = f"outline-{sort_no}"
        next_item["sortNo"] = sort_no
        next_item["startSec"] = start_sec
        next_item["endSec"] = end_sec
        repaired.append(next_item)
        previous_end = end_sec
    return repaired


def _caption_payload(segment: CourseSegment) -> dict[str, Any] | None:
    start_sec = _as_outline_int(segment.start_sec)
    end_sec = _as_outline_int(segment.end_sec)
    text = _compact_text(segment.text_content or segment.plain_text)
    if start_sec is None or end_sec is None or end_sec <= start_sec or not text:
        return None
    return {
        "segmentKey": _segment_source_key(segment),
        "title": _compact_text(segment.title),
        "textContent": text,
        "startSec": start_sec,
        "endSec": end_sec,
        "orderNo": segment.order_no,
    }


def _outline_child_items(outline_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for raw_item in outline_payload.get("items", []):
        if not isinstance(raw_item, dict):
            continue
        raw_children = raw_item.get("children")
        if isinstance(raw_children, list):
            children.extend(dict(child) for child in raw_children if isinstance(child, dict))
    return children


def _outline_child_with_block(
    raw_child: Mapping[str, Any],
    blocks_by_key: Mapping[str, HandoutBlock],
) -> dict[str, Any]:
    child = dict(raw_child)
    block = blocks_by_key.get(str(child.get("outlineKey") or ""))
    if block is not None:
        child["blockId"] = block.id
        child["generationStatus"] = block.status
        child["sourceSegmentKeys"] = list(
            block.source_segment_keys_json or child.get("sourceSegmentKeys") or []
        )
    else:
        child.setdefault("sourceSegmentKeys", [])
    return child


def _document_context_from_segments(
    segments: Sequence[CourseSegment],
    *,
    max_chars: int = 3600,
    per_segment_chars: int = 260,
) -> str:
    lines: list[str] = []
    total_chars = 0
    for segment in segments:
        text = _compact_text(segment.text_content or segment.plain_text or segment.formula_text)
        if not text:
            continue
        title = _compact_text(segment.title)
        locator = _outline_context_locator(segment)
        prefix = f"- [{_segment_source_key(segment)} {segment.segment_type}{locator}]"
        content = _truncate_text(f"{title}：{text}" if title else text, per_segment_chars)
        line = f"{prefix} {content}"
        next_total = total_chars + len(line) + 1
        if next_total > max_chars:
            break
        lines.append(line)
        total_chars = next_total
    return "\n".join(lines)


def _outline_context_locator(segment: CourseSegment) -> str:
    if segment.page_no is not None:
        return f" page={segment.page_no}"
    if segment.slide_no is not None:
        return f" slide={segment.slide_no}"
    if segment.section_path:
        return f" section={'/'.join(str(item) for item in segment.section_path)}"
    return ""


def _outline_item_from_caption_group(group: list[dict[str, Any]], index: int) -> dict[str, Any]:
    text = _compact_text(" ".join(str(item["textContent"]) for item in group))
    title = group[0].get("title") or _short_title(text, fallback=f"第 {index} 段")
    return {
        "outlineKey": f"outline-{index}",
        "title": title,
        "summary": _truncate_text(text, 72) or "本段围绕视频字幕展开。",
        "startSec": group[0]["startSec"],
        "endSec": group[-1]["endSec"],
        "sortNo": index,
        "generationStatus": "pending",
        "sourceSegmentKeys": [str(item["segmentKey"]) for item in group],
    }


def _segment_source_key(segment: CourseSegment) -> str:
    return f"segment-{segment.id}"


def _segment_id_from_source_key(value: str) -> int | None:
    prefix = "segment-"
    if not value.startswith(prefix):
        return None
    raw_id = value[len(prefix):]
    if not raw_id.isdigit():
        return None
    return int(raw_id)


def _locator_for_handout_ref(
    raw_item: dict[str, Any],
    segment: CourseSegment,
    *,
    block: HandoutBlock | None = None,
) -> dict[str, Any]:
    raw_locator = _raw_locator(raw_item)
    if _locator_group_count(raw_locator) > 1:
        return {}

    segment_locator = _segment_locator(segment)
    if not segment_locator:
        return {}

    if segment.segment_type == "video_caption":
        if not raw_locator:
            return segment_locator
        if "startSec" not in raw_locator or "endSec" not in raw_locator:
            return {}
        raw_start = _as_outline_int(raw_locator.get("startSec"))
        raw_end = _as_outline_int(raw_locator.get("endSec"))
        segment_start = _as_outline_int(segment_locator.get("startSec"))
        segment_end = _as_outline_int(segment_locator.get("endSec"))
        if (
            raw_start is None
            or raw_end is None
            or segment_start is None
            or segment_end is None
            or raw_end <= raw_start
        ):
            return {}
        if raw_start >= segment_start and raw_end <= segment_end:
            return {"startSec": raw_start, "endSec": raw_end}
        if (
            block is not None
            and segment.id == _first_source_segment_id(block)
            and raw_start == _as_outline_int(block.start_sec)
            and raw_end == _as_outline_int(block.end_sec)
        ):
            return {"startSec": raw_start, "endSec": raw_end}
        return {}

    return segment_locator


def _first_source_segment_id(block: HandoutBlock) -> int | None:
    for source_key in block.source_segment_keys_json or []:
        segment_id = _segment_id_from_source_key(str(source_key))
        if segment_id is not None:
            return segment_id
    return None


def _segment_locator(segment: CourseSegment) -> dict[str, Any]:
    if segment.page_no is not None:
        return {"pageNo": int(segment.page_no)}
    if segment.slide_no is not None:
        return {"slideNo": int(segment.slide_no)}
    if segment.segment_type == "docx_block_text" or segment.section_path:
        return {"anchorKey": _segment_source_key(segment)}
    start_sec = _as_outline_int(segment.start_sec)
    end_sec = _as_outline_int(segment.end_sec)
    if start_sec is not None and end_sec is not None and end_sec > start_sec:
        return {"startSec": start_sec, "endSec": end_sec}
    return {}


def _raw_locator(payload: dict[str, Any]) -> dict[str, Any]:
    locator: dict[str, Any] = {}
    for key in ("pageNo", "slideNo"):
        value = _as_outline_int(_payload_value(payload, key, _camel_to_snake(key)))
        if value is not None:
            locator[key] = value
    anchor_key = _payload_value(payload, "anchorKey", "anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        locator["anchorKey"] = _compact_text(anchor_key)
    start_sec = _as_outline_int(_payload_value(payload, "startSec", "start_sec"))
    end_sec = _as_outline_int(_payload_value(payload, "endSec", "end_sec"))
    if start_sec is not None and end_sec is not None and end_sec > start_sec:
        locator["startSec"] = start_sec
        locator["endSec"] = end_sec
    elif start_sec is not None or end_sec is not None:
        locator["invalidTimeRange"] = True
    return locator


def _locator_group_count(locator: dict[str, Any]) -> int:
    groups = 0
    groups += 1 if "pageNo" in locator else 0
    groups += 1 if "slideNo" in locator else 0
    groups += 1 if "anchorKey" in locator else 0
    groups += 1 if "startSec" in locator and "endSec" in locator else 0
    groups += 1 if "invalidTimeRange" in locator else 0
    return groups


def _locator_tuple(locator: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(
        (key, locator[key])
        for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec")
        if key in locator
    )


def _ref_type(locator: dict[str, Any]) -> str:
    if "startSec" in locator and "endSec" in locator:
        return "video_time_range"
    if "pageNo" in locator:
        return "pdf_page"
    if "slideNo" in locator:
        return "ppt_slide"
    if "anchorKey" in locator:
        return "doc_anchor"
    return "segment"


def _ref_label(raw_item: dict[str, Any], segment: CourseSegment, locator: dict[str, Any]) -> str:
    raw_label = _payload_value(raw_item, "refLabel", "ref_label")
    if isinstance(raw_label, str) and raw_label.strip():
        return _truncate_text(raw_label, 255)
    if "startSec" in locator and "endSec" in locator:
        return f"视频 {int(locator['startSec']):02d}s-{int(locator['endSec']):02d}s"
    if "pageNo" in locator:
        return f"PDF 第 {int(locator['pageNo'])} 页"
    if "slideNo" in locator:
        return f"PPT 第 {int(locator['slideNo'])} 页"
    if "anchorKey" in locator:
        return "文档片段"
    return _truncate_text(segment.title or "来源片段", 255)


def _segment_keyword_tokens(segments: Sequence[CourseSegment]) -> set[str]:
    tokens: set[str] = set()
    for segment in segments:
        tokens.update(_text_tokens(segment.text_content or segment.plain_text))
        if segment.title:
            tokens.update(_text_tokens(segment.title))
    return tokens


def _text_tokens(text: str) -> set[str]:
    tokens = {
        token
        for token in re.findall(r"[A-Za-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", text.lower())
        if len(token) >= 2
    }
    for chinese_run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.update(chinese_run[index : index + 2] for index in range(0, len(chinese_run) - 1))
    return tokens


def _video_segment_near_range(
    segment: CourseSegment,
    *,
    min_start: float | None,
    max_end: float | None,
    tolerance_sec: int = 30,
) -> bool:
    if min_start is None or max_end is None or segment.start_sec is None or segment.end_sec is None:
        return False
    return segment.start_sec < max_end + tolerance_sec and segment.end_sec > min_start - tolerance_sec


def _as_positive_int(value: Any) -> int | None:
    parsed = _as_outline_int(value)
    if parsed is None or parsed < 1:
        return None
    return parsed


def _as_outline_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _camel_to_snake(value: str) -> str:
    output = []
    for char in value:
        if char.isupper():
            output.append("_")
            output.append(char.lower())
        else:
            output.append(char)
    return "".join(output).lstrip("_")


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _short_title(text: str, *, fallback: str) -> str:
    clean = _compact_text(text)
    if not clean:
        return fallback
    return _truncate_text(clean, 24)


def _truncate_text(text: str, limit: int) -> str:
    clean = _compact_text(text)
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit].rstrip()}..."


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value
