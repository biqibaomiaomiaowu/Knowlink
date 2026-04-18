from __future__ import annotations

from datetime import timedelta

from server.domain.repositories import CourseRepository, IdempotencyRepository, ResourceRepository
from server.domain.services.errors import ServiceError
from server.infra.repositories.memory_runtime import utcnow


class ResourceService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        resources: ResourceRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.resources = resources
        self.idempotency = idempotency

    def upload_init(self, *, course_id: int, payload, request_host: str) -> dict[str, object]:
        self._ensure_course(course_id)
        object_key = f"raw/1/{course_id}/temp/{payload.filename}"
        return {
            "uploadUrl": f"https://{request_host}/upload/demo",
            "objectKey": object_key,
            "headers": {"x-amz-meta-course-id": str(course_id)},
            "expiresAt": utcnow() + timedelta(minutes=15),
        }

    def upload_complete(
        self,
        *,
        course_id: int,
        payload,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)

        def factory() -> dict[str, object]:
            return self.resources.create_resource(
                course_id,
                payload.model_dump(by_alias=True),
            )

        return self.idempotency.run_idempotent(
            "resources.upload_complete",
            idempotency_key,
            factory,
        )

    def list_resources(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return {"items": self.resources.list_resources(course_id)}

    def delete_resource(self, *, course_id: int, resource_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        deleted = self.resources.delete_resource(course_id, resource_id)
        if not deleted:
            raise ServiceError(
                message="Resource was not found.",
                error_code="resource.not_found",
                status_code=404,
            )
        return {"deleted": True, "resourceId": resource_id}

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course
