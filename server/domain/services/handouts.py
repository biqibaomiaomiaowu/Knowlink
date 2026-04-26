from __future__ import annotations

from server.domain.repositories import (
    CourseRepository,
    HandoutRepository,
    IdempotencyRepository,
)
from server.domain.services.errors import ServiceError


class HandoutService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        handouts: HandoutRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.handouts = handouts
        self.idempotency = idempotency

    def generate_handout(self, *, course_id: int, idempotency_key: str | None) -> dict[str, object]:
        course = self._ensure_course(course_id)
        if course.get("activeParseRunId") is None:
            raise ServiceError(
                message="Course is not ready for handout generation.",
                error_code="pipeline.not_ready",
                status_code=409,
            )

        def factory() -> dict[str, object]:
            _, trigger, _ = self.handouts.create_handout(course_id)
            return trigger

        return self.idempotency.run_idempotent("handouts.generate", idempotency_key, factory)

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
            "totalBlocks": handout["totalBlocks"],
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
