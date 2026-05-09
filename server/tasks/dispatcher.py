from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import Parameter, signature
from typing import Any


LOGGER = logging.getLogger(__name__)


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

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "handout_generate",
                "payload": payload,
                "adapter": "noop",
            }
        )

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "handout_block_generate",
                "payload": payload,
                "adapter": "noop",
            }
        )

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _log_enqueue("quiz_generate", task_id=task_id, payload=payload, adapter="noop")
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "quiz_generate",
                "payload": payload,
                "adapter": "noop",
            }
        )

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _log_enqueue("review_refresh", task_id=task_id, payload=payload, adapter="noop")
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "review_refresh",
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

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "handout_generate",
                "payload": payload,
                "adapter": "in_memory",
            }
        )
        _call_with_supported_kwargs(
            self.async_tasks.update_async_task,
            task_id=task_id,
            status="succeeded",
            progress_pct=100,
        )

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "handout_block_generate",
                "payload": payload,
                "adapter": "in_memory",
            }
        )
        _call_with_supported_kwargs(
            self.async_tasks.update_async_task,
            task_id=task_id,
            status="succeeded",
            progress_pct=100,
        )

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _log_enqueue("quiz_generate", task_id=task_id, payload=payload, adapter="in_memory")
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "quiz_generate",
                "payload": payload,
                "adapter": "in_memory",
            }
        )

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _log_enqueue("review_refresh", task_id=task_id, payload=payload, adapter="in_memory")
        self.enqueued.append(
            {
                "taskId": task_id,
                "taskType": "review_refresh",
                "payload": payload,
                "adapter": "in_memory",
            }
        )


@dataclass
class DramatiqTaskDispatcher:
    parse_pipeline_actor_path: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLINK_PARSE_PIPELINE_ACTOR",
            "server.tasks.worker:parse_pipeline",
        )
    )
    handout_generate_actor_path: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLINK_HANDOUT_GENERATE_ACTOR",
            "server.tasks.worker:handout_generate",
        )
    )
    handout_block_generate_actor_path: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLINK_HANDOUT_BLOCK_GENERATE_ACTOR",
            "server.tasks.worker:handout_block_generate",
        )
    )
    quiz_generate_actor_path: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLINK_QUIZ_GENERATE_ACTOR",
            "server.tasks.worker:quiz_generate",
        )
    )
    review_refresh_actor_path: str = field(
        default_factory=lambda: os.getenv(
            "KNOWLINK_REVIEW_REFRESH_ACTOR",
            "server.tasks.worker:review_refresh",
        )
    )

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        actor = self._load_actor(self.parse_pipeline_actor_path)
        actor.send({"taskId": task_id, **payload})

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        actor = self._load_actor(self.handout_generate_actor_path)
        actor.send({"taskId": task_id, **payload})

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        actor = self._load_actor(self.handout_block_generate_actor_path)
        actor.send({"taskId": task_id, **payload})

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _log_enqueue("quiz_generate", task_id=task_id, payload=payload, adapter="dramatiq")
        actor = self._load_actor(self.quiz_generate_actor_path)
        actor.send({"taskId": task_id, **payload})

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _log_enqueue("review_refresh", task_id=task_id, payload=payload, adapter="dramatiq")
        actor = self._load_actor(self.review_refresh_actor_path)
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


def _log_enqueue(task_type: str, *, task_id: int, payload: dict[str, Any], adapter: str) -> None:
    LOGGER.info(
        "task enqueued",
        extra={
            "task_id": task_id,
            "task_type": task_type,
            "course_id": _int_value(payload, "courseId", "course_id"),
            "target_id": _int_value(payload, "quizId", "quiz_id", "reviewTaskRunId", "review_task_run_id"),
            "adapter": adapter,
        },
    )


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
