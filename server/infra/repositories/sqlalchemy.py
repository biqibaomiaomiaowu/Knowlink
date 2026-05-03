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
    HandoutBlock,
    HandoutOutline,
    HandoutVersion,
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

    def create_handout(
        self,
        course_id: int,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        course = self._get_course_model(course_id)
        if course is None:
            raise ValueError(f"Course {course_id} was not found.")

        source_parse_run_id = course.active_parse_run_id
        outline_payload: dict[str, Any] | None = None
        if source_parse_run_id is not None:
            outline_payload = _build_outline_from_caption_segments(
                course=course,
                captions=self._list_active_video_caption_segments(
                    course_id=course_id,
                    parse_run_id=source_parse_run_id,
                ),
            )

        if outline_payload is None:
            status = "failed"
            outline_status = "failed"
            title = course.title
            summary = "没有可用的视频字幕片段，未生成视频时间轴目录。"
            error_code = "handout_outline.no_video_caption"
            error_message = "Active parse run has no usable video_caption segments."
            outline_items: list[dict[str, Any]] = []
        else:
            status = "outline_ready"
            outline_status = "ready"
            title = str(outline_payload["title"])
            summary = str(outline_payload["summary"])
            error_code = None
            error_message = None
            outline_items = list(outline_payload["items"])

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
            meta_json=None,
        )
        self.session.add(version)
        self.session.flush()

        blocks: list[HandoutBlock] = []
        if outline_payload is not None:
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
        block = self.session.scalar(
            select(HandoutBlock)
            .join(HandoutVersion, HandoutVersion.id == HandoutBlock.handout_version_id)
            .join(Course, Course.id == HandoutVersion.course_id)
            .where(HandoutBlock.id == block_id, Course.user_id == self.user_id)
        )
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

        return {
            "blockId": block.id,
            "outlineKey": block.outline_key,
            "videoResourceId": video_resource_id,
            "startSec": block.start_sec,
            "endSec": block.end_sec,
            "docResourceId": None,
            "pageNo": None,
            "slideNo": None,
            "anchorKey": None,
        }

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
            active = self._get_handout_version_model(course.active_handout_version_id)
            if active is not None:
                return active
        return self.session.scalars(
            select(HandoutVersion)
            .where(HandoutVersion.course_id == course_id)
            .order_by(HandoutVersion.created_at.desc(), HandoutVersion.id.desc())
        ).first()

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

    def _list_handout_blocks(self, handout_version_id: int) -> list[dict[str, Any]]:
        blocks = self.session.scalars(
            select(HandoutBlock)
            .where(HandoutBlock.handout_version_id == handout_version_id)
            .order_by(HandoutBlock.sort_no.asc(), HandoutBlock.id.asc())
        ).all()
        return [_handout_block_dict(block) for block in blocks]

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
        item = dict(raw_item)
        block = blocks_by_key.get(str(item.get("outlineKey") or ""))
        if block is not None:
            item["blockId"] = block.id
            item["generationStatus"] = block.status
            item["sourceSegmentKeys"] = list(
                block.source_segment_keys_json or item.get("sourceSegmentKeys") or []
            )
        else:
            item.setdefault("sourceSegmentKeys", [])
        items.append(item)

    return {
        "handoutVersionId": version.id,
        "title": outline.title,
        "summary": outline.summary,
        "items": items,
    }


def _handout_block_dict(block: HandoutBlock) -> dict[str, Any]:
    return {
        "blockId": block.id,
        "outlineKey": block.outline_key,
        "title": block.title,
        "summary": block.summary,
        "status": block.status,
        "contentMd": block.content_md,
        "startSec": block.start_sec,
        "endSec": block.end_sec,
        "sourceSegmentKeys": list(block.source_segment_keys_json or []),
        "knowledgePoints": block.knowledge_points_json or [],
        "citations": block.citations_json or [],
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
