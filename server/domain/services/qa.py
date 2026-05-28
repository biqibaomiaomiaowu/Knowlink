from __future__ import annotations

from server.ai.qa_policy import (
    QaAnswerClient,
    build_block_scoped_qa_candidates,
    build_qa_message_refs,
    generate_block_qa_response,
)
from server.domain.repositories import CourseRepository, QaRepository
from server.domain.services.errors import ServiceError


class QaService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        qa: QaRepository,
        qa_answer_client: QaAnswerClient | None = None,
    ) -> None:
        self.courses = courses
        self.qa = qa
        self.qa_answer_client = qa_answer_client

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
        active_course_id = int(context["activeCourseId"])
        active_parse_run_id = int(context["activeParseRunId"])
        active_handout_version_id = int(context["activeHandoutVersionId"])
        candidates = build_block_scoped_qa_candidates(
            payload.question,
            current_block=context["currentBlock"],
            segments=context.get("segments") or [],
            knowledge_point_evidences=context.get("knowledgePointEvidences") or [],
            adjacent_blocks=context.get("adjacentBlocks") or [],
            active_course_id=active_course_id,
            active_parse_run_id=active_parse_run_id,
            active_handout_version_id=active_handout_version_id,
        )
        response = generate_block_qa_response(
            payload.question,
            current_block=context["currentBlock"],
            segments=context.get("segments") or [],
            knowledge_point_evidences=context.get("knowledgePointEvidences") or [],
            adjacent_blocks=context.get("adjacentBlocks") or [],
            active_course_id=active_course_id,
            active_parse_run_id=active_parse_run_id,
            active_handout_version_id=active_handout_version_id,
            course_scope=context.get("courseScope") or {},
            client=self.qa_answer_client,
        )
        refs = build_qa_message_refs(
            response,
            candidates,
            active_course_id=active_course_id,
            active_parse_run_id=active_parse_run_id,
            active_handout_version_id=active_handout_version_id,
        )
        result = self.qa.save_qa_exchange(
            context,
            payload.question,
            response,
            refs,
            len(candidates),
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
