from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryAsyncTaskRepository:
    def __init__(self, *, task_id_factory: Callable[[], int]) -> None:
        self._task_id_factory = task_id_factory
        self._lock = Lock()
        self._tasks: dict[int, dict[str, Any]] = {}

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
        with self._lock:
            task_id = self._task_id_factory()
            task = {
                "taskId": task_id,
                "courseId": course_id,
                "parseRunId": parse_run_id,
                "taskType": task_type,
                "status": status,
                "progressPct": progress_pct,
                "payloadJson": payload_json or {},
                "resultJson": None,
                "errorMessage": None,
                "parentTaskId": parent_task_id,
                "targetType": target_type,
                "targetId": target_id,
                "stepCode": step_code,
                "createdAt": _utcnow(),
                "updatedAt": _utcnow(),
            }
            self._tasks[task_id] = task
            return dict(task)

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task is not None else None

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            tasks = [
                dict(task)
                for task in self._tasks.values()
                if task["courseId"] == course_id
                and (parse_run_id is None or task.get("parseRunId") == parse_run_id)
            ]
        return sorted(tasks, key=lambda task: task["taskId"])

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        payload_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
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
            task["updatedAt"] = _utcnow()
            return dict(task)
