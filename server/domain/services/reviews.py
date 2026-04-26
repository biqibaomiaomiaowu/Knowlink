from __future__ import annotations

from server.domain.repositories import CourseRepository, IdempotencyRepository, ReviewRepository
from server.domain.services.errors import ServiceError


class ReviewService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        reviews: ReviewRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.reviews = reviews
        self.idempotency = idempotency

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

        def factory() -> dict[str, object]:
            run = self.reviews.create_review_run(course_id)
            return {
                "taskId": self.reviews.next_task_id(),
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "review_task_run", "id": run["reviewTaskRunId"]},
            }

        return self.idempotency.run_idempotent(
            "reviews.regenerate",
            idempotency_key,
            factory,
        )

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
