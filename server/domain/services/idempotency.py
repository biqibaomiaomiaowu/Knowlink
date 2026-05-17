from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar


T = TypeVar("T")
_MISSING = object()


def run_scoped_idempotent(
    idempotency: Any,
    *,
    action: str,
    key: str | None,
    factory: Callable[[], T],
    legacy_action: str | None = None,
    legacy_matches: Callable[[object], bool] | None = None,
) -> T:
    if not key:
        return idempotency.run_idempotent(action, key, factory)

    scoped = _get_idempotency_result(idempotency, action, key)
    if scoped is not _MISSING:
        return scoped  # type: ignore[return-value]

    if legacy_action is not None and legacy_matches is not None:
        legacy = _get_idempotency_result(idempotency, legacy_action, key)
        if legacy is not _MISSING and legacy_matches(legacy):
            return idempotency.run_idempotent(action, key, lambda: legacy)

    return idempotency.run_idempotent(action, key, factory)


def result_matches_course(result: object, *, course_id: int) -> bool:
    return isinstance(result, dict) and _course_id_from_record(result) == course_id


def recommendation_result_matches_catalog(result: object, *, catalog_id: str) -> bool:
    if not isinstance(result, dict):
        return False
    created_from = _text_value(result, "createdFromCatalogId", "created_from_catalog_id")
    if created_from == catalog_id:
        return True
    course = result.get("course")
    return isinstance(course, dict) and _text_value(course, "catalogId", "catalog_id") == catalog_id


def async_trigger_matches_course(
    result: object,
    *,
    course_id: int,
    entity_type: str,
    task_type: str,
    async_tasks: Any,
    target_type: str | None = None,
) -> bool:
    if not isinstance(result, dict):
        return False
    entity_id = _entity_id(result, entity_type=entity_type)
    if entity_id is None:
        return False

    task = _task_for_result(async_tasks, result)
    if not isinstance(task, dict):
        return _course_id_from_record(result) == course_id
    if _text_value(task, "taskType", "task_type") != task_type:
        return False
    if target_type is not None and _text_value(task, "targetType", "target_type") != target_type:
        return False
    target_id = _int_value(_field_value(task, "targetId", "target_id"))
    if target_id is not None and target_id != entity_id:
        return False
    return _course_id_from_record(task) == course_id


def review_result_matches_course(
    result: object,
    *,
    course_id: int,
    async_tasks: Any,
) -> bool:
    if async_trigger_matches_course(
        result,
        course_id=course_id,
        entity_type="review_task_run",
        task_type="review_refresh",
        async_tasks=async_tasks,
        target_type="review_task_run",
    ):
        return True
    if not isinstance(result, dict):
        return False
    if _int_value(_field_value(result, "reviewTaskRunId", "review_task_run_id", "id")) is None:
        return False
    return _course_id_from_record(result) == course_id


def _get_idempotency_result(idempotency: Any, action: str, key: str) -> object:
    read = getattr(idempotency, "get_idempotency_result", None)
    if read is None:
        return _MISSING
    value = read(action, key)
    if value is None:
        return _MISSING
    return value


def _task_for_result(async_tasks: Any, result: dict[str, object]) -> dict[str, object] | None:
    task_id = _int_value(_field_value(result, "taskId", "task_id"))
    get_task = getattr(async_tasks, "get_async_task", None)
    if task_id is None or get_task is None:
        return None
    task = get_task(task_id)
    return task if isinstance(task, dict) else None


def _entity_id(result: dict[str, object], *, entity_type: str) -> int | None:
    entity = result.get("entity")
    if not isinstance(entity, dict):
        return None
    if _text_value(entity, "type") != entity_type:
        return None
    return _int_value(_field_value(entity, "id"))


def _course_id_from_record(record: dict[str, object]) -> int | None:
    course_id = _int_value(_field_value(record, "courseId", "course_id"))
    if course_id is not None:
        return course_id
    payload = _dict_value(record, "payload", "payloadJson", "payload_json")
    if payload is None:
        return None
    return _int_value(_field_value(payload, "courseId", "course_id"))


def _dict_value(record: dict[str, object], *keys: str) -> dict[str, object] | None:
    value = _field_value(record, *keys)
    return value if isinstance(value, dict) else None


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
