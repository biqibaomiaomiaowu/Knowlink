from __future__ import annotations

from server.domain.repositories import CourseRepository, QaRepository
from server.domain.services.errors import ServiceError


class QaService:
    def __init__(self, *, courses: CourseRepository, qa: QaRepository) -> None:
        self.courses = courses
        self.qa = qa

    def create_message(self, *, payload) -> dict[str, object]:
        if self.courses.get_course(payload.course_id) is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return self.qa.create_qa_message(payload.course_id, payload.handout_block_id)

    def get_session_messages(self, *, session_id: int) -> dict[str, object]:
        messages = self.qa.get_session_messages(session_id)
        if messages is None:
            raise ServiceError(
                message="QA session was not found.",
                error_code="common.not_found",
                status_code=404,
            )
        return {"items": messages}
