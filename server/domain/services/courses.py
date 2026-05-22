from __future__ import annotations

from server.domain.repositories import CourseRepository, IdempotencyRepository
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import run_fingerprinted_idempotent


class CourseService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.idempotency = idempotency

    def create_course(self, *, payload, idempotency_key: str | None) -> dict[str, object]:
        def factory() -> dict[str, object]:
            return {
                "course": self.courses.create_course(
                    title=payload.title,
                    entry_type=payload.entry_type,
                    goal_text=payload.goal_text,
                    preferred_style=payload.preferred_style,
                    exam_at=payload.exam_at,
                )
            }

        return run_fingerprinted_idempotent(
            self.idempotency,
            scope="courses.create",
            key=idempotency_key,
            request_payload=payload.model_dump(by_alias=True),
            factory=factory,
            legacy_action="courses.create",
            legacy_matches=lambda result: isinstance(result, dict),
        )

    def list_recent_courses(self) -> dict[str, object]:
        return {"items": self.courses.list_recent_courses()}

    def get_course(self, *, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return {"course": course}

    def switch_current_course(self, *, course_id: int) -> dict[str, object]:
        course = self.courses.set_current_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return {"currentCourseId": course["courseId"], "course": course}

    def get_current_course(self) -> dict[str, object]:
        course = self.courses.get_current_course()
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return {"course": course}
