from __future__ import annotations

from typing import Any

from server.domain.repositories import CourseRepository, LessonRepository, ScopedArtifactRepository
from server.domain.services.errors import ServiceError


AVAILABLE_EXPORT_TYPES = [
    "course_summary",
    "lesson_summary",
    "qa_transcript",
    "quiz_report",
    "review_plan",
]


class ExportService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        lessons: LessonRepository | None = None,
        scoped_artifacts: ScopedArtifactRepository | None = None,
    ) -> None:
        self.courses = courses
        self.lessons = lessons
        self.scoped_artifacts = scoped_artifacts

    def get_course_graph(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return self._graph_placeholder(scope_type="course")

    def get_lesson_graph(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        return self._graph_placeholder(scope_type="lesson", lesson_id=lesson_id)

    def get_course_report_summary(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return self._report_placeholder(course_id=course_id, scope_type="course")

    def get_lesson_report_summary(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        return self._report_placeholder(course_id=course_id, scope_type="lesson", lesson_id=lesson_id)

    def list_exports(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return self._export_placeholder(course_id=course_id, scope_type="course")

    def create_export(self, *, course_id: int, payload) -> dict[str, object]:
        self._ensure_course(course_id)
        scope_type = payload.scope_type
        lesson_id = payload.lesson_id
        if scope_type == "lesson":
            if lesson_id is None:
                raise ServiceError(
                    message="Lesson export requires a lesson id.",
                    error_code="artifact.scope_invalid",
                    status_code=400,
                )
            self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        else:
            lesson_id = None
        export_id = None
        if self.scoped_artifacts is not None:
            try:
                artifact = self.scoped_artifacts.create_scoped_artifact(
                    artifact_type="export_run",
                    course_id=course_id,
                    scope_type=scope_type,
                    lesson_id=lesson_id,
                    status="placeholder",
                    exportType=payload.export_type,
                )
            except ValueError as exc:
                raise self._service_error_from_value_error(exc) from exc
            export_id = int(artifact["artifactId"])
        return self._export_placeholder(
            course_id=course_id,
            scope_type=scope_type,
            lesson_id=lesson_id,
            export_type=payload.export_type,
            export_id=export_id,
        )

    def _ensure_course(self, course_id: int) -> dict[str, Any]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _ensure_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
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

    def _graph_placeholder(self, *, scope_type: str, lesson_id: int | None = None) -> dict[str, object]:
        return {
            "status": "placeholder",
            "scopeType": scope_type,
            "lessonId": lesson_id,
            "message": "知识图谱本轮仅提供占位 read model。",
            "availableActions": [],
            "citations": [],
            "nodes": [],
            "edges": [],
        }

    def _report_placeholder(
        self,
        *,
        course_id: int,
        scope_type: str,
        lesson_id: int | None = None,
    ) -> dict[str, object]:
        return {
            "summaryStatus": "placeholder",
            "scopeType": scope_type,
            "courseId": course_id,
            "lessonId": lesson_id,
            "metrics": [],
            "message": "学习报告本轮仅提供占位摘要。",
        }

    def _export_placeholder(
        self,
        *,
        course_id: int,
        scope_type: str,
        lesson_id: int | None = None,
        export_type: str | None = None,
        export_id: int | None = None,
    ) -> dict[str, object]:
        return {
            "availableExportTypes": AVAILABLE_EXPORT_TYPES,
            "status": "placeholder",
            "scopeType": scope_type,
            "courseId": course_id,
            "lessonId": lesson_id,
            "exportType": export_type,
            "exportId": export_id,
            "downloadUrl": None,
            "message": "导出本轮仅提供占位入口，不生成下载文件。",
        }

    def _service_error_from_value_error(self, exc: ValueError) -> ServiceError:
        error_code = str(exc) or "artifact.scope_invalid"
        return ServiceError(
            message=error_code.replace(".", " "),
            error_code=error_code,
            status_code={
                "artifact.scope_invalid": 400,
                "lesson.not_found": 404,
                "course.not_found": 404,
            }.get(error_code, 400),
        )
