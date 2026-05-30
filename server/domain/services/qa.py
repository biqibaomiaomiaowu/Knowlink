from __future__ import annotations

from server.ai.qa_orchestrator import QaOrchestrator
from server.ai.qa_policy import QaAnswerClient
from server.domain.repositories import CourseRepository, QaRepository
from server.domain.services.errors import ServiceError


class QaService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        qa: QaRepository,
        embedding_client: object | None = None,
        qa_answer_client: QaAnswerClient | None = None,
        answer_client: QaAnswerClient | None = None,
    ) -> None:
        self.courses = courses
        self.qa = qa
        self.embedding_client = embedding_client
        self.qa_answer_client = qa_answer_client if qa_answer_client is not None else answer_client

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
