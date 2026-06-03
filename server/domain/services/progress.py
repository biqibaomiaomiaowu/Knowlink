from __future__ import annotations

from server.domain.repositories import CourseRepository, LessonProgressRepository, LessonRepository, ProgressRepository
from server.domain.services.errors import ServiceError


class ProgressService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        progress: ProgressRepository,
        lessons: LessonRepository | None = None,
        lesson_progress: LessonProgressRepository | None = None,
    ) -> None:
        self.courses = courses
        self.progress = progress
        self.lessons = lessons
        self.lesson_progress = lesson_progress

    def get_progress(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return self.progress.get_progress(course_id)

    def update_progress(self, *, course_id: int, payload) -> dict[str, object]:
        self._ensure_course(course_id)
        try:
            return self.progress.update_progress(
                course_id,
                payload.model_dump(by_alias=True, exclude_none=True),
            )
        except ValueError as exc:
            raise ServiceError(
                message=str(exc),
                error_code="progress.invalid_reference",
                status_code=400,
            ) from exc

    def get_lesson_progress(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        progress = self._require_lesson_progress().get_user_lesson_progress(course_id=course_id, lesson_id=lesson_id)
        if progress is None:
            return {
                "courseId": course_id,
                "lessonId": lesson_id,
                "lastPositionSec": None,
                "lastHandoutBlockId": None,
                "handoutReadPercent": 0,
                "quizStatus": "not_generated",
                "reviewStatus": "not_due",
                "lastActivityAt": None,
            }
        return progress

    def update_lesson_progress(self, *, course_id: int, lesson_id: int, payload) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        try:
            return self._require_lesson_progress().upsert_user_lesson_progress(
                course_id=course_id,
                lesson_id=lesson_id,
                payload=payload.model_dump(by_alias=True, exclude_none=True),
            )
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _ensure_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        if self.lessons is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        lesson = self.lessons.get_lesson(course_id=course_id, lesson_id=lesson_id)
        if lesson is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        return lesson

    def _require_lesson_progress(self) -> LessonProgressRepository:
        if self.lesson_progress is None:
            raise ServiceError(
                message="Lesson progress is unavailable.",
                error_code="lesson.not_found",
                status_code=404,
            )
        return self.lesson_progress

    def _service_error_from_value_error(self, exc: ValueError) -> ServiceError:
        error_code = str(exc) or "common.validation_error"
        return ServiceError(
            message=error_code.replace(".", " "),
            error_code=error_code,
            status_code={
                "lesson.not_found": 404,
                "artifact.scope_invalid": 400,
            }.get(error_code, 400),
        )
