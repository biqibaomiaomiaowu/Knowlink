from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from server.domain.services.errors import ServiceError


T = TypeVar("T")
IDEMPOTENCY_EXPIRES_IN = timedelta(hours=24)
_MISSING = object()


def build_request_hash(payload: dict[str, object] | None) -> str:
    raw = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_fingerprinted_idempotent(
    idempotency: Any,
    *,
    scope: str,
    key: str | None,
    request_payload: dict[str, object] | None,
    factory: Callable[[], T],
    legacy_action: str | None = None,
    legacy_matches: Callable[[object], bool] | None = None,
) -> T:
    if not key:
        return factory()

    request_hash = build_request_hash(request_payload)
    scoped = getattr(idempotency, "run_scoped_idempotent", None)
    if callable(scoped):
        return scoped(
            scope=scope,
            key=key,
            request_hash=request_hash,
            factory=lambda: _legacy_or_factory(
                idempotency,
                key=key,
                factory=factory,
                scoped_legacy_action=scope,
                legacy_action=legacy_action,
                legacy_matches=legacy_matches,
            ),
        )

    record = _get_scoped_record(idempotency, scope, key)
    if record is not _MISSING:
        return _value_from_fingerprinted_record(record, request_hash)  # type: ignore[return-value]

    return run_scoped_idempotent(
        idempotency,
        action=scope,
        key=key,
        factory=factory,
        legacy_action=legacy_action,
        legacy_matches=legacy_matches,
    )


def _legacy_or_factory(
    idempotency: Any,
    *,
    key: str,
    factory: Callable[[], T],
    scoped_legacy_action: str | None = None,
    legacy_action: str | None,
    legacy_matches: Callable[[object], bool] | None,
) -> T:
    checked_actions: set[str] = set()
    if scoped_legacy_action is not None:
        checked_actions.add(scoped_legacy_action)
        legacy = _get_idempotency_result(idempotency, scoped_legacy_action, key)
        if legacy is not _MISSING and (legacy_matches is None or legacy_matches(legacy)):
            return legacy  # type: ignore[return-value]
    if legacy_action is not None and legacy_matches is not None:
        if legacy_action in checked_actions:
            return factory()
        legacy = _get_idempotency_result(idempotency, legacy_action, key)
        if legacy is not _MISSING and legacy_matches(legacy):
            return legacy  # type: ignore[return-value]
    return factory()


def raise_idempotency_body_mismatch() -> None:
    raise ServiceError(
        message="Idempotency key was reused with a different request body.",
        error_code="idempotency.body_mismatch",
        status_code=409,
    )


def raise_idempotency_in_progress() -> None:
    raise ServiceError(
        message="A request with the same idempotency key is still processing.",
        error_code="common.idempotency_replay",
        status_code=409,
    )


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


def _get_scoped_record(idempotency: Any, scope: str, key: str) -> object:
    records = getattr(idempotency, "idempotency_records", None)
    if isinstance(records, dict):
        value = records.get((scope, key))
        if value is not None:
            return value
    value = _get_idempotency_result(idempotency, scope, key)
    if isinstance(value, dict) and (
        "requestHash" in value
        or "request_hash" in value
        or "status" in value
        or "responseJson" in value
        or "response_json" in value
    ):
        return value
    return _MISSING


def _value_from_fingerprinted_record(record: object, request_hash: str) -> object:
    if not isinstance(record, dict):
        return record
    existing_hash = _text_value(record, "requestHash", "request_hash")
    if existing_hash is not None and existing_hash != request_hash:
        raise_idempotency_body_mismatch()
    if _text_value(record, "status") == "in_progress":
        raise_idempotency_in_progress()
    return _field_value(record, "responseJson", "response_json", "resultJson", "result_json")


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
