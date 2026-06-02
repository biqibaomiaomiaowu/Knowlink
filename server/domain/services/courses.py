from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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

    def list_courses(self, *, filters: Mapping[str, Any] | None = None) -> dict[str, object]:
        courses = self.courses.list_courses(filters)
        return {"items": [self._library_item(course) for course in courses]}

    def get_course(self, *, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            self._raise_not_found()
        return {"course": course}

    def update_course(self, *, course_id: int, payload) -> dict[str, object]:
        changes = payload.model_dump(exclude_unset=True)
        course = self.courses.update_course(course_id, changes)
        if course is None:
            self._raise_not_found()
        return {"course": course}

    def archive_course(self, *, course_id: int) -> dict[str, object]:
        course = self.courses.archive_course(course_id)
        if course is None:
            self._raise_not_found()
        return {"course": course}

    def restore_course(self, *, course_id: int) -> dict[str, object]:
        course = self.courses.restore_course(course_id)
        if course is None:
            self._raise_not_found()
        return {"course": course}

    def get_course_delete_impact(self, *, course_id: int) -> dict[str, object]:
        impact = self.courses.get_course_delete_impact(course_id)
        if impact is None:
            self._raise_not_found()
        return impact

    def delete_course(self, *, course_id: int) -> dict[str, object]:
        try:
            result = self.courses.delete_course(course_id)
        except ValueError as exc:
            if str(exc) == "course.delete_blocked":
                raise ServiceError(
                    message="Course has dependent data and cannot be deleted safely.",
                    error_code="course.delete_blocked",
                    status_code=409,
                ) from exc
            raise
        if result is None:
            self._raise_not_found()
        return result

    def switch_current_course(self, *, course_id: int) -> dict[str, object]:
        course = self.courses.set_current_course(course_id)
        if course is None:
            self._raise_not_found()
        return {"currentCourseId": course["courseId"], "course": course}

    def get_current_course(self) -> dict[str, object]:
        course = self.courses.get_current_course()
        if course is None:
            self._raise_not_found()
        return {"course": course}

    def _library_item(self, course: dict[str, Any]) -> dict[str, Any]:
        return {
            "courseId": course["courseId"],
            "title": course["title"],
            "isCurrent": bool(course.get("isCurrent", False)),
            "entryType": course["entryType"],
            "learningStatus": course.get("lifecycleStatus", "draft"),
            "lastActivityAt": course.get("lastActivityAt") or course.get("updatedAt"),
            "lessonCount": int(course.get("lessonCount", 0)),
            "courseResourceCount": int(course.get("courseResourceCount", 0)),
            "currentLessonId": course.get("currentLessonId"),
            "currentLessonTitle": course.get("currentLessonTitle"),
            "overallMasteryScore": course.get("overallMasteryScore"),
            "pendingReviewCount": int(course.get("pendingReviewCount", 0)),
            "pipelineStage": course.get("pipelineStage", "idle"),
            "pipelineStatus": course.get("pipelineStatus", "idle"),
            "lifecycleStatus": course.get("lifecycleStatus", "draft"),
            "archivedAt": course.get("archivedAt"),
        }

    def _raise_not_found(self) -> None:
        raise ServiceError(
            message="Course was not found.",
            error_code="course.not_found",
            status_code=404,
        )
