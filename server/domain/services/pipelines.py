from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, signature
from typing import Any

from server.domain.repositories import (
    AsyncTaskRepository,
    CourseRepository,
    IdempotencyRepository,
    ParseRunRepository,
    ResourceRepository,
    TaskDispatcher,
)
from server.domain.services.errors import ServiceError


PIPELINE_STEPS = [
    {"code": "resource_validate", "label": "资源校验", "weight": 10},
    {"code": "caption_extract", "label": "字幕提取", "weight": 20},
    {"code": "document_parse", "label": "文档解析", "weight": 25},
    {"code": "knowledge_extract", "label": "目录抽取", "weight": 25},
    {"code": "vectorize", "label": "向量化", "weight": 20},
]

DOCUMENT_RESOURCE_TYPES = {"pdf", "pptx", "docx"}
VIDEO_RESOURCE_TYPES = {"mp4", "srt"}
PIPELINE_STATUSES = {"idle", "queued", "running", "partial_success", "succeeded", "failed"}
STEP_STATUSES = {"queued", "running", "succeeded", "failed", "skipped", "partial_success"}

TASK_TYPE_TO_STEP = {
    "resource_validate": "resource_validate",
    "subtitle_extract": "caption_extract",
    "caption_extract": "caption_extract",
    "asr": "caption_extract",
    "doc_parse": "document_parse",
    "document_parse": "document_parse",
    "ocr": "document_parse",
    "outline_generate": "knowledge_extract",
    "knowledge_extract": "knowledge_extract",
    "embed": "vectorize",
    "vectorize": "vectorize",
}

INITIAL_TASK_TYPE_BY_STEP = {
    "resource_validate": "resource_validate",
    "caption_extract": "subtitle_extract",
    "document_parse": "doc_parse",
    "knowledge_extract": "knowledge_extract",
    "vectorize": "embed",
}

DEFAULT_PROGRESS_BY_STATUS = {
    "queued": 0,
    "running": 50,
    "succeeded": 100,
    "failed": 0,
    "skipped": 100,
    "partial_success": 100,
}

MESSAGE_BY_STATUS = {
    "queued": "等待执行",
    "running": "正在执行",
    "succeeded": "已完成",
    "failed": "执行失败",
    "skipped": "本课程无需执行",
    "partial_success": "部分完成，可继续使用已生成内容",
}


