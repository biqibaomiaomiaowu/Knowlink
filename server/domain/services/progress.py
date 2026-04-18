from __future__ import annotations

from server.domain.repositories import CourseRepository, ProgressRepository
from server.domain.services.errors import ServiceError


class ProgressService:
    def __init__(self, *, courses: CourseRepository, progress: ProgressRepository) -> None:
        self.courses = courses
        self.progress = progress

    def get_progress(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return self.progress.get_progress(course_id)

    def update_progress(self, *, course_id: int, payload) -> dict[str, object]:
        self._ensure_course(course_id)
        return self.progress.update_progress(
            course_id,
            payload.model_dump(by_alias=True, exclude_none=True),
        )

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course
