from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.domain.services.pipelines import PipelineService
from server.infra.db.base import Base


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_RUNTIME_TABLE_COLUMNS = {
    "parse_runs": {
        "course_id",
        "status",
        "trigger_type",
        "source_parse_run_id",
        "progress_pct",
        "summary_json",
        "started_at",
        "finished_at",
    },
    "async_tasks": {
        "parse_run_id",
        "course_id",
        "resource_id",
        "task_type",
        "status",
        "parent_task_id",
        "target_type",
        "target_id",
        "step_code",
        "progress_pct",
        "payload_json",
        "result_json",
        "error_code",
        "error_message",
        "retry_count",
        "started_at",
        "finished_at",
    },
    "course_segments": {
        "course_id",
        "resource_id",
        "parse_run_id",
        "segment_type",
        "title",
        "section_path",
        "text_content",
        "plain_text",
        "start_sec",
        "end_sec",
        "page_no",
        "slide_no",
        "image_key",
        "formula_text",
        "bbox_json",
        "order_no",
        "token_count",
        "is_active",
    },
    "learning_preferences": {
        "user_id",
        "course_id",
        "goal_type",
        "self_level",
        "time_budget_minutes",
        "exam_at",
        "preferred_style",
        "example_density",
        "formula_detail_level",
        "language_style",
        "focus_knowledge_json",
        "inquiry_answers_json",
        "confirmed_at",
    },
    "vector_documents": {
        "course_id",
        "parse_run_id",
        "handout_version_id",
        "owner_type",
        "owner_id",
        "resource_id",
        "content_text",
        "metadata_json",
        "embedding",
    },
}


def _import_db_models() -> None:
    models_pkg = importlib.import_module("server.infra.db.models")
    for module_info in pkgutil.iter_modules(models_pkg.__path__, f"{models_pkg.__name__}."):
        importlib.import_module(module_info.name)


def _migration_text() -> str:
    versions_dir = ROOT / "alembic/versions"
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(versions_dir.glob("*.py")))


def _value(entity: Any, *names: str) -> Any:
    if isinstance(entity, dict):
        for name in names:
            if name in entity:
                return entity[name]
    for name in names:
        if hasattr(entity, name):
            return getattr(entity, name)
    pytest.fail(f"Could not read any of {names!r} from {entity!r}")


def _call_with_supported_kwargs(method: Callable[..., Any], **kwargs: Any) -> Any:
    signature = inspect.signature(method)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return method(**kwargs)
    filtered = {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
    }
    return method(**filtered)


