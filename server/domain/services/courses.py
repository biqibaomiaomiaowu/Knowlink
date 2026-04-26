from __future__ import annotations

from server.domain.repositories import CourseRepository, IdempotencyRepository


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
                )
            }

        return self.idempotency.run_idempotent("courses.create", idempotency_key, factory)

    def list_recent_courses(self) -> dict[str, object]:
        return {"items": self.courses.list_recent_courses()}
