from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.domain.services.pipelines import PipelineService
from server.tests.test_api import AUTH_HEADERS, create_manual_course, request, upload_ready_pdf


ROOT = Path(__file__).resolve().parents[2]
WEEK2_PIPELINE_STEPS = [
    "resource_validate",
    "caption_extract",
    "document_parse",
    "knowledge_extract",
    "vectorize",
]
PIPELINE_STATUS_VALUES = {
    "idle",
    "queued",
    "running",
    "partial_success",
    "succeeded",
    "failed",
}
STEP_STATUS_VALUES = {
    "queued",
    "running",
    "succeeded",
    "failed",
    "skipped",
    "partial_success",
}


def _post_parse_start(course_id: int, idempotency_key: str) -> tuple[int, dict[str, Any]]:
    return asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/parse/start",
            headers=AUTH_HEADERS | {"idempotency-key": idempotency_key},
        )
    )


def test_app_import_keeps_basic_scaffold_without_worker_side_effects():
    script = """
import json
import sys
from server.app import app

routes = sorted(getattr(route, "path", "") for route in app.routes)
print(json.dumps({
    "health": "/health" in routes,
    "parse_start": "/api/v1/courses/{courseId}/parse/start" in routes,
    "pipeline_status": "/api/v1/courses/{courseId}/pipeline-status" in routes,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["health"]
    assert payload["parse_start"]
    assert payload["pipeline_status"]
    assert payload["worker_imported"] is False
    assert payload["broker_imported"] is False
    assert payload["dramatiq_imported"] is False


def test_dramatiq_dispatcher_build_is_lazy_in_explicit_dramatiq_mode():
    script = """
import json
import os
import sys

os.environ["KNOWLINK_TASK_QUEUE"] = "dramatiq"
from server.tasks.dispatcher import build_task_dispatcher

