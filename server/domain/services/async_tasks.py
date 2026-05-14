from __future__ import annotations

from collections.abc import Callable
from inspect import Parameter, signature
from typing import Any

from server.domain.services.errors import ServiceError


ENQUEUE_FAILED_ERROR_CODE = "async_task.enqueue_failed"


def enqueue_or_mark_failed(
    async_tasks: Any,
    *,
    task_id: int,
    enqueue: Callable[[], None],
    on_failure: Callable[[Exception], None] | None = None,
) -> None:
    try:
        enqueue()
    except Exception as exc:
        mark_task_enqueue_failed(async_tasks, task_id=task_id, exc=exc)
        if on_failure is not None:
            on_failure(exc)
        raise ServiceError(
            message="Async task could not be enqueued.",
            error_code=ENQUEUE_FAILED_ERROR_CODE,
            status_code=503,
        ) from exc


def enqueue_or_fail_if_missing_dispatcher(
    async_tasks: Any,
    *,
    task_id: int,
    dispatcher: Any,
    enqueue: Callable[[], None],
) -> None:
    if dispatcher is None:
        exc = RuntimeError("Task dispatcher is not configured.")
        mark_task_enqueue_failed(async_tasks, task_id=task_id, exc=exc)
        raise ServiceError(
            message="Async task could not be enqueued because task dispatcher is not configured.",
            error_code=ENQUEUE_FAILED_ERROR_CODE,
            status_code=503,
        ) from exc
    enqueue_or_mark_failed(async_tasks, task_id=task_id, enqueue=enqueue)


def mark_task_enqueue_failed(async_tasks: Any, *, task_id: int, exc: Exception) -> None:
    update = getattr(async_tasks, "update_async_task", None)
    if update is None:
        return
    _call_with_supported_kwargs(
        update,
        task_id=task_id,
        status="failed",
        progress_pct=0,
        error_code=ENQUEUE_FAILED_ERROR_CODE,
        error_message=str(exc),
    )


def raise_async_task_binding_failed(async_tasks: Any, *, task_id: int | None, message: str) -> None:
    _raise_async_task_binding_failed(async_tasks, task_id=task_id, message=message)


def ensure_async_task_for_trigger(
    async_tasks: Any,
    trigger: dict[str, object],
    *,
    course_id: int | None,
    task_type: str,
    payload: dict[str, object],
    target_type: str | None,
    target_id: int | None,
    parse_run_id: int | None = None,
    allow_create: bool = False,
) -> tuple[dict[str, object], int | None]:
    task_id = _int_value(trigger.get("taskId") or trigger.get("task_id"))
    should_bind = trigger.get("status") == "queued" and trigger.get("nextAction") == "poll"
    if not should_bind:
        return trigger, task_id
    if task_id is None:
        if allow_create:
            _raise_async_task_binding_failed(
                async_tasks,
                task_id=None,
                message="Async task trigger did not include a task id.",
            )
        return trigger, None
    if async_tasks is None:
        if allow_create:
            _raise_async_task_binding_failed(
                async_tasks,
                task_id=task_id,
                message="Async task repository is not configured.",
            )
        return trigger, task_id

    get_task = getattr(async_tasks, "get_async_task", None)
    if get_task is None:
        if allow_create:
            _raise_async_task_binding_failed(
                async_tasks,
                task_id=task_id,
                message="Async task repository cannot verify tasks.",
            )
        return trigger, None

    existing = get_task(task_id)
    if isinstance(existing, dict):
        if _task_matches(
            existing,
            course_id=course_id,
            task_type=task_type,
            target_type=target_type,
            target_id=target_id,
            parse_run_id=parse_run_id,
        ):
            return trigger, task_id
        if not allow_create:
            return trigger, None
    elif not allow_create:
        return trigger, None

    create_task = getattr(async_tasks, "create_async_task", None)
    if create_task is None or course_id is None:
        _raise_async_task_binding_failed(
            async_tasks,
            task_id=task_id,
            message="Async task repository cannot create a replacement task.",
        )

    created = _call_with_supported_kwargs(
        create_task,
        course_id=course_id,
        task_type=task_type,
        status="queued",
        progress_pct=0,
        payload_json=payload,
        parse_run_id=parse_run_id,
        target_type=target_type,
        target_id=target_id,
    )
    if not isinstance(created, dict):
        _raise_async_task_binding_failed(
            async_tasks,
            task_id=task_id,
            message="Async task creation did not return a task record.",
        )
    real_task_id = _int_value(created.get("taskId") or created.get("task_id"))
    if real_task_id is None:
        _raise_async_task_binding_failed(
            async_tasks,
            task_id=task_id,
            message="Async task creation did not return a task id.",
        )
    verified = get_task(real_task_id)
    if not isinstance(verified, dict) or not _task_matches(
        verified,
        course_id=course_id,
        task_type=task_type,
        target_type=target_type,
        target_id=target_id,
        parse_run_id=parse_run_id,
    ):
        message = "Async task creation could not be verified."
        if real_task_id != task_id:
            mark_task_enqueue_failed(async_tasks, task_id=real_task_id, exc=RuntimeError(message))
        _raise_async_task_binding_failed(async_tasks, task_id=task_id, message=message)
    updated_trigger = dict(trigger)
    updated_trigger["taskId"] = real_task_id
    return updated_trigger, real_task_id


