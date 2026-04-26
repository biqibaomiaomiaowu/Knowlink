from __future__ import annotations

from server.domain.repositories import (
    CourseRepository,
    IdempotencyRepository,
    ParseRunRepository,
    ResourceRepository,
)
from server.domain.services.errors import ServiceError


class PipelineService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        parse_runs: ParseRunRepository,
        resources: ResourceRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.parse_runs = parse_runs
        self.resources = resources
        self.idempotency = idempotency

    def start_parse(self, *, course_id: int, idempotency_key: str | None) -> dict[str, object]:
        course = self._ensure_course(course_id)
        if not self.resources.list_resources(course_id):
            raise ServiceError(
                message="Course is not ready for parsing.",
                error_code="pipeline.not_ready",
                status_code=409,
            )

        def factory() -> dict[str, object]:
            _, trigger = self.parse_runs.create_parse_run(course_id)
            return trigger

        _ = course
        return self.idempotency.run_idempotent(
            "pipelines.parse_start",
            idempotency_key,
            factory,
        )

    def get_parse_run(self, *, parse_run_id: int) -> dict[str, object]:
        parse_run = self.parse_runs.get_parse_run(parse_run_id)
        if parse_run is None:
            raise ServiceError(
                message="Parse run was not found.",
                error_code="pipeline.parse_run_not_found",
                status_code=404,
            )
        return parse_run

    def get_pipeline_status(self, *, course_id: int) -> dict[str, object]:
        course = self._ensure_course(course_id)
        resources_ready = bool(self.resources.list_resources(course_id))
        return {
            "courseStatus": {
                "lifecycleStatus": course["lifecycleStatus"],
                "pipelineStage": course["pipelineStage"],
                "pipelineStatus": course["pipelineStatus"],
            },
            "progressPct": 100 if course.get("activeParseRunId") else 0,
            "steps": [
                {
                    "code": "resource_validate",
                    "label": "资源校验",
                    "status": "succeeded" if resources_ready else "pending",
                },
                {
                    "code": "knowledge_extract",
                    "label": "知识点抽取",
                    "status": "succeeded" if course.get("activeParseRunId") else "pending",
                },
            ],
            "activeParseRunId": course.get("activeParseRunId"),
            "activeHandoutVersionId": course.get("activeHandoutVersionId"),
            "nextAction": "enter_inquiry" if course.get("activeParseRunId") else "upload_resource",
            "sourceOverview": {
                "videoReady": resources_ready,
                "docTypes": [item.get("resourceType") for item in self.resources.list_resources(course_id)],
                "organizedSourceCount": len(self.resources.list_resources(course_id)),
            },
            "knowledgeMap": {
                "status": "ready" if course.get("activeParseRunId") else "pending",
                "knowledgePointCount": 5 if course.get("activeParseRunId") else 0,
                "segmentCount": 12 if course.get("activeParseRunId") else 0,
            },
            "highlightSummary": {
                "status": "ready" if course.get("activeParseRunId") else "pending",
                "items": [
                    "重点公式与高频题型已抽取",
                    "已生成下一步 AI 个性化问询入口",
                ]
                if course.get("activeParseRunId")
                else [],
            },
        }

    def get_parse_summary(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        parse_run = self.parse_runs.get_latest_parse_run(course_id)
        return {
            "courseId": course_id,
            "activeParseRunId": parse_run["parseRunId"] if parse_run else None,
            "segmentCount": 12 if parse_run else 0,
            "knowledgePointCount": 5 if parse_run else 0,
        }

    def retry_async_task(self, *, task_id: int) -> dict[str, object]:
        return {"taskId": task_id, "status": "queued", "nextAction": "poll"}

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course
