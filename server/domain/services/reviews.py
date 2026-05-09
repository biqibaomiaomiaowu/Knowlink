from __future__ import annotations

from server.domain.repositories import CourseRepository, IdempotencyRepository, ReviewRepository, TaskDispatcher
from server.domain.services.errors import ServiceError


class ReviewService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        reviews: ReviewRepository,
        idempotency: IdempotencyRepository,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self.courses = courses
        self.reviews = reviews
        self.idempotency = idempotency
        self.task_dispatcher = task_dispatcher

    def list_review_tasks(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return {"items": self.reviews.list_review_tasks(course_id)}

    def regenerate_review_tasks(
        self,
        *,
        course_id: int,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        enqueue_request: tuple[int, dict[str, object]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal enqueue_request, created_response
            run = self.reviews.create_review_run(course_id)
            refresh_task = run.pop("_reviewRefreshTask", None)
            if isinstance(refresh_task, dict):
                task_id = _int_value(refresh_task.get("taskId"))
                payload = refresh_task.get("payload")
                if task_id is not None and isinstance(payload, dict):
                    enqueue_request = (task_id, payload)
                    created_response = {
                        "taskId": task_id,
                        "status": "queued",
                        "nextAction": "poll",
                        "entity": {"type": "review_task_run", "id": run["reviewTaskRunId"]},
                    }
                    return created_response
            return {
                "taskId": self.reviews.next_task_id(),
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "review_task_run", "id": run["reviewTaskRunId"]},
            }

        result = self.idempotency.run_idempotent(
            "reviews.regenerate",
            idempotency_key,
            factory,
        )
        if self.task_dispatcher is not None and enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            self.task_dispatcher.enqueue_review_refresh(task_id=task_id, payload=payload)
        return result

    def get_review_run_status(self, *, review_task_run_id: int) -> dict[str, object]:
        run = self.reviews.get_review_run(review_task_run_id)
        if run is None:
            raise ServiceError(
                message="Review run was not found.",
                error_code="review.run_not_found",
                status_code=404,
            )
        return run

    def complete_review_task(self, *, review_task_id: int) -> dict[str, object]:
        return self.reviews.complete_review_task(review_task_id)

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
