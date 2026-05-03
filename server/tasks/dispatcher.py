from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import Parameter, signature
from typing import Any


class NoopTaskDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[dict[str, Any]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "parse_pipeline",
                "payload": payload,
                "adapter": "noop",
            }
        )


class InMemoryTaskDispatcher:
    def __init__(self, *, parse_runs: Any, async_tasks: Any) -> None:
        self.parse_runs = parse_runs
        self.async_tasks = async_tasks
        self.enqueued: list[dict[str, Any]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "parse_pipeline",
                "payload": payload,
                "adapter": "in_memory",
            }
        )
        course_id = _int_value(payload, "courseId", "course_id")
        parse_run_id = _int_value(payload, "parseRunId", "parse_run_id")
        if course_id is None or parse_run_id is None:
            return

        for task in _call_with_supported_kwargs(
            self.async_tasks.list_async_tasks,
            course_id=course_id,
            parse_run_id=parse_run_id,
        ):
            current_status = str(task.get("status", "queued"))
            next_status = "skipped" if current_status == "skipped" else "succeeded"
            _call_with_supported_kwargs(
                self.async_tasks.update_async_task,
                task_id=int(task["taskId"]),
                status=next_status,
                progress_pct=100,
            )

        mark_succeeded = getattr(self.parse_runs, "mark_parse_run_succeeded", None)
        if callable(mark_succeeded):
            _call_with_supported_kwargs(mark_succeeded, parse_run_id=parse_run_id)


@dataclass
class DramatiqTaskDispatcher:
    parse_pipeline_actor_path: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLINK_PARSE_PIPELINE_ACTOR",
            "server.tasks.worker:parse_pipeline",
        )
    )

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        actor = self._load_actor(self.parse_pipeline_actor_path)
        actor.send({"taskId": task_id, **payload})

    def _load_actor(self, actor_path: str) -> Any:
        module_name, _, attr_name = actor_path.partition(":")
        if not module_name or not attr_name:
            raise RuntimeError("KNOWLINK_PARSE_PIPELINE_ACTOR must use module:attribute format.")
        module = importlib.import_module(module_name)
        return getattr(module, attr_name)


def build_task_dispatcher() -> NoopTaskDispatcher | DramatiqTaskDispatcher:
    queue_mode = os.getenv("KNOWLINK_TASK_QUEUE", "noop").lower()
    if queue_mode == "dramatiq":
        return DramatiqTaskDispatcher()
    return NoopTaskDispatcher()


def _call_with_supported_kwargs(method: Callable[..., Any], **kwargs: Any) -> Any:
    parameters = signature(method).parameters.values()
    if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters):
        return method(**kwargs)
    supported = set(signature(method).parameters)
    return method(**{key: value for key, value in kwargs.items() if key in supported})


def _int_value(record: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None
