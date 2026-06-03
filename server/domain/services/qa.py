from __future__ import annotations

from server.ai.qa_orchestrator import QaOrchestrator
from server.ai.qa_policy import QaAnswerClient
from server.domain.repositories import CourseRepository, LessonRepository, QaRepository, ResourceRepository
from server.domain.services.errors import ServiceError


class QaService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        qa: QaRepository,
        lessons: LessonRepository | None = None,
        resources: ResourceRepository | None = None,
        embedding_client: object | None = None,
        qa_answer_client: QaAnswerClient | None = None,
        answer_client: QaAnswerClient | None = None,
    ) -> None:
        self.courses = courses
        self.qa = qa
        self.lessons = lessons
        self.resources = resources
        self.embedding_client = embedding_client
        self.qa_answer_client = qa_answer_client if qa_answer_client is not None else answer_client

    def list_course_sessions(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return {"items": self.qa.list_scoped_qa_sessions(course_id=course_id, scope_type="course")}

    def list_lesson_sessions(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        return {
            "items": self.qa.list_scoped_qa_sessions(
                course_id=course_id,
                scope_type="lesson",
                lesson_id=lesson_id,
            )
        }

    def create_course_message(self, *, course_id: int, payload) -> dict[str, object]:
        course = self._ensure_course(course_id)
        citations = self._course_citations(course_id=course_id)
        return self._create_scoped_message(
            course_id=course_id,
            scope_type="course",
            lesson_id=None,
            session_id=payload.session_id,
            question=payload.question,
            answer_md=f"这是《{course.get('title') or '当前课程'}》的课程级 QA 占位回答。",
            citations=citations,
        )

    def create_lesson_message(self, *, course_id: int, lesson_id: int, payload) -> dict[str, object]:
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        citations = self._lesson_citations(course_id=course_id, lesson=lesson)
        return self._create_scoped_message(
            course_id=course_id,
            scope_type="lesson",
            lesson_id=lesson_id,
            session_id=payload.session_id,
            question=payload.question,
            answer_md=f"这是《{lesson.get('title') or '当前课时'}》的课时级 QA 占位回答。",
            citations=citations,
        )

    def create_message(self, *, payload) -> dict[str, object]:
        if self.courses.get_course(payload.course_id) is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        context = self.qa.get_qa_context(payload.course_id, payload.handout_block_id)
        if context is None:
            raise ServiceError(
                message="Handout block was not found.",
                error_code="qa.block_not_found",
                status_code=404,
            )
        generation_result = QaOrchestrator(
            retrieval_repository=self.qa,
            embedding_client=self.embedding_client,
            qa_answer_client=self.qa_answer_client,
        ).answer(
            payload.question,
            context,
        )
        response = generation_result.response
        refs = generation_result.refs
        if response.get("generationMetadata", {}).get("evidenceTier") != "original_evidence":
            response = {**response, "citations": []}
            refs = []
        result = self.qa.save_qa_exchange(
            context,
            payload.question,
            response,
            refs,
            generation_result.candidate_count,
        )
        return result

    def get_session_messages(self, *, session_id: int) -> dict[str, object]:
        messages = self.qa.get_session_messages(session_id)
        if messages is None:
            raise ServiceError(
                message="QA session was not found.",
                error_code="common.not_found",
                status_code=404,
            )
        return {"items": messages}

    def _create_scoped_message(
        self,
        *,
        course_id: int,
        scope_type: str,
        lesson_id: int | None,
        session_id: int | None,
        question: str,
        answer_md: str,
        citations: list[dict[str, object]],
    ) -> dict[str, object]:
        try:
            return self.qa.create_scoped_qa_exchange(
                course_id=course_id,
                scope_type=scope_type,
                lesson_id=lesson_id,
                session_id=session_id,
                question=question,
                answer_md=answer_md,
                citations=citations,
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

    def _course_citations(self, *, course_id: int) -> list[dict[str, object]]:
        if self.resources is None:
            return []
        citations = []
        lessons = {
            lesson["lessonId"]: lesson
            for lesson in (self.lessons.list_lessons(course_id) if self.lessons is not None else [])
        }
        for resource in self.resources.list_resources(course_id):
            if resource.get("scopeType") == "lesson" and resource.get("visibleToCourseQa") is not True:
                continue
            citations.append(self._resource_citation(resource=resource, lesson=lessons.get(resource.get("lessonId"))))
        return citations

    def _lesson_citations(self, *, course_id: int, lesson: dict[str, object]) -> list[dict[str, object]]:
        if self.resources is None:
            return []
        lesson_id = int(lesson["lessonId"])
        return [
            self._resource_citation(resource=resource, lesson=lesson)
            for resource in self.resources.list_resources(course_id)
            if resource.get("scopeType") == "lesson" and resource.get("lessonId") == lesson_id
        ]

    def _resource_citation(
        self,
        *,
        resource: dict[str, object],
        lesson: dict[str, object] | None,
    ) -> dict[str, object]:
        lesson_id = lesson.get("lessonId") if lesson is not None else None
        lesson_title = lesson.get("title") if lesson is not None else None
        lesson_order = lesson.get("orderIndex") if lesson is not None else None
        prefix = f"第 {lesson_order} 课时：{lesson_title} / " if lesson_title and lesson_order else ""
        return {
            "scopeType": resource.get("scopeType"),
            "lessonId": lesson_id,
            "lessonTitle": lesson_title,
            "lessonOrderIndex": lesson_order,
            "resourceId": resource["resourceId"],
            "resourceName": resource.get("originalName"),
            "refLabel": f"{prefix}{resource.get('originalName') or '课程资料'}",
            "startSec": 0 if resource.get("resourceType") == "mp4" else None,
            "endSec": min(int(resource.get("durationSec") or 60), 60) if resource.get("resourceType") == "mp4" else None,
            "confidenceScore": 0.5,
        }

    def _service_error_from_value_error(self, exc: ValueError) -> ServiceError:
        error_code = str(exc) or "qa.scope_invalid"
        return ServiceError(
            message=error_code.replace(".", " "),
            error_code=error_code,
            status_code={
                "course.not_found": 404,
                "lesson.not_found": 404,
                "qa.scope_invalid": 400,
            }.get(error_code, 400),
        )
