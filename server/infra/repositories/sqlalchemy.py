from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.infra.db.base import utcnow
from server.infra.db.models import (
    AsyncTask,
    Course,
    CourseResource,
    CourseSegment,
    IdempotencyRecord,
    LearningPreference,
    ParseRun,
    VectorDocument,
)


T = TypeVar("T")


GRANULARITY_MAP = {
    "quick": ("low", "low"),
    "balanced": ("medium", "medium"),
    "detailed": ("high", "high"),
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

    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
    ) -> dict[str, Any]:
        course = Course(
            user_id=self.user_id,
            title=title,
            entry_type=entry_type,
            catalog_id=catalog_id,
            goal_text=goal_text,
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
            "exam_at": course.exam_at if course is not None else None,
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

    def _get_course_model(self, course_id: int) -> Course | None:
        return self.session.scalar(
            select(Course).where(Course.id == course_id, Course.user_id == self.user_id)
        )

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
        "preferredStyle": course.preferred_style,
        "lifecycleStatus": course.lifecycle_status,
        "pipelineStage": course.pipeline_stage,
        "pipelineStatus": course.pipeline_status,
        "activeParseRunId": course.active_parse_run_id,
        "activeHandoutVersionId": course.active_handout_version_id,
        "updatedAt": course.updated_at,
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
        "nextAction": "poll",
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


def _course_segment_dict(segment: CourseSegment) -> dict[str, Any]:
    return {
        "segmentId": segment.id,
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
