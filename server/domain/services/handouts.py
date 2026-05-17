from __future__ import annotations

from server.domain.repositories import (
    AsyncTaskRepository,
    CourseRepository,
    HandoutRepository,
    IdempotencyRepository,
    TaskDispatcher,
)
from server.domain.services.async_tasks import (
    enqueue_or_fail_if_missing_dispatcher,
    ensure_async_task_for_trigger,
    raise_async_task_binding_failed,
    refresh_enqueue_failure_status,
    resolve_async_tasks,
)
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import async_trigger_matches_course, run_scoped_idempotent
from server.ai.handout_lazy import HandoutOutlineClient, generate_handout_outline


class HandoutService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        handouts: HandoutRepository,
        idempotency: IdempotencyRepository,
        task_dispatcher: TaskDispatcher | None = None,
        outline_client: HandoutOutlineClient | None = None,
        async_tasks: AsyncTaskRepository | None = None,
    ) -> None:
        self.courses = courses
        self.handouts = handouts
        self.idempotency = idempotency
        self.task_dispatcher = task_dispatcher
        self.outline_client = outline_client
        self.async_tasks = resolve_async_tasks(async_tasks, handouts)

    def generate_handout(self, *, course_id: int, idempotency_key: str | None) -> dict[str, object]:
        course = self._ensure_course(course_id)
        if course.get("activeParseRunId") is None:
            raise ServiceError(
                message="Course is not ready for handout generation.",
                error_code="pipeline.not_ready",
                status_code=409,
            )

        enqueue_request: tuple[int, dict[str, object]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal enqueue_request, created_response
            outline, outline_meta, error_code, error_message = self._build_outline_for_course(course_id)
            _, trigger, _ = self.handouts.create_handout(
                course_id,
                outline=outline,
                outline_meta=outline_meta,
                error_code=error_code,
                error_message=error_message,
            )
            if _should_enqueue_trigger(trigger):
                task_id = _int_value(trigger.get("taskId"))
                if task_id is None:
                    raise_async_task_binding_failed(
                        self.async_tasks,
                        task_id=None,
                        message="Async task trigger did not include a task id.",
                    )
                handout_version_id = _entity_id(trigger)
                if handout_version_id is None:
                    raise_async_task_binding_failed(
                        self.async_tasks,
                        task_id=task_id,
                        message="Async task trigger did not include a handout version id.",
                    )
                payload = {
                    "courseId": course_id,
                    "handoutVersionId": handout_version_id,
                    "sourceParseRunId": course.get("activeParseRunId"),
                }
                trigger, task_id = ensure_async_task_for_trigger(
                    self.async_tasks,
                    trigger,
                    course_id=course_id,
                    task_type="handout_generate",
                    payload=payload,
                    target_type="handout_version",
                    target_id=handout_version_id,
                    parse_run_id=_int_value(course.get("activeParseRunId")),
                    allow_create=True,
                )
                if task_id is None:
                    raise_async_task_binding_failed(
                        self.async_tasks,
                        task_id=None,
                        message="Async task trigger could not be bound.",
                    )
                enqueue_request = (task_id, payload)
            created_response = trigger
            return trigger

        result = run_scoped_idempotent(
            self.idempotency,
            action=f"handouts.generate:{course_id}",
            key=idempotency_key,
            factory=factory,
            legacy_action="handouts.generate",
            legacy_matches=lambda legacy: async_trigger_matches_course(
                legacy,
                course_id=course_id,
                entity_type="handout_version",
                task_type="handout_generate",
                async_tasks=self.async_tasks,
                target_type="handout_version",
            ),
        )
        if enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            enqueue_or_fail_if_missing_dispatcher(
                self.async_tasks,
                task_id=task_id,
                dispatcher=self.task_dispatcher,
                enqueue=lambda: self.task_dispatcher.enqueue_handout_generate(task_id=task_id, payload=payload),
            )
        if isinstance(result, dict) and self.async_tasks is not None:
            return refresh_enqueue_failure_status(self.async_tasks, result)
        return result

    def _build_outline_for_course(
        self,
        course_id: int,
    ) -> tuple[dict[str, object] | None, dict[str, object], str | None, str | None]:
        context = self.handouts.get_handout_outline_context(course_id)
        if context is None:
            return None, {}, None, None

        caption_segments = context.get("captionSegments")
        if not isinstance(caption_segments, list) or not caption_segments:
            return (
                None,
                {"outlineUsedFallback": False, "outlineIssues": ["handout_outline.no_video_caption"]},
                "handout_outline.no_video_caption",
                "Active parse run has no usable video_caption segments.",
            )

        try:
            generation = generate_handout_outline(
                caption_segments,
                client=self.outline_client,
                title=str(context.get("title") or "视频时间轴目录"),
                summary=str(context.get("summary") or "基于视频字幕快速生成的讲义目录。"),
                document_context=_optional_text(context.get("documentContext")),
            )
        except ValueError:
            return (
                None,
                {"outlineUsedFallback": False, "outlineIssues": ["handout_outline.no_video_caption"]},
                "handout_outline.no_video_caption",
                "Active parse run has no usable video_caption segments.",
            )

        return (
            generation.outline,
            {
                "outlineUsedFallback": generation.used_fallback,
                "outlineIssues": generation.issues,
            },
            None,
            None,
        )

    def get_status(self, *, handout_version_id: int) -> dict[str, object]:
        handout = self.handouts.get_handout(handout_version_id)
        if handout is None:
            raise ServiceError(
                message="Handout was not found.",
                error_code="handout.not_found",
                status_code=404,
            )
        return {
            "handoutVersionId": handout["handoutVersionId"],
            "status": handout["status"],
            "outlineStatus": handout.get("outlineStatus", "ready"),
            "totalBlocks": handout["totalBlocks"],
            "readyBlocks": handout.get("readyBlocks", 0),
            "pendingBlocks": handout.get("pendingBlocks", 0),
            "sourceParseRunId": handout["sourceParseRunId"],
        }

    def get_latest_handout(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        handout = self.handouts.get_latest_handout(course_id)
        if handout is None:
            raise ServiceError(
                message="The course has no active handout.",
                error_code="handout.no_active_version",
                status_code=404,
            )
        return {
            "handoutVersionId": handout["handoutVersionId"],
            "title": handout["title"],
            "summary": handout["summary"],
            "totalBlocks": handout["totalBlocks"],
            "status": handout["status"],
        }

    def get_latest_outline(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        outline = self.handouts.get_latest_outline(course_id)
        if outline is None:
            raise ServiceError(
                message="The course has no active handout outline.",
                error_code="handout.no_active_version",
                status_code=404,
            )
        return outline

    def get_latest_blocks(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        handout = self.handouts.get_latest_handout(course_id)
        if handout is None:
            raise ServiceError(
                message="The course has no active handout.",
                error_code="handout.no_active_version",
                status_code=404,
            )
        return {"items": handout["blocks"]}

    def generate_block(self, *, block_id: int, idempotency_key: str | None) -> dict[str, object]:
        current_status = self.handouts.get_handout_block_status(block_id)
        if current_status is not None and current_status.get("status") == "ready":
            return current_status

        enqueue_request: tuple[int, dict[str, object]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal enqueue_request, created_response
            prepared = self.handouts.prepare_handout_block_generation(block_id)
            if prepared is None:
                raise ServiceError(
                    message="Handout block was not found.",
                    error_code="qa.block_not_found",
                    status_code=404,
                )
            response, prepared_enqueue_request = prepared
            if prepared_enqueue_request is not None:
                task_id, payload = prepared_enqueue_request
                course_id = _int_value(payload.get("courseId"))
                block_target_id = _int_value(payload.get("handoutBlockId")) or block_id
                if self.async_tasks is not None:
                    response, task_id = ensure_async_task_for_trigger(
                        self.async_tasks,
                        response,
                        course_id=course_id,
                        task_type="handout_block_generate",
                        payload=payload,
                        target_type="handout_block",
                        target_id=block_target_id,
                        parse_run_id=_int_value(payload.get("sourceParseRunId")),
                        allow_create=True,
                    )
                if task_id is not None:
                    enqueue_request = (task_id, payload)
            else:
                block_target_id = _entity_id(response) or block_id
                response, task_id = ensure_async_task_for_trigger(
                    self.async_tasks,
                    response,
                    course_id=None,
                    task_type="handout_block_generate",
                    payload={"handoutBlockId": block_target_id},
                    target_type="handout_block",
                    target_id=block_target_id,
                )
                if task_id is None and current_status is not None:
                    response = current_status
            created_response = response
            return response

        result = self.idempotency.run_idempotent(
            f"handout_blocks.generate:{block_id}",
            idempotency_key,
            factory,
        )
        if enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            enqueue_or_fail_if_missing_dispatcher(
                self.async_tasks,
                task_id=task_id,
                dispatcher=self.task_dispatcher,
                enqueue=lambda: self.task_dispatcher.enqueue_handout_block_generate(task_id=task_id, payload=payload),
            )
        if isinstance(result, dict) and self.async_tasks is not None:
            return refresh_enqueue_failure_status(self.async_tasks, result)
        return result

    def get_block_status(self, *, block_id: int) -> dict[str, object]:
        status = self.handouts.get_handout_block_status(block_id)
        if status is None:
            raise ServiceError(
                message="Handout block was not found.",
                error_code="qa.block_not_found",
                status_code=404,
            )
        return status

    def get_current_block(self, *, course_id: int, current_sec: int) -> dict[str, object]:
        self._ensure_course(course_id)
        current = self.handouts.get_current_handout_block(course_id, current_sec)
        if current is None:
            raise ServiceError(
                message="The course has no matching handout block.",
                error_code="handout.block_not_found",
                status_code=404,
            )
        return current

    def get_jump_target(self, *, block_id: int) -> dict[str, object]:
        jump_target = self.handouts.get_block_jump_target(block_id)
        if jump_target is None:
            raise ServiceError(
                message="Handout block was not found.",
                error_code="qa.block_not_found",
                status_code=404,
            )
        return jump_target

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course


def _entity_id(trigger: dict[str, object]) -> int | None:
    entity = trigger.get("entity")
    if not isinstance(entity, dict):
        return None
    return _int_value(entity.get("id"))


def _should_enqueue_trigger(trigger: dict[str, object]) -> bool:
    return trigger.get("status") == "queued" and trigger.get("nextAction") == "poll"


def _int_value(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
