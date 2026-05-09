from __future__ import annotations

from server.domain.repositories import CourseRepository, IdempotencyRepository, QuizRepository, TaskDispatcher
from server.domain.services.errors import ServiceError


class QuizService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        quizzes: QuizRepository,
        idempotency: IdempotencyRepository,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self.courses = courses
        self.quizzes = quizzes
        self.idempotency = idempotency
        self.task_dispatcher = task_dispatcher

    def generate_quiz(self, *, course_id: int, idempotency_key: str | None) -> dict[str, object]:
        self._ensure_course(course_id)
        enqueue_request: tuple[int, dict[str, object]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal enqueue_request, created_response
            try:
                _, trigger = self.quizzes.create_quiz(course_id)
            except ValueError as exc:
                raise ServiceError(
                    message=str(exc),
                    error_code="quiz.not_ready",
                    status_code=409,
                ) from exc
            task_id = _int_value(trigger.get("taskId"))
            quiz_id = _entity_id(trigger)
            if task_id is not None and quiz_id is not None and _should_enqueue_trigger(trigger):
                enqueue_request = (
                    task_id,
                    {
                        "courseId": course_id,
                        "quizId": quiz_id,
                    },
                )
            created_response = trigger
            return trigger

        result = self.idempotency.run_idempotent("quizzes.generate", idempotency_key, factory)
        if self.task_dispatcher is not None and enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            self.task_dispatcher.enqueue_quiz_generate(task_id=task_id, payload=payload)
        return result

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
        quiz = self.quizzes.get_quiz(quiz_id)
        if quiz is None:
            raise ServiceError(
                message="Quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        if quiz.get("status") != "ready":
            raise ServiceError(
                message="Quiz is not ready for attempts.",
                error_code="quiz.not_ready",
                status_code=409,
            )
        answers = payload.model_dump(by_alias=True, exclude_none=True).get("answers", [])
        result = dict(self.quizzes.submit_quiz(quiz_id, answers))
        refresh_task = result.pop("_reviewRefreshTask", None)
        if self.task_dispatcher is not None and isinstance(refresh_task, dict):
            task_id = _int_value(refresh_task.get("taskId"))
            payload = refresh_task.get("payload")
            if task_id is not None and isinstance(payload, dict):
                self.task_dispatcher.enqueue_review_refresh(task_id=task_id, payload=payload)
        return result

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course


def _int_value(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _entity_id(trigger: dict[str, object]) -> int | None:
    entity = trigger.get("entity")
    if not isinstance(entity, dict):
        return None
    return _int_value(entity.get("id"))


def _should_enqueue_trigger(trigger: dict[str, object]) -> bool:
    return trigger.get("status") in {"queued", "running"} and trigger.get("nextAction") == "poll"