class PipelineService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        parse_runs: ParseRunRepository,
        resources: ResourceRepository,
        async_tasks: AsyncTaskRepository,
        task_dispatcher: TaskDispatcher,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.courses = courses
        self.parse_runs = parse_runs
        self.resources = resources
        self.async_tasks = async_tasks
        self.task_dispatcher = task_dispatcher
        self.idempotency = idempotency

    def start_parse(self, *, course_id: int, idempotency_key: str | None) -> dict[str, object]:
        course = self._ensure_course(course_id)
        resources = self.resources.list_resources(course_id)
        if not resources:
            raise ServiceError(
                message="Course is not ready for parsing.",
                error_code="pipeline.not_ready",
                status_code=409,
            )

        enqueue_request: tuple[int, dict[str, Any]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal created_response, enqueue_request
            previous_active_parse_run_id = _value(course, "activeParseRunId", "active_parse_run_id")
            parse_run, existing_trigger = self._create_parse_run(course_id)
            parse_run_id = _int_value(parse_run, "parseRunId", "parse_run_id", "id")
            if parse_run_id is None:
                raise ServiceError(
                    message="Parse run creation did not return an id.",
                    error_code="pipeline.parse_run_invalid",
                    status_code=500,
                )

            self._mark_parse_started(
                course=course,
                parse_run=parse_run,
                previous_active_parse_run_id=previous_active_parse_run_id,
            )
            resource_types = self._resource_types(resources)
            payload = {
                "courseId": course_id,
                "parseRunId": parse_run_id,
                "resourceTypes": resource_types,
            }
            root_task = self._existing_root_task(existing_trigger)
            if root_task is None:
                root_task = self._create_async_task(
                    course_id=course_id,
                    parse_run_id=parse_run_id,
                    task_type="parse_pipeline",
                    status="queued",
                    progress_pct=0,
                    payload_json=payload,
                    target_type="parse_run",
                    target_id=parse_run_id,
                )
            else:
                updated_root_task = self._update_async_task_payload(
                    task_id=_int_value(root_task, "taskId", "task_id", "id") or 0,
                    payload=payload,
                )
                if updated_root_task is not None:
                    root_task = updated_root_task
            root_task_id = _int_value(root_task, "taskId", "task_id", "id")
            if root_task_id is None:
                raise ServiceError(
                    message="Async task creation did not return an id.",
                    error_code="pipeline.task_invalid",
                    status_code=500,
                )

            self._create_initial_step_tasks(
                course_id=course_id,
                parse_run_id=parse_run_id,
                root_task_id=root_task_id,
                resource_types=resource_types,
            )
            created_response = {
                "taskId": root_task_id,
                "status": _task_status(root_task),
                "nextAction": "poll",
                "entity": {"type": "parse_run", "id": parse_run_id},
            }
            enqueue_request = (root_task_id, payload)
            return created_response

        result = self.idempotency.run_idempotent(
            "pipelines.parse_start",
            idempotency_key,
            factory,
        )
        if enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            self.task_dispatcher.enqueue_parse_pipeline(task_id=task_id, payload=payload)
        return result

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
        resources = self.resources.list_resources(course_id)
        course_tasks = self._list_async_tasks(course_id=course_id)
        parse_run = self._select_current_parse_run(course, course_tasks)
        parse_run_id = _int_value(parse_run, "parseRunId", "parse_run_id", "id") if parse_run else None
        tasks = (
            self._list_async_tasks(course_id=course_id, parse_run_id=parse_run_id)
            if parse_run_id is not None
            else course_tasks
        )
        steps = self._aggregate_steps(tasks=tasks, resources=resources, has_parse_run=parse_run is not None)
        pipeline_status = self._aggregate_pipeline_status(steps, parse_run=parse_run, tasks=tasks)
        progress_pct = self._aggregate_progress(steps, pipeline_status)
        active_parse_run_id = self._active_parse_run_id(course, parse_run, pipeline_status)

        return {
            "courseStatus": {
                "lifecycleStatus": self._lifecycle_status(course, resources, pipeline_status),
                "pipelineStage": "parse" if parse_run is not None else course["pipelineStage"],
                "pipelineStatus": pipeline_status,
            },
            "progressPct": progress_pct,
            "steps": steps,
            "activeParseRunId": active_parse_run_id,
            "activeHandoutVersionId": course.get("activeHandoutVersionId"),
            "nextAction": self._next_action(resources, pipeline_status),
            "sourceOverview": self._source_overview(resources, steps),
            "knowledgeMap": self._knowledge_map(parse_run, pipeline_status),
            "highlightSummary": self._highlight_summary(steps, pipeline_status),
        }

    def get_parse_summary(self, *, course_id: int) -> dict[str, object]:
        course = self._ensure_course(course_id)
        course_tasks = self._list_async_tasks(course_id=course_id)
        parse_run = self._select_current_parse_run(course, course_tasks)
        return {
            "courseId": course_id,
            "activeParseRunId": _value(course, "activeParseRunId", "active_parse_run_id"),
            "latestParseRunId": _value(parse_run, "parseRunId", "parse_run_id", "id") if parse_run else None,
            "segmentCount": _int_value(parse_run, "segmentCount", "segment_count", default=0) if parse_run else 0,
            "knowledgePointCount": _int_value(
                parse_run,
                "knowledgePointCount",
                "knowledge_point_count",
                default=0,
            )
            if parse_run
            else 0,
        }

    def retry_async_task(self, *, task_id: int) -> dict[str, object]:
        task = self.async_tasks.get_async_task(task_id)
        if task is None:
            raise ServiceError(
                message="Async task was not found.",
                error_code="pipeline.task_not_found",
                status_code=404,
            )
        updated = self.async_tasks.update_async_task(task_id, status="queued", progress_pct=0) or task
        if _task_type(updated) == "parse_pipeline":
            payload = _dict_value(updated, "payloadJson", "payload_json", "payload")
            self.task_dispatcher.enqueue_parse_pipeline(task_id=task_id, payload=payload)
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

    def _create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
        created = self.parse_runs.create_parse_run(course_id)
        if isinstance(created, tuple):
            return created[0], created[1] if len(created) > 1 else None
        return created, None

    def _existing_root_task(self, trigger: dict[str, Any] | None) -> dict[str, Any] | None:
        task_id = _int_value(trigger, "taskId", "task_id", "id")
        if task_id is None:
            return None
        task = self.async_tasks.get_async_task(task_id)
        if task is None:
            return None
        if _task_type(task) != "parse_pipeline":
            return None
        return task

    def _mark_parse_started(
        self,
        *,
        course: dict[str, object],
        parse_run: dict[str, Any],
        previous_active_parse_run_id: object,
    ) -> None:
        # The current memory scaffold creates a completed fake run. Normalize the
        # returned dict so API behavior matches the Week 2 async contract.
        parse_run["status"] = "queued"
        parse_run["progressPct"] = 0
        parse_run["progress_pct"] = 0
        parse_run["finishedAt"] = None
        parse_run["finished_at"] = None
        if previous_active_parse_run_id is None:
            course.pop("activeParseRunId", None)
            course.pop("active_parse_run_id", None)
        else:
            course["activeParseRunId"] = previous_active_parse_run_id
        course["pipelineStage"] = "parse"
        course["pipelineStatus"] = "queued"
        if course.get("lifecycleStatus") == "draft":
            course["lifecycleStatus"] = "resource_ready"

    def _create_initial_step_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int,
        root_task_id: int,
        resource_types: list[str],
    ) -> None:
        has_video = bool(VIDEO_RESOURCE_TYPES.intersection(resource_types))
        has_document = bool(DOCUMENT_RESOURCE_TYPES.intersection(resource_types))
        for step in PIPELINE_STEPS:
            code = step["code"]
            status = "queued"
            progress_pct = 0
            if code == "caption_extract" and not has_video:
                status = "skipped"
                progress_pct = 100
            elif code == "document_parse" and not has_document:
                status = "skipped"
                progress_pct = 100
            self._create_async_task(
                course_id=course_id,
                parse_run_id=parse_run_id,
                task_type=INITIAL_TASK_TYPE_BY_STEP[code],
                status=status,
                progress_pct=progress_pct,
                payload_json={"stepCode": code, "resourceTypes": resource_types},
                parent_task_id=root_task_id,
                step_code=code,
            )

    def _create_async_task(self, **kwargs: Any) -> dict[str, Any]:
        return _call_with_supported_kwargs(self.async_tasks.create_async_task, **kwargs)

    def _update_async_task_payload(self, *, task_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        if task_id <= 0:
            return None
        return _call_with_supported_kwargs(
            self.async_tasks.update_async_task,
            task_id=task_id,
            payload_json=payload,
        )

    def _list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return _call_with_supported_kwargs(
            self.async_tasks.list_async_tasks,
            course_id=course_id,
            parse_run_id=parse_run_id,
        )

    def _select_current_parse_run(
        self,
        course: dict[str, object],
        course_tasks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        latest_root = self._latest_root_task(course_tasks)
        latest_parse_run_id = _int_value(latest_root, "parseRunId", "parse_run_id") if latest_root else None
        if latest_parse_run_id is not None:
            parse_run = self.parse_runs.get_parse_run(latest_parse_run_id)
            if parse_run is not None:
                return parse_run
        active_parse_run_id = _int_value(course, "activeParseRunId", "active_parse_run_id")
        if active_parse_run_id is not None:
            parse_run = self.parse_runs.get_parse_run(active_parse_run_id)
            if parse_run is not None:
                return parse_run
        return self.parse_runs.get_latest_parse_run(_int_value(course, "courseId", "course_id", "id") or 0)

    def _latest_root_task(self, tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
        root_tasks = [
            task
            for task in tasks
            if _task_type(task) == "parse_pipeline" and _value(task, "parentTaskId", "parent_task_id") is None
        ]
        if not root_tasks:
            return None
        return max(root_tasks, key=lambda task: _int_value(task, "taskId", "task_id", "id", default=0) or 0)

    def _aggregate_steps(
        self,
        *,
        tasks: list[dict[str, Any]],
        resources: list[dict[str, Any]],
        has_parse_run: bool,
    ) -> list[dict[str, object]]:
        tasks_by_step: dict[str, list[dict[str, Any]]] = {step["code"]: [] for step in PIPELINE_STEPS}
        for task in tasks:
            step_code = _task_step_code(task)
            if step_code in tasks_by_step:
                tasks_by_step[step_code].append(task)

        return [
            self._aggregate_step(
                step=step,
                tasks=tasks_by_step[step["code"]],
                resources=resources,
                has_parse_run=has_parse_run,
            )
            for step in PIPELINE_STEPS
        ]

    def _aggregate_step(
        self,
        *,
        step: dict[str, Any],
        tasks: list[dict[str, Any]],
        resources: list[dict[str, Any]],
        has_parse_run: bool,
    ) -> dict[str, object]:
        code = step["code"]
        if tasks:
            status = self._aggregate_task_status(tasks)
            progress_pct = self._aggregate_task_progress(tasks, status)
            failed_resource_ids = self._failed_resource_ids(tasks)
        else:
            status = self._default_step_status(code, resources, has_parse_run)
            progress_pct = DEFAULT_PROGRESS_BY_STATUS[status]
            failed_resource_ids = []

        result: dict[str, object] = {
            "code": code,
            "label": step["label"],
            "status": status,
            "progressPct": progress_pct,
            "failedResourceIds": failed_resource_ids,
        }
        if status in {"failed", "partial_success"} or not tasks or status != "queued":
            result["message"] = MESSAGE_BY_STATUS[status]
        return result

    def _aggregate_task_status(self, tasks: list[dict[str, Any]]) -> str:
        statuses = [_task_status(task) for task in tasks]
        if any(status == "running" for status in statuses):
            return "running"
        if any(status == "partial_success" for status in statuses):
            return "partial_success"
        if any(status == "failed" for status in statuses):
            if any(status in {"succeeded", "skipped"} for status in statuses):
                return "partial_success"
            return "failed"
        if any(status == "queued" for status in statuses):
            return "queued"
        if all(status == "skipped" for status in statuses):
            return "skipped"
        if all(status in {"succeeded", "skipped"} for status in statuses):
            return "succeeded"
        return "queued"

    def _aggregate_task_progress(self, tasks: list[dict[str, Any]], status: str) -> int:
        progress_values = [
            _int_value(task, "progressPct", "progress_pct")
            for task in tasks
            if _int_value(task, "progressPct", "progress_pct") is not None
        ]
        if not progress_values:
            return DEFAULT_PROGRESS_BY_STATUS[status]
        return max(0, min(100, round(sum(progress_values) / len(progress_values))))

    def _aggregate_pipeline_status(
        self,
        steps: list[dict[str, object]],
        *,
        parse_run: dict[str, Any] | None,
        tasks: list[dict[str, Any]],
    ) -> str:
        if parse_run is None:
            return "idle"
        root_task = self._latest_root_task(tasks)
        root_status = _task_status(root_task) if root_task else None
        parse_status = _parse_run_status(parse_run)
        if parse_status == "succeeded" and any(
            step["status"] in {"failed", "partial_success"} for step in steps
        ):
            return self._failed_or_partial(steps)
        if parse_status in {"succeeded", "partial_success", "failed"}:
            return parse_status
        if root_status in {"running", "failed", "succeeded", "partial_success"}:
            if root_status == "succeeded" and any(
                step["status"] in {"failed", "partial_success"} for step in steps
            ):
                return self._failed_or_partial(steps)
            return root_status
        step_statuses = {str(step["code"]): str(step["status"]) for step in steps}
        if any(status == "running" for status in step_statuses.values()):
            return "running"
        if any(status == "queued" for status in step_statuses.values()):
            return "queued"
        if any(status in {"failed", "partial_success"} for status in step_statuses.values()):
            return self._failed_or_partial(steps)
        return "succeeded"

    def _failed_or_partial(self, steps: list[dict[str, object]]) -> str:
        statuses = {str(step["code"]): str(step["status"]) for step in steps}
        if statuses.get("resource_validate") == "failed":
            return "failed"
        if statuses.get("knowledge_extract") == "failed":
            return "failed"
        caption_unusable = statuses.get("caption_extract") in {"failed", "skipped"}
        document_unusable = statuses.get("document_parse") in {"failed", "skipped"}
        if caption_unusable and document_unusable:
            return "failed"
        return "partial_success"

    def _aggregate_progress(self, steps: list[dict[str, object]], pipeline_status: str) -> int:
        if pipeline_status == "idle":
            return 0
        if pipeline_status in {"succeeded", "partial_success"}:
            return 100
        progress = 0.0
        for step in steps:
            weight = next(item["weight"] for item in PIPELINE_STEPS if item["code"] == step["code"])
            progress_pct = _int_value(step, "progressPct", "progress_pct", default=0) or 0
            progress += weight * progress_pct / 100
        return max(0, min(100, round(progress)))

    def _default_step_status(
        self,
        code: str,
        resources: list[dict[str, Any]],
        has_parse_run: bool,
    ) -> str:
        if code == "caption_extract" and not self._has_video(resources):
            return "skipped"
        if code == "document_parse" and not self._has_document(resources):
            return "skipped"
        return "queued" if has_parse_run else "queued"

    def _active_parse_run_id(
        self,
        course: dict[str, object],
        parse_run: dict[str, Any] | None,
        pipeline_status: str,
    ) -> int | None:
        active_parse_run_id = _int_value(course, "activeParseRunId", "active_parse_run_id")
        if active_parse_run_id is not None:
            return active_parse_run_id
        if pipeline_status == "succeeded" and parse_run is not None:
            return _int_value(parse_run, "parseRunId", "parse_run_id", "id")
        return None

    def _lifecycle_status(
        self,
        course: dict[str, object],
        resources: list[dict[str, Any]],
        pipeline_status: str,
    ) -> object:
        if pipeline_status in {"succeeded", "partial_success"}:
            return "inquiry_ready"
        if resources and course.get("lifecycleStatus") == "draft":
            return "resource_ready"
        return course["lifecycleStatus"]

    def _next_action(self, resources: list[dict[str, Any]], pipeline_status: str) -> str:
        if not resources:
            return "upload_resource"
        if pipeline_status in {"queued", "running"}:
            return "wait"
        if pipeline_status == "failed":
            return "retry_parse"
        if pipeline_status in {"succeeded", "partial_success"}:
            return "enter_inquiry"
        return "upload_resource"

    def _source_overview(self, resources: list[dict[str, Any]], steps: list[dict[str, object]]) -> dict[str, object]:
        failed_resource_ids: list[int] = []
        for step in steps:
            failed_resource_ids.extend(int(item) for item in step.get("failedResourceIds", []) if item is not None)
        return {
            "videoReady": self._has_video(resources),
            "docTypes": self._resource_types(resources, allowed=DOCUMENT_RESOURCE_TYPES),
            "organizedSourceCount": len(resources),
            "failedResourceIds": sorted(set(failed_resource_ids)),
        }

    def _knowledge_map(self, parse_run: dict[str, Any] | None, pipeline_status: str) -> dict[str, object]:
        return {
            "status": "ready" if pipeline_status in {"succeeded", "partial_success"} else pipeline_status,
            "knowledgePointCount": _int_value(
                parse_run,
                "knowledgePointCount",
                "knowledge_point_count",
                default=0,
            )
            if parse_run
            else 0,
            "segmentCount": _int_value(parse_run, "segmentCount", "segment_count", default=0) if parse_run else 0,
        }

    def _highlight_summary(self, steps: list[dict[str, object]], pipeline_status: str) -> dict[str, object]:
        items = [
            str(step["message"])
            for step in steps
            if step.get("status") in {"failed", "partial_success"} and step.get("message")
        ]
        return {
            "status": "ready" if pipeline_status in {"succeeded", "partial_success"} else pipeline_status,
            "items": items,
        }

    def _resource_types(
        self,
        resources: list[dict[str, Any]],
        *,
        allowed: set[str] | None = None,
    ) -> list[str]:
        resource_types = {
            str(_value(resource, "resourceType", "resource_type"))
            for resource in resources
            if _value(resource, "resourceType", "resource_type") is not None
        }
        if allowed is not None:
            resource_types &= allowed
        return sorted(resource_types)

    def _has_video(self, resources: list[dict[str, Any]]) -> bool:
        return bool(VIDEO_RESOURCE_TYPES.intersection(self._resource_types(resources)))

    def _has_document(self, resources: list[dict[str, Any]]) -> bool:
        return bool(DOCUMENT_RESOURCE_TYPES.intersection(self._resource_types(resources)))

    def _failed_resource_ids(self, tasks: list[dict[str, Any]]) -> list[int]:
        resource_ids: list[int] = []
        for task in tasks:
            if _task_status(task) != "failed":
                continue
            for source in (task, _dict_value(task, "payloadJson", "payload_json", "payload")):
                resource_id = _int_value(source, "resourceId", "resource_id")
                if resource_id is not None:
                    resource_ids.append(resource_id)
                resource_ids.extend(
                    int(item)
                    for item in (_value(source, "resourceIds", "resource_ids") or [])
                    if item is not None
                )
        return sorted(set(resource_ids))


def _call_with_supported_kwargs(method: Callable[..., Any], **kwargs: Any) -> Any:
    parameters = signature(method).parameters.values()
    if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters):
        return method(**kwargs)
    supported = set(signature(method).parameters)
    return method(**{key: value for key, value in kwargs.items() if key in supported})


def _value(record: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    if record is None:
        return default
    for key in keys:
        if key in record:
            return record[key]
    return default


def _dict_value(record: dict[str, Any] | None, *keys: str) -> dict[str, Any]:
    value = _value(record, *keys, default={})
    return value if isinstance(value, dict) else {}


def _int_value(record: dict[str, Any] | None, *keys: str, default: int | None = None) -> int | None:
    value = _value(record, *keys, default=default)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _task_type(task: dict[str, Any] | None) -> str | None:
    value = _value(task, "taskType", "task_type")
    return str(value) if value is not None else None


def _task_step_code(task: dict[str, Any]) -> str | None:
    step_code = _value(task, "stepCode", "step_code")
    if step_code:
        return str(step_code)
    task_type = _task_type(task)
    return TASK_TYPE_TO_STEP.get(task_type or "")


def _task_status(task: dict[str, Any] | None) -> str:
    raw_status = _value(task, "status", default="queued")
    status = str(raw_status)
    if status == "retrying":
        return "running"
    if status in {"pending", "created"}:
        return "queued"
    if status == "canceled":
        return "failed"
    return status if status in STEP_STATUSES else "queued"


def _parse_run_status(parse_run: dict[str, Any]) -> str:
    raw_status = str(_value(parse_run, "status", default="queued"))
    if raw_status == "canceled":
        return "failed"
    if raw_status in PIPELINE_STATUSES:
        return raw_status
    return "queued"