def _task_matches(
    task: dict[str, object],
    *,
    course_id: int | None,
    task_type: str,
    target_type: str | None,
    target_id: int | None,
    parse_run_id: int | None,
) -> bool:
    if _text_value(task, "taskType", "task_type") != task_type:
        return False
    if course_id is not None and _int_value(_field_value(task, "courseId", "course_id")) != course_id:
        return False
    if target_type is not None and _text_value(task, "targetType", "target_type") != target_type:
        return False
    if target_id is not None and _int_value(_field_value(task, "targetId", "target_id")) != target_id:
        return False
    if parse_run_id is not None and _int_value(_field_value(task, "parseRunId", "parse_run_id")) != parse_run_id:
        return False
    return True


def refresh_enqueue_failure_status(async_tasks: Any, response: dict[str, object]) -> dict[str, object]:
    task_id = _int_value(response.get("taskId"))
    get_task = getattr(async_tasks, "get_async_task", None)
    if task_id is None or get_task is None:
        return response
    task = get_task(task_id)
    if not isinstance(task, dict):
        return response
    status = task.get("status")
    error_code = task.get("errorCode") or task.get("error_code")
    if status != "failed" or error_code != ENQUEUE_FAILED_ERROR_CODE:
        return response
    refreshed = dict(response)
    refreshed["status"] = "failed"
    refreshed["nextAction"] = "retry"
    error_message = task.get("errorMessage") or task.get("error_message")
    if error_code is not None:
        refreshed["errorCode"] = error_code
    if error_message is not None:
        refreshed["errorMessage"] = error_message
    return refreshed


def _raise_async_task_binding_failed(async_tasks: Any, *, task_id: int | None, message: str) -> None:
    exc = RuntimeError(message)
    if task_id is not None:
        mark_task_enqueue_failed(async_tasks, task_id=task_id, exc=exc)
    raise ServiceError(
        message="Async task could not be enqueued.",
        error_code=ENQUEUE_FAILED_ERROR_CODE,
        status_code=503,
    ) from exc


def resolve_async_tasks(*candidates: Any) -> Any | None:
    for candidate in candidates:
        if hasattr(candidate, "get_async_task") and hasattr(candidate, "update_async_task"):
            return candidate
    return None


def _call_with_supported_kwargs(method: Callable[..., Any], **kwargs: Any) -> Any:
    parameters = signature(method).parameters.values()
    if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters):
        return method(**kwargs)
    supported = set(signature(method).parameters)
    return method(**{key: value for key, value in kwargs.items() if key in supported})


def _field_value(record: dict[str, object], *keys: str) -> object:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _text_value(record: dict[str, object], *keys: str) -> str | None:
    value = _field_value(record, *keys)
    if value is None:
        return None
    return str(value)


def _int_value(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
