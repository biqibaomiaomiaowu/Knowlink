from __future__ import annotations

from server.domain.repositories import CourseRepository, IdempotencyRepository, QuizRepository
from server.domain.services.errors import ServiceError


class QuizService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        quizzes: QuizRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.quizzes = quizzes
        self.idempotency = idempotency

    def generate_quiz(self, *, course_id: int, idempotency_key: str | None) -> dict[str, object]:
        self._ensure_course(course_id)

        def factory() -> dict[str, object]:
            _, trigger = self.quizzes.create_quiz(course_id)
            return trigger

        return self.idempotency.run_idempotent("quizzes.generate", idempotency_key, factory)

    def get_quiz(self, *, quiz_id: int) -> dict[str, object]:
        quiz = self.quizzes.get_quiz(quiz_id)
        if quiz is None:
            raise ServiceError(
                message="Quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        return quiz

    def get_quiz_status(self, *, quiz_id: int) -> dict[str, object]:
        quiz = self.get_quiz(quiz_id=quiz_id)
        return {
            "quizId": quiz["quizId"],
            "status": quiz["status"],
            "questionCount": quiz["questionCount"],
        }

    def submit_quiz(self, *, quiz_id: int, payload) -> dict[str, object]:
        _ = payload
        quiz = self.quizzes.get_quiz(quiz_id)
        if quiz is None:
            raise ServiceError(
                message="Quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        return self.quizzes.submit_quiz(quiz_id)

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course
