from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.domain.services.pipelines import PipelineService


WEEK2_PIPELINE_STEPS = [
    "resource_validate",
    "caption_extract",
    "document_parse",
    "knowledge_extract",
    "vectorize",
]


@dataclass
class _PipelineRepo:
    pipeline_status: str
    step_statuses: dict[str, str]

    def get_course(self, course_id: int) -> dict[str, Any]:
        return {
            "courseId": course_id,
            "lifecycleStatus": "resource_ready",
            "pipelineStage": "parse",
            "pipelineStatus": "running",
        }

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return [{"resourceId": 501, "resourceType": "pdf"}]

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return {
            "parseRunId": parse_run_id,
            "courseId": 101,
            "status": self.pipeline_status,
            "progressPct": 100,
            "segmentCount": 12,
            "knowledgePointCount": 4,
        }

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any]:
        return self.get_parse_run(9001) or {}

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._tasks()

    def run_idempotent(self, action: str, key: str | None, factory):
        return factory()

    def _tasks(self) -> list[dict[str, Any]]:
        tasks = [
            {
                "taskId": 7001,
                "courseId": 101,
                "parseRunId": 9001,
                "taskType": "parse_pipeline",
                "status": self.pipeline_status,
                "parentTaskId": None,
                "progressPct": 100,
            }
        ]
        task_types = {
            "resource_validate": "resource_validate",
            "caption_extract": "asr",
            "document_parse": "doc_parse",
            "knowledge_extract": "knowledge_extract",
            "vectorize": "embed",
        }
        for index, code in enumerate(WEEK2_PIPELINE_STEPS, start=1):
            status = self.step_statuses[code]
            tasks.append(
                {
                    "taskId": 7001 + index,
                    "courseId": 101,
                    "parseRunId": 9001,
                    "taskType": task_types[code],
                    "status": status,
                    "parentTaskId": 7001,
                    "stepCode": code,
                    "progressPct": 100
                    if status in {"succeeded", "skipped", "partial_success"}
                    else 50,
                    "errorCode": "embedding.dimension_mismatch"
                    if code == "vectorize" and status == "failed"
                    else None,
                    "errorMessage": "Embedding dimension mismatch"
                    if code == "vectorize" and status == "failed"
                    else None,
                }
            )
        return tasks


class _NoopDispatcher:
    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        raise AssertionError("status aggregation must not enqueue parse tasks")


def test_pipeline_status_downgrades_vectorize_failed_for_partial_success():
    repo = _PipelineRepo(
        pipeline_status="partial_success",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "skipped",
            "document_parse": "succeeded",
            "knowledge_extract": "succeeded",
            "vectorize": "failed",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=101)
    vectorize_step = next(
        step for step in data["steps"] if step["code"] == "vectorize"
    )

    assert data["courseStatus"]["pipelineStatus"] == "partial_success"
    assert vectorize_step["status"] == "partial_success"
    assert vectorize_step["progressPct"] == 100
    assert vectorize_step["message"] == "部分完成，可继续使用已生成内容"
    assert data["highlightSummary"]["items"] == ["部分完成，可继续使用已生成内容"]