def _discover_sql_repository_class() -> type[Any]:
    repositories_pkg = importlib.import_module("server.infra.repositories")
    required_methods = {
        "run_idempotent",
        "create_course",
        "create_resource",
        "list_resources",
        "create_parse_run",
        "get_async_task",
        "list_async_tasks",
        "update_async_task",
        "save_inquiry_answers",
    }
    candidates: list[str] = []

    for module_info in pkgutil.iter_modules(repositories_pkg.__path__, f"{repositories_pkg.__name__}."):
        if module_info.name.endswith((".memory", ".memory_runtime")):
            continue
        module = importlib.import_module(module_info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not cls.__module__.startswith("server.infra.repositories"):
                continue
            class_name = cls.__name__.lower()
            if "memory" in class_name:
                continue
            if not any(token in class_name for token in ("sql", "alchemy", "db")):
                continue
            if required_methods <= set(dir(cls)):
                return cls
            candidates.append(f"{cls.__module__}.{cls.__name__}")

    pytest.fail(
        "Expected a synchronous SQL repository under server.infra.repositories with "
        f"{sorted(required_methods)}. Discovered candidates: {candidates}"
    )


def _build_sqlite_repository(repository_cls: type[Any]):
    _import_db_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()

    attempts = [
        lambda: repository_cls(session),
        lambda: repository_cls(db=session),
        lambda: repository_cls(session=session),
        lambda: repository_cls(sync_session=session),
        lambda: repository_cls(session_factory=session_factory),
        lambda: repository_cls(engine=engine),
    ]
    errors: list[str] = []
    for attempt in attempts:
        try:
            return attempt(), session, engine
        except TypeError as exc:
            errors.append(str(exc))
    pytest.fail(
        f"Could not instantiate {repository_cls.__module__}.{repository_cls.__name__} "
        f"with a SQLite sync session/engine. Errors: {errors}"
    )


def test_week2_runtime_models_and_migrations_expose_key_fields():
    _import_db_models()
    migration = _migration_text()
    failures: list[str] = []

    for table_name, expected_columns in EXPECTED_RUNTIME_TABLE_COLUMNS.items():
        table = Base.metadata.tables.get(table_name)
        if table is None:
            failures.append(f"{table_name} missing from SQLAlchemy metadata")
        else:
            actual_columns = set(table.c.keys())
            missing_columns = sorted(expected_columns - actual_columns)
            if missing_columns:
                failures.append(f"{table_name} model missing columns: {missing_columns}")

        if not re.search(rf"create_table\(\s*['\"]{re.escape(table_name)}['\"]", migration):
            failures.append(f"{table_name} missing from Alembic migrations")
        for column in expected_columns:
            if f"'{column}'" not in migration and f'"{column}"' not in migration:
                failures.append(f"{table_name}.{column} missing from Alembic migrations")

    assert failures == []


def test_sync_sql_repository_closes_course_resource_parse_task_and_inquiry_on_sqlite():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.run_idempotent(
        "courses.create",
        "sqlite-course-1",
        lambda: _call_with_supported_kwargs(
            repo.create_course,
            user_id=1,
            title="SQLite Week 2 闭环课",
            entry_type="manual_import",
            goal_text="验证 SQL repository 幂等闭环",
            preferred_style="balanced",
            catalog_id=None,
        ),
    )
    same_course = repo.run_idempotent(
        "courses.create",
        "sqlite-course-1",
        lambda: _call_with_supported_kwargs(
            repo.create_course,
            user_id=1,
            title="不应写入的新标题",
            entry_type="manual_import",
            goal_text="第二次调用应命中幂等结果",
            preferred_style="exam",
            catalog_id=None,
        ),
    )
    course_id = _value(course, "courseId", "course_id", "id")
    assert _value(same_course, "courseId", "course_id", "id") == course_id

    resource_payload = {
        "resourceType": "pdf",
        "objectKey": f"raw/1/{course_id}/sqlite-contract.pdf",
        "originalName": "sqlite-contract.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 2048,
        "checksum": "sha256:sqlite-contract",
    }
    resource = repo.run_idempotent(
        "resources.upload_complete",
        "sqlite-resource-1",
        lambda: repo.create_resource(course_id, resource_payload),
    )
    same_resource = repo.run_idempotent(
        "resources.upload_complete",
        "sqlite-resource-1",
        lambda: repo.create_resource(course_id, resource_payload | {"checksum": "sha256:changed"}),
    )
    resource_id = _value(resource, "resourceId", "resource_id", "id")
    assert _value(same_resource, "resourceId", "resource_id", "id") == resource_id
    assert any(
        _value(item, "resourceId", "resource_id", "id") == resource_id
        for item in repo.list_resources(course_id)
    )

    parse_run, trigger = repo.run_idempotent(
        "pipelines.parse_start",
        "sqlite-parse-1",
        lambda: repo.create_parse_run(course_id),
    )
    same_parse_run, same_trigger = repo.run_idempotent(
        "pipelines.parse_start",
        "sqlite-parse-1",
        lambda: repo.create_parse_run(course_id),
    )
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    task_id = _value(trigger, "taskId", "task_id", "id")
    assert _value(same_parse_run, "parseRunId", "parse_run_id", "id") == parse_run_id
    assert _value(same_trigger, "taskId", "task_id", "id") == task_id
    trigger_entity = _value(trigger, "entity")
    assert _value(trigger_entity, "type") == "parse_run"
    assert _value(trigger_entity, "id") == parse_run_id

    async_tasks = Base.metadata.tables.get("async_tasks")
    assert async_tasks is not None
    task_row = session.execute(
        sa.select(async_tasks).where(async_tasks.c.id == task_id)
    ).mappings().one()
    assert task_row["course_id"] == course_id
    assert task_row["parse_run_id"] == parse_run_id
    assert task_row["task_type"] == "parse_pipeline"
    assert task_row["status"] == "queued"
    assert task_row["parent_task_id"] is None
    assert task_row["target_type"] == "parse_run"
    assert task_row["target_id"] == parse_run_id
    assert task_row["payload_json"] == {
        "courseId": course_id,
        "parseRunId": parse_run_id,
        "resourceTypes": ["pdf"],
    }
    assert _value(repo.get_async_task(task_id), "taskId", "task_id", "id") == task_id
    assert any(
        _value(item, "taskId", "task_id", "id") == task_id
        for item in repo.list_async_tasks(course_id=course_id, parse_run_id=parse_run_id)
    )

    saved = repo.save_inquiry_answers(
        course_id,
        [
            {"key": "goal_type", "value": "exam_sprint"},
            {"key": "mastery_level", "value": "intermediate"},
            {"key": "time_budget_minutes", "value": 90},
            {"key": "handout_style", "value": "exam"},
            {"key": "explanation_granularity", "value": "detailed"},
        ],
    )
    assert _value(saved, "saved") is True

    learning_preferences = Base.metadata.tables.get("learning_preferences")
    assert learning_preferences is not None
    preference_row = session.execute(
        sa.select(learning_preferences).where(learning_preferences.c.course_id == course_id)
    ).mappings().one()
    assert preference_row["goal_type"] == "exam_sprint"
    assert preference_row["self_level"] == "intermediate"
    assert preference_row["time_budget_minutes"] == 90
    assert preference_row["preferred_style"] == "exam"
    assert preference_row["formula_detail_level"] == "high"
    assert preference_row["example_density"] == "high"
    assert preference_row["confirmed_at"] is not None

    session.close()
    engine.dispose()


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append({"taskId": task_id, "payload": payload})


def test_pipeline_service_sql_parse_start_enqueues_once_and_persists_complete_payload():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite service parse start",
        entry_type="manual_import",
        goal_text="验证 service 入队与 payload",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    for resource_type in ("pdf", "docx"):
        repo.create_resource(
            course_id,
            {
                "resourceType": resource_type,
                "objectKey": f"raw/1/{course_id}/service-{resource_type}",
                "originalName": f"service.{resource_type}",
                "mimeType": "application/octet-stream",
                "sizeBytes": 1024,
                "checksum": f"sha256:service-{resource_type}",
            },
        )

    dispatcher = _RecordingDispatcher()
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=dispatcher,
        idempotency=repo,
    )

    first = service.start_parse(course_id=course_id, idempotency_key="sqlite-service-parse")
    second = service.start_parse(course_id=course_id, idempotency_key="sqlite-service-parse")

    assert first == second
    assert dispatcher.calls == [
        {
            "taskId": first["taskId"],
            "payload": {
                "courseId": course_id,
                "parseRunId": first["entity"]["id"],
                "resourceTypes": ["docx", "pdf"],
            },
        }
    ]

    async_tasks = Base.metadata.tables.get("async_tasks")
    assert async_tasks is not None
    task_row = session.execute(
        sa.select(async_tasks).where(async_tasks.c.id == first["taskId"])
    ).mappings().one()
    assert task_row["payload_json"] == dispatcher.calls[0]["payload"]

    session.close()
    engine.dispose()