dispatcher = build_task_dispatcher()
print(json.dumps({
    "dispatcher_class": dispatcher.__class__.__name__,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {"KNOWLINK_TASK_QUEUE": "dramatiq"},
    )
    payload = json.loads(result.stdout)

    assert payload["dispatcher_class"] == "DramatiqTaskDispatcher"
    assert payload["worker_imported"] is False
    assert payload["broker_imported"] is False
    assert payload["dramatiq_imported"] is False


def test_dramatiq_default_actor_path_resolves_parse_pipeline_actor():
    from server.tasks.dispatcher import DramatiqTaskDispatcher

    dispatcher = DramatiqTaskDispatcher()
    actor = dispatcher._load_actor(dispatcher.parse_pipeline_actor_path)

    assert hasattr(actor, "send")


def test_legacy_global_repository_backend_env_is_ignored():
    script = """
import json
from server.config.settings import get_settings

settings = get_settings()
print(json.dumps({
    "runtime_repository_backend": settings.runtime_repository_backend,
    "has_repository_backend": hasattr(settings, "repository_backend"),
}))
"""
    env = os.environ.copy()
    env["KNOWLINK_REPOSITORY_BACKEND"] = "sql"
    env.pop("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "runtime_repository_backend": "memory",
        "has_repository_backend": False,
    }


def test_runtime_repository_backend_sql_mode_keeps_week2_api_flow_on_sqlite(tmp_path):
    script = """
import asyncio
import json

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import get_engine
from server.tests.test_api import AUTH_HEADERS, request

Base.metadata.create_all(get_engine())

async def main():
    create_status, create_body = await request(
        "POST",
        "/api/v1/courses",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-course"},
        json_body={
            "title": "SQL runtime API course",
            "entryType": "manual_import",
            "goalText": "verify SQL runtime API flow",
            "preferredStyle": "balanced",
        },
    )
    course_id = create_body["data"]["course"]["courseId"]

    upload_status, upload_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/resources/upload-complete",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-upload"},
        json_body={
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/sql-runtime.pdf",
            "originalName": "sql-runtime.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:sql-runtime",
        },
    )
    resources_status, resources_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/resources",
        headers=AUTH_HEADERS,
    )
    parse_status, parse_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/parse/start",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-parse"},
    )
    pipeline_status, pipeline_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/pipeline-status",
        headers=AUTH_HEADERS,
    )

    print(json.dumps({
        "create_status": create_status,
        "upload_status": upload_status,
        "resource_id": upload_body["data"]["resourceId"],
        "resources_status": resources_status,
        "resource_ids": [
            resource["resourceId"]
            for resource in resources_body["data"]["items"]
        ],
        "parse_status": parse_status,
        "parse_entity_type": parse_body["data"]["entity"]["type"],
        "pipeline_status": pipeline_status,
        "pipeline_course_status": pipeline_body["data"]["courseStatus"]["pipelineStatus"],
        "step_codes": [
            step["code"]
            for step in pipeline_body["data"]["steps"]
        ],
    }))

asyncio.run(main())
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'runtime.sqlite3'}"
    env.pop("KNOWLINK_REPOSITORY_BACKEND", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["create_status"] == 201
    assert payload["upload_status"] == 201
    assert payload["resources_status"] == 200
    assert payload["resource_id"] in payload["resource_ids"]
    assert payload["parse_status"] == 200
    assert payload["parse_entity_type"] == "parse_run"
    assert payload["pipeline_status"] == 200
    assert payload["pipeline_course_status"] in PIPELINE_STATUS_VALUES
    assert payload["step_codes"] == WEEK2_PIPELINE_STEPS


def test_domain_services_do_not_import_worker_or_dramatiq_directly():
    service_dir = ROOT / "server/domain/services"
    forbidden_tokens = ("server.tasks", "dramatiq")

    violations: list[str] = []
    for path in sorted(service_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if f"import {token}" in text or f"from {token}" in text:
                violations.append(f"{path.relative_to(ROOT)} imports {token}")

    assert violations == []


def test_parse_start_idempotently_returns_root_parse_task_and_parse_run_entity():
    course_id, _ = create_manual_course(
        idempotency_key="runtime-contract-parse-course",
        title="Week 2 解析根任务课",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key="runtime-contract-parse-upload",
        suffix="runtime-contract-parse",
    )

    first_status, first = _post_parse_start(course_id, "runtime-contract-parse-start")
    second_status, second = _post_parse_start(course_id, "runtime-contract-parse-start")

    assert first_status == 200
    assert second_status == 200
    assert first["data"] == second["data"]

    trigger = first["data"]
    assert isinstance(trigger["taskId"], int)
    assert trigger["taskId"] > 0
    assert trigger["status"] == "queued"
    assert trigger["nextAction"] == "poll"
    assert trigger["entity"]["type"] == "parse_run"
    assert isinstance(trigger["entity"]["id"], int)

    parse_status, parse_run = asyncio.run(
        request(
            "GET",
            f"/api/v1/parse-runs/{trigger['entity']['id']}",
            headers=AUTH_HEADERS,
        )
    )
    assert parse_status == 200
    assert parse_run["data"]["parseRunId"] == trigger["entity"]["id"]
    assert parse_run["data"]["courseId"] == course_id
    assert parse_run["data"]["status"] in PIPELINE_STATUS_VALUES | {"canceled", "superseded"}
    assert 0 <= parse_run["data"]["progressPct"] <= 100


def test_pipeline_status_uses_week2_fixed_steps_and_status_enums_after_parse():
    course_id, _ = create_manual_course(
        idempotency_key="runtime-contract-pipeline-course",
        title="Week 2 五步流水线课",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key="runtime-contract-pipeline-upload",
        suffix="runtime-contract-pipeline",
    )
    parse_status, _ = _post_parse_start(course_id, "runtime-contract-pipeline-start")
    assert parse_status == 200

    status, body = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/pipeline-status",
            headers=AUTH_HEADERS,
        )
    )
    assert status == 200

    data = body["data"]
    assert data["courseStatus"]["pipelineStatus"] in PIPELINE_STATUS_VALUES
    assert 0 <= data["progressPct"] <= 100
    assert [step["code"] for step in data["steps"]] == WEEK2_PIPELINE_STEPS
    assert {step["status"] for step in data["steps"]} <= STEP_STATUS_VALUES
    for step in data["steps"]:
        assert step["label"]
        assert "pending" not in step["status"]


@dataclass
class _TaskBackedPipelineRepo:
    expected_pipeline_status: str
    step_statuses: dict[str, str]

    def get_course(self, course_id: int) -> dict[str, Any]:
        return {
            "courseId": course_id,
            "lifecycleStatus": "resource_ready",
            "pipelineStage": "parse",
            "pipelineStatus": "idle",
        }

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return [{"resourceId": 501, "resourceType": "pdf"}]

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        raise AssertionError("aggregation tests should not create parse runs")

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return None

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any]:
        return {"parseRunId": 9001, "courseId": course_id, "status": "running", "progressPct": 40}

    def run_idempotent(self, action: str, key: str | None, factory):
        return factory()

    def _async_tasks(self) -> list[dict[str, Any]]:
        tasks = [
            {
                "taskId": 7001,
                "id": 7001,
                "courseId": 101,
                "course_id": 101,
                "parseRunId": 9001,
                "parse_run_id": 9001,
                "taskType": "parse_pipeline",
                "task_type": "parse_pipeline",
                "status": self.expected_pipeline_status,
                "parentTaskId": None,
                "parent_task_id": None,
                "targetType": "parse_run",
                "target_type": "parse_run",
                "targetId": 9001,
                "target_id": 9001,
                "stepCode": None,
                "step_code": None,
                "progressPct": 100
                if self.expected_pipeline_status in {"succeeded", "partial_success"}
                else 40,
                "progress_pct": 100
                if self.expected_pipeline_status in {"succeeded", "partial_success"}
                else 40,
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
                    "id": 7001 + index,
                    "courseId": 101,
                    "course_id": 101,
                    "parseRunId": 9001,
                    "parse_run_id": 9001,
                    "taskType": task_types[code],
                    "task_type": task_types[code],
                    "status": status,
                    "parentTaskId": 7001,
                    "parent_task_id": 7001,
                    "targetType": "parse_run",
                    "target_type": "parse_run",
                    "targetId": 9001,
                    "target_id": 9001,
                    "stepCode": code,
                    "step_code": code,
                    "progressPct": 100 if status in {"succeeded", "skipped", "partial_success"} else 50,
                    "progress_pct": 100 if status in {"succeeded", "skipped", "partial_success"} else 50,
                    "resultJson": {"nonBlockingFailure": status == "partial_success"},
                    "result_json": {"non_blocking_failure": status == "partial_success"},
                    "errorCode": "demo.failure" if status == "failed" else None,
                    "error_code": "demo.failure" if status == "failed" else None,
                    "errorMessage": "contract scenario" if status == "failed" else None,
                    "error_message": "contract scenario" if status == "failed" else None,
                }
            )
        return tasks

    def list_async_tasks(self, *, course_id: int | None = None, parse_run_id: int | None = None):
        return self._async_tasks()

    def list_async_tasks_for_course(self, course_id: int):
        return self._async_tasks()

    def list_tasks_for_parse_run(self, parse_run_id: int):
        return self._async_tasks()

    def list_pipeline_steps(self, course_id: int) -> list[dict[str, Any]]:
        return [
            {
                "code": code,
                "label": {
                    "resource_validate": "资源校验",
                    "caption_extract": "字幕提取",
                    "document_parse": "文档解析",
                    "knowledge_extract": "目录抽取",
                    "vectorize": "向量化",
                }[code],
                "status": self.step_statuses[code],
                "progressPct": 100 if self.step_statuses[code] in {"succeeded", "skipped"} else 50,
                "message": "contract scenario",
                "failedResourceIds": [501] if self.step_statuses[code] == "failed" else [],
            }
            for code in WEEK2_PIPELINE_STEPS
        ]

    def aggregate_pipeline_status(self, course_id: int) -> dict[str, Any]:
        return {
            "pipelineStatus": self.expected_pipeline_status,
            "progressPct": 100 if self.expected_pipeline_status in {"succeeded", "partial_success"} else 40,
        }


class _NoopTaskDispatcher:
    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        raise AssertionError("status aggregation should not enqueue parse tasks")


class _CommitAwareParseStartRepo:
    def __init__(self) -> None:
        self.course = {
            "courseId": 201,
            "lifecycleStatus": "resource_ready",
            "pipelineStage": "idle",
            "pipelineStatus": "idle",
        }
        self.resources = [{"resourceId": 501, "resourceType": "pdf"}]
        self.parse_runs: dict[int, dict[str, Any]] = {}
        self.tasks: dict[int, dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str], dict[str, object]] = {}
        self.next_parse_run_id = 9000
        self.next_task_id = 7000
        self.in_factory = False
        self.committed = False

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.resources

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        self.next_parse_run_id += 1
        parse_run = {
            "parseRunId": self.next_parse_run_id,
            "courseId": course_id,
            "status": "queued",
            "progressPct": 0,
        }
        self.parse_runs[self.next_parse_run_id] = parse_run
        return parse_run, {}

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return self.parse_runs.get(parse_run_id)

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        if not self.parse_runs:
            return None
        return self.parse_runs[max(self.parse_runs)]

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        self.in_factory = True
        value = factory()
        self.in_factory = False
        self.committed = True
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def create_async_task(
        self,
        *,
        course_id: int,
        task_type: str,
        status: str = "queued",
        progress_pct: int = 0,
        payload_json: dict[str, Any] | None = None,
        parse_run_id: int | None = None,
        parent_task_id: int | None = None,
        target_type: str | None = None,
        target_id: int | None = None,
        step_code: str | None = None,
    ) -> dict[str, Any]:
        self.next_task_id += 1
        task = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": parse_run_id,
            "taskType": task_type,
            "status": status,
            "progressPct": progress_pct,
            "payloadJson": payload_json or {},
            "parentTaskId": parent_task_id,
            "targetType": target_type,
            "targetId": target_id,
            "stepCode": step_code,
        }
        self.tasks[self.next_task_id] = task
        return task

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            task
            for task in self.tasks.values()
            if task["courseId"] == course_id
            and (parse_run_id is None or task["parseRunId"] == parse_run_id)
        ]

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        payload_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if status is not None:
            task["status"] = status
        if progress_pct is not None:
            task["progressPct"] = progress_pct
        if payload_json is not None:
            task["payloadJson"] = payload_json
        if error_message is not None:
            task["errorMessage"] = error_message
        return task


class _CommitAwareDispatcher:
    def __init__(self, repo: _CommitAwareParseStartRepo) -> None:
        self.repo = repo
        self.calls: list[dict[str, Any]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        assert self.repo.in_factory is False
        assert self.repo.committed is True
        self.calls.append({"taskId": task_id, "payload": payload})


def test_parse_start_enqueues_after_idempotent_commit_and_not_on_duplicate_key():
    repo = _CommitAwareParseStartRepo()
    dispatcher = _CommitAwareDispatcher(repo)
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=dispatcher,
        idempotency=repo,
    )

    first = service.start_parse(course_id=201, idempotency_key="commit-aware-parse-start")
    second = service.start_parse(course_id=201, idempotency_key="commit-aware-parse-start")

    assert first == second
    assert dispatcher.calls == [
        {
            "taskId": first["taskId"],
            "payload": {
                "courseId": 201,
                "parseRunId": first["entity"]["id"],
                "resourceTypes": ["pdf"],
            },
        }
    ]


def test_pipeline_status_service_reflects_week2_aggregation_semantics():
    repo = _TaskBackedPipelineRepo(
        expected_pipeline_status="partial_success",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "skipped",
            "document_parse": "succeeded",
            "knowledge_extract": "succeeded",
            "vectorize": "partial_success",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopTaskDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=101)

    assert data["courseStatus"]["pipelineStatus"] == "partial_success"
    assert data["progressPct"] == 100
    assert [step["code"] for step in data["steps"]] == WEEK2_PIPELINE_STEPS
    assert [step["status"] for step in data["steps"]] == [
        "succeeded",
        "skipped",
        "succeeded",
        "succeeded",
        "partial_success",
    ]


def test_pipeline_status_child_partial_overrides_succeeded_root_task():
    repo = _TaskBackedPipelineRepo(
        expected_pipeline_status="succeeded",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "skipped",
            "document_parse": "succeeded",
            "knowledge_extract": "succeeded",
            "vectorize": "partial_success",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopTaskDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=101)

    assert data["courseStatus"]["pipelineStatus"] == "partial_success"


def test_pipeline_status_service_can_surface_all_step_status_values():
    repo = _TaskBackedPipelineRepo(
        expected_pipeline_status="running",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "running",
            "document_parse": "failed",
            "knowledge_extract": "queued",
            "vectorize": "partial_success",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopTaskDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=102)
    statuses = {step["status"] for step in data["steps"]}

    assert data["courseStatus"]["pipelineStatus"] == "running"
    assert statuses == {"succeeded", "running", "failed", "queued", "partial_success"}
