from __future__ import annotations

from server.domain.repositories import (
    CourseRepository,
    HandoutRepository,
    IdempotencyRepository,
    TaskDispatcher,
)
from server.domain.services.errors import ServiceError


class HandoutService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        handouts: HandoutRepository,
        idempotency: IdempotencyRepository,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self.courses = courses
        self.handouts = handouts
        self.idempotency = idempotency
        self.task_dispatcher = task_dispatcher

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
            _, trigger, _ = self.handouts.create_handout(course_id)
            task_id = _int_value(trigger.get("taskId"))
            payload = {
                "courseId": course_id,
                "handoutVersionId": _entity_id(trigger),
                "sourceParseRunId": course.get("activeParseRunId"),
            }
            if task_id is not None and payload["handoutVersionId"] is not None and _should_enqueue_trigger(trigger):
                enqueue_request = (task_id, payload)
            created_response = trigger
            return trigger

        result = self.idempotency.run_idempotent("handouts.generate", idempotency_key, factory)
        if self.task_dispatcher is not None and enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            self.task_dispatcher.enqueue_handout_generate(task_id=task_id, payload=payload)
        return result

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
            response, enqueue_request = prepared
            created_response = response
            return response

        result = self.idempotency.run_idempotent(
            f"handout_blocks.generate:{block_id}",
            idempotency_key,
            factory,
        )
        if self.task_dispatcher is not None and enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            self.task_dispatcher.enqueue_handout_block_generate(task_id=task_id, payload=payload)
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
