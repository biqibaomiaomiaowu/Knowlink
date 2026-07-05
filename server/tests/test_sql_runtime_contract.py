from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import re
import textwrap
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.domain.services.courses import CourseService
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import build_request_hash
from server.domain.services.pipelines import PipelineService
from server.domain.services.quizzes import QuizService
from server.domain.services.reviews import ReviewService
from server.infra.db.base import Base
from server.infra.db.models import AsyncTask, IdempotencyRecord, Quiz, QuizAttempt, ReviewTaskRun
from server.schemas.requests import CreateCourseRequest, SubmitQuizRequest
from server.tasks.reviews import run_review_refresh


ROOT = Path(__file__).resolve().parents[2]


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, dict[str, Any]]] = []

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("quiz_generate", task_id, payload))


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
    "handout_versions": {
        "course_id",
        "source_parse_run_id",
        "title",
        "summary",
        "status",
        "outline_status",
        "total_blocks",
        "ready_blocks",
        "pending_blocks",
        "error_code",
        "error_message",
        "meta_json",
    },
    "handout_outlines": {
        "handout_version_id",
        "course_id",
        "source_parse_run_id",
        "status",
        "title",
        "summary",
        "item_count",
        "outline_json",
    },
    "handout_blocks": {
        "handout_version_id",
        "outline_key",
        "title",
        "summary",
        "status",
        "content_md",
        "start_sec",
        "end_sec",
        "sort_no",
        "source_segment_keys_json",
        "knowledge_points_json",
        "citations_json",
        "generation_metadata_json",
    },
    "handout_block_refs": {
        "handout_block_id",
        "resource_id",
        "segment_id",
        "ref_type",
        "quote_text",
        "page_no",
        "slide_no",
        "anchor_key",
        "start_sec",
        "end_sec",
        "bbox_json",
        "ref_label",
        "sort_no",
    },
    "qa_sessions": {
        "user_id",
        "course_id",
        "handout_version_id",
        "handout_block_id",
        "status",
        "context_snapshot_json",
        "message_count",
        "last_message_at",
    },
    "qa_messages": {
        "session_id",
        "role",
        "content_md",
        "content_text",
        "answer_type",
        "latency_ms",
        "token_usage_prompt",
        "token_usage_completion",
        "safety_flag",
    },
    "qa_message_refs": {
        "qa_message_id",
        "resource_id",
        "segment_id",
        "ref_type",
        "quote_text",
        "page_no",
        "slide_no",
        "anchor_key",
        "start_sec",
        "end_sec",
        "bbox_json",
        "ref_label",
        "sort_no",
        "rank",
    },
    "quizzes": {
        "course_id",
        "handout_version_id",
        "source_parse_run_id",
        "quiz_type",
        "status",
        "question_count",
        "payload_json",
        "error_code",
        "error_message",
    },
    "quiz_questions": {
        "quiz_id",
        "question_key",
        "question_type",
        "stem_md",
        "options_json",
        "correct_answer",
        "explanation_md",
        "difficulty_level",
        "knowledge_point_key",
        "knowledge_point_name",
        "source_block_key",
        "source_segment_keys_json",
        "sort_no",
    },
    "quiz_question_refs": {
        "quiz_question_id",
        "resource_id",
        "segment_id",
        "ref_type",
        "quote_text",
        "page_no",
        "slide_no",
        "anchor_key",
        "start_sec",
        "end_sec",
        "bbox_json",
        "ref_label",
        "sort_no",
    },
    "quiz_attempts": {
        "user_id",
        "course_id",
        "quiz_id",
        "review_task_run_id",
        "score",
        "total_score",
        "accuracy",
        "result_json",
    },
    "quiz_attempt_items": {
        "attempt_id",
        "quiz_question_id",
        "question_key",
        "selected_option",
        "correct_answer",
        "is_correct",
        "obtained_score",
        "explanation_md",
        "knowledge_point_key",
        "source_block_key",
        "sort_no",
    },
    "mastery_records": {
        "user_id",
        "course_id",
        "last_quiz_attempt_id",
        "knowledge_point_key",
        "knowledge_point",
        "mastery_score",
        "confidence_score",
        "correct_count",
        "wrong_count",
        "review_priority",
        "status",
        "source_question_keys_json",
        "source_block_key",
    },
    "review_task_runs": {
        "user_id",
        "course_id",
        "source_quiz_attempt_id",
        "status",
        "generated_count",
        "payload_json",
        "error_code",
        "error_message",
        "finished_at",
    },
    "review_tasks": {
        "review_task_run_id",
        "course_id",
        "task_key",
        "task_type",
        "priority_score",
        "reason_text",
        "recommended_minutes",
        "knowledge_point_key",
        "source_block_key",
        "source_question_keys_json",
        "source_segment_keys_json",
        "recommended_action_json",
        "recommended_segment_json",
        "practice_entry_json",
        "review_order",
        "intensity",
        "status",
        "completed_at",
    },
    "review_task_refs": {
        "review_task_id",
        "resource_id",
        "segment_id",
        "ref_type",
        "quote_text",
        "page_no",
        "slide_no",
        "anchor_key",
        "start_sec",
        "end_sec",
        "bbox_json",
        "ref_label",
        "sort_no",
    },
    "user_course_progress": {
        "user_id",
        "course_id",
        "handout_version_id",
        "last_handout_block_id",
        "last_video_resource_id",
        "last_position_sec",
        "last_doc_resource_id",
        "last_page_no",
        "last_slide_no",
        "last_anchor_key",
        "last_activity_at",
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
        "embedding_vector",
        "embedding_model",
        "embedding_dim",
        "embedding_status",
        "embedding_error",
        "search_text",
    },
}


def _import_db_models() -> None:
    models_pkg = importlib.import_module("server.infra.db.models")
    for module_info in pkgutil.iter_modules(models_pkg.__path__, f"{models_pkg.__name__}."):
        importlib.import_module(module_info.name)


def _migration_text() -> str:
    versions_dir = ROOT / "alembic/versions"
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(versions_dir.glob("*.py")))


def _imported_modules_from_source(source: str) -> set[str]:
    imported: set[str] = set()
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")
    return imported


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
        "get_resource",
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


def _assert_same_datetime(actual: Any, expected: datetime) -> None:
    assert isinstance(actual, datetime)
    comparable = actual if actual.tzinfo is not None else actual.replace(tzinfo=timezone.utc)
    assert comparable == expected


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
    assert _value(repo.get_resource(resource_id), "resourceId", "resource_id", "id") == resource_id
    other_user_repo = repository_cls(session, user_id=2)
    assert other_user_repo.get_resource(resource_id) is None
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


def test_sql_repository_create_course_persists_exam_at_and_returns_it():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    exam_at = datetime(2026, 6, 20, 1, 30, tzinfo=timezone.utc)

    course = repo.create_course(
        title="SQLite examAt 课程",
        entry_type="manual_import",
        goal_text="验证考试时间持久化",
        preferred_style="exam",
        exam_at=exam_at,
    )
    course_id = _value(course, "courseId", "course_id", "id")

    _assert_same_datetime(_value(course, "examAt", "exam_at"), exam_at)
    courses = Base.metadata.tables.get("courses")
    assert courses is not None
    row_exam_at = session.execute(
        sa.select(courses.c.exam_at).where(courses.c.id == course_id)
    ).scalar_one()
    _assert_same_datetime(row_exam_at, exam_at)

    session.close()
    engine.dispose()


def test_sql_repository_current_course_uses_recent_then_explicit_switch():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    first = repo.create_course(
        title="SQLite 当前课程 A",
        entry_type="manual_import",
        goal_text="验证当前课程默认语义",
        preferred_style="balanced",
    )
    second = repo.create_course(
        title="SQLite 当前课程 B",
        entry_type="manual_import",
        goal_text="验证当前课程切换语义",
        preferred_style="balanced",
    )
    first_id = _value(first, "courseId", "course_id", "id")
    second_id = _value(second, "courseId", "course_id", "id")

    assert _value(repo.get_current_course(), "courseId", "course_id", "id") == second_id
    switched = repo.set_current_course(first_id)

    assert switched is not None
    assert _value(switched, "courseId", "course_id", "id") == first_id
    assert _value(repo.get_current_course(), "courseId", "course_id", "id") == first_id
    repo.create_parse_run(second_id)
    assert _value(repo.get_current_course(), "courseId", "course_id", "id") == first_id
    assert repo.set_current_course(999999) is None

    session.close()
    engine.dispose()


def test_sql_repository_soft_deletes_course_with_dependents():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite deletable library course",
        entry_type="manual_import",
        goal_text="verify course library soft delete",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    repo.create_lesson(course_id=course_id, title="Dependent lesson")
    repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/dependent.pdf",
            "originalName": "dependent.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:dependent",
        },
    )

    impact = repo.get_course_delete_impact(course_id)
    deleted = repo.delete_course(course_id)

    assert impact is not None
    assert impact["canDelete"] is False
    assert impact["blockers"]["lessons"] == 1
    assert impact["blockers"]["resources"] == 1
    assert deleted is not None
    assert deleted["deleted"] is True
    assert deleted["impact"]["blockers"]["lessons"] == 1
    assert repo.get_course(course_id) is None
    assert course_id not in {
        _value(item, "courseId", "course_id", "id")
        for item in repo.list_courses({"archived": "include"})
    }

    session.close()
    engine.dispose()


def test_sql_repository_current_library_lesson_skips_overread_handout():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite overread handout course",
        entry_type="manual_import",
        goal_text="verify current lesson completion semantics",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    first = repo.create_lesson(course_id=course_id, title="Lesson 1")
    second = repo.create_lesson(course_id=course_id, title="Lesson 2")
    repo.upsert_user_lesson_progress(
        course_id=course_id,
        lesson_id=first["lessonId"],
        payload={"handoutReadPercent": 120},
    )

    current_lesson = repo._current_library_lesson(course_id=course_id, lessons=repo.list_lessons(course_id))

    assert current_lesson is not None
    assert current_lesson["lessonId"] == second["lessonId"]

    session.close()
    engine.dispose()


def test_sql_repository_current_library_lesson_skips_lesson_level_completed_quiz():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite lesson quiz completed course",
        entry_type="manual_import",
        goal_text="verify lesson-level quiz completion semantics",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    first = repo.create_lesson(course_id=course_id, title="Lesson 1")
    second = repo.create_lesson(course_id=course_id, title="Lesson 2")
    repo.update_lesson(
        course_id=course_id,
        lesson_id=first["lessonId"],
        changes={"quizStatus": "completed"},
    )

    current_lesson = repo._current_library_lesson(course_id=course_id, lessons=repo.list_lessons(course_id))

    assert current_lesson is not None
    assert current_lesson["lessonId"] == second["lessonId"]

    session.close()
    engine.dispose()


def test_sql_repository_normalizes_non_utc_exam_at_to_utc_for_sqlite_round_trip():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    exam_at = datetime(2026, 6, 20, 9, 30, tzinfo=timezone(timedelta(hours=8)))
    expected_utc = datetime(2026, 6, 20, 1, 30, tzinfo=timezone.utc)

    course = repo.create_course(
        title="SQLite examAt 非 UTC 课程",
        entry_type="manual_import",
        goal_text="验证考试时间时区归一化",
        preferred_style="exam",
        exam_at=exam_at,
    )
    course_id = _value(course, "courseId", "course_id", "id")

    returned_exam_at = _value(course, "examAt", "exam_at")
    assert returned_exam_at == expected_utc
    assert returned_exam_at.tzinfo is timezone.utc

    fetched_exam_at = _value(repo.get_course(course_id), "examAt", "exam_at")
    assert fetched_exam_at == expected_utc
    assert fetched_exam_at.tzinfo is timezone.utc

    courses = Base.metadata.tables.get("courses")
    assert courses is not None
    row_exam_at = session.execute(
        sa.select(courses.c.exam_at).where(courses.c.id == course_id)
    ).scalar_one()
    assert isinstance(row_exam_at, datetime)
    assert row_exam_at.replace(tzinfo=timezone.utc) == expected_utc

    session.close()
    engine.dispose()


def test_sql_handout_block_generation_metadata_persists_to_read_models():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite handout metadata 课程",
        entry_type="manual_import",
        goal_text="验证讲义块生成元数据持久化",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/metadata.pdf",
            "originalName": "metadata.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:metadata",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "title": "极限定义",
                "textContent": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "plainText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
                "orderNo": 1,
                "tokenCount": 20,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    generation_metadata = {"source": "fallback", "reason": "model_unavailable"}
    handout, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "SQLite metadata 讲义",
            "summary": "用于讲义块 metadata 验收。",
            "items": [
                {
                    "outlineKey": "section-1",
                    "title": "极限定义",
                    "summary": "理解极限定义。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-1",
                            "title": "极限定义",
                            "summary": "理解极限定义。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segment_key],
                            "topicTags": ["极限"],
                        }
                    ],
                }
            ],
        },
    )
    saved = repo.save_handout_block_result(
        blocks[0]["blockId"],
        {
            "title": "极限定义",
            "summary": "理解极限定义。",
            "contentMd": "极限定义需要同时关注自变量趋近和函数值趋近。",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit-metadata",
                    "displayName": "极限定义",
                    "description": "同时关注自变量趋近和函数值趋近。",
                    "difficultyLevel": "medium",
                    "importanceScore": 90,
                }
            ],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentId": segments[0]["segmentId"],
                    "segmentKey": segment_key,
                    "pageNo": 2,
                    "refLabel": "PDF 第 2 页",
                }
            ],
            "generationMetadata": generation_metadata,
        },
    )

    assert saved["generationMetadata"] == generation_metadata
    for read_model in (
        repo.get_handout(handout["handoutVersionId"])["blocks"][0],
        repo.get_latest_handout(course_id)["blocks"][0],
        repo.get_handout_block_status(blocks[0]["blockId"]),
    ):
        assert read_model["generationMetadata"] == generation_metadata
    public_citation = repo.get_latest_handout(course_id)["blocks"][0]["citations"][0]
    assert "segmentId" not in public_citation
    assert "segmentKey" not in public_citation
    handout_blocks = Base.metadata.tables["handout_blocks"]
    internal_citations = session.execute(
        sa.select(handout_blocks.c.citations_json).where(handout_blocks.c.id == blocks[0]["blockId"])
    ).scalar_one()
    assert internal_citations[0]["segmentId"] == segments[0]["segmentId"]
    assert internal_citations[0]["segmentKey"] == segment_key
    qa_context = repo.get_qa_context(course_id, blocks[0]["blockId"])
    assert qa_context["currentBlock"]["citations"][0]["segmentId"] == segments[0]["segmentId"]
    assert qa_context["currentBlock"]["citations"][0]["segmentKey"] == segment_key

    session.close()
    engine.dispose()


def test_sql_legacy_ready_handout_block_without_metadata_returns_fallback_marker():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite legacy metadata 课程",
        entry_type="manual_import",
        goal_text="验证旧 ready 讲义块 metadata 兼容",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/legacy.pdf",
            "originalName": "legacy.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:legacy",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "title": "旧讲义块",
                "textContent": "旧数据在 metadata 字段上线前已经处于 ready。",
                "plainText": "旧数据在 metadata 字段上线前已经处于 ready。",
                "pageNo": 1,
                "orderNo": 1,
                "tokenCount": 18,
            }
        ],
    )
    handout, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "Legacy metadata 讲义",
            "summary": "用于旧数据 metadata 兼容。",
            "items": [
                {
                    "outlineKey": "section-1",
                    "title": "旧讲义块",
                    "summary": "旧数据兼容。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-legacy",
                            "title": "旧讲义块",
                            "summary": "旧数据兼容。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segments[0]["segmentKey"]],
                            "topicTags": ["兼容"],
                        }
                    ],
                }
            ],
        },
    )
    expected = {"source": "fallback", "reason": "legacy_unknown"}
    handout_versions = Base.metadata.tables["handout_versions"]
    handout_blocks = Base.metadata.tables["handout_blocks"]
    session.execute(
        sa.update(handout_versions)
        .where(handout_versions.c.id == handout["handoutVersionId"])
        .values(status="ready", ready_blocks=1, pending_blocks=0)
    )
    session.execute(
        sa.update(handout_blocks)
        .where(handout_blocks.c.id == blocks[0]["blockId"])
        .values(
            status="ready",
            content_md="旧数据在 metadata 字段上线前已经处于 ready。",
            knowledge_points_json=[],
            citations_json=[],
            generation_metadata_json=None,
        )
    )
    session.commit()

    for read_model in (
        repo.get_handout(handout["handoutVersionId"])["blocks"][0],
        repo.get_latest_handout(course_id)["blocks"][0],
        repo.get_handout_block_status(blocks[0]["blockId"]),
    ):
        assert read_model["generationMetadata"] == expected

    session.close()
    engine.dispose()


def test_import_collection_ignores_comments_and_string_literals():
    imported = _imported_modules_from_source(
        '''
        # import server.ai.quiz_strategy
        text = "server.ai.review_strategy"
        import server.infra.repositories.sqlalchemy as sql_repo
        from server.ai import quiz_strategy
        from server.ai.review_strategy import build_mastery_record_updates
        '''
    )

    assert "server.infra.repositories.sqlalchemy" in imported
    assert "server.ai.quiz_strategy" in imported
    assert "server.ai.review_strategy" in imported


def test_sql_repository_does_not_import_quiz_or_review_strategy_layers():
    imported = _imported_modules_from_source(
        (ROOT / "server" / "infra" / "repositories" / "sqlalchemy.py").read_text(encoding="utf-8")
    )
    forbidden = {"server.ai.quiz_strategy", "server.ai.review_strategy"}

    assert not {
        module
        for module in imported
        if any(module == name or module.startswith(f"{name}.") for name in forbidden)
    }


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append({"taskId": task_id, "payload": payload})

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
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


def test_pipeline_service_sql_replays_legacy_route_scoped_parse_start_record():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite legacy route-scoped parse",
        entry_type="manual_import",
        goal_text="验证旧 route-scoped 幂等记录回放",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/legacy-route-scoped.pdf",
            "originalName": "legacy-route-scoped.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:legacy-route-scoped",
        },
    )
    _, legacy_trigger = repo.create_parse_run(course_id)
    legacy = repo.run_idempotent(
        f"pipelines.parse_start:{course_id}",
        "sqlite-legacy-route-parse",
        lambda: legacy_trigger,
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

    replayed = service.start_parse(course_id=course_id, idempotency_key="sqlite-legacy-route-parse")

    assert replayed == legacy
    assert dispatcher.calls == []

    session.close()
    engine.dispose()


def test_sql_scoped_idempotency_ignores_expired_records():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    in_progress_scope = "resources.upload_complete:11"
    in_progress_key = "sqlite-expired-in-progress"
    in_progress_hash = build_request_hash({"objectKey": "old.pdf"})
    replacement_hash = build_request_hash({"objectKey": "new.pdf"})
    session.add(
        IdempotencyRecord(
            action="legacy-expired-in-progress",
            scope=in_progress_scope,
            key=in_progress_key,
            request_hash=in_progress_hash,
            status="in_progress",
            response_json=None,
            expires_at=expired_at,
        )
    )
    session.commit()

    replacement = repo.run_scoped_idempotent(
        scope=in_progress_scope,
        key=in_progress_key,
        request_hash=replacement_hash,
        factory=lambda: {"resourceId": 701, "objectKey": "new.pdf"},
    )

    succeeded_scope = "pipelines.parse_start:11"
    succeeded_key = "sqlite-expired-succeeded"
    succeeded_hash = build_request_hash({"courseId": 11})
    new_succeeded_hash = build_request_hash({"courseId": 12})
    session.add(
        IdempotencyRecord(
            action="legacy-expired-succeeded",
            scope=succeeded_scope,
            key=succeeded_key,
            request_hash=succeeded_hash,
            status="succeeded",
            response_json={"taskId": 1},
            result_json={"taskId": 1},
            expires_at=expired_at,
        )
    )
    session.commit()

    new_value = repo.run_scoped_idempotent(
        scope=succeeded_scope,
        key=succeeded_key,
        request_hash=new_succeeded_hash,
        factory=lambda: {"taskId": 2},
    )

    rows = session.scalars(
        sa.select(IdempotencyRecord).where(
            IdempotencyRecord.scope.in_([in_progress_scope, succeeded_scope])
        )
    ).all()
    records = {(row.scope, row.key): row for row in rows}
    assert replacement == {"resourceId": 701, "objectKey": "new.pdf"}
    assert records[(in_progress_scope, in_progress_key)].request_hash == replacement_hash
    assert records[(in_progress_scope, in_progress_key)].status == "succeeded"
    assert new_value == {"taskId": 2}
    assert records[(succeeded_scope, succeeded_key)].request_hash == new_succeeded_hash

    session.close()
    engine.dispose()


def test_sql_scoped_idempotency_keeps_non_expired_mismatch_protection():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    scope = "resources.upload_complete:11"
    key = "sqlite-active-mismatch"
    session.add(
        IdempotencyRecord(
            action="legacy-active-mismatch",
            scope=scope,
            key=key,
            request_hash=build_request_hash({"objectKey": "old.pdf"}),
            status="succeeded",
            response_json={"resourceId": 1},
            result_json={"resourceId": 1},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    session.commit()

    with pytest.raises(ServiceError) as exc_info:
        repo.run_scoped_idempotent(
            scope=scope,
            key=key,
            request_hash=build_request_hash({"objectKey": "new.pdf"}),
            factory=lambda: {"resourceId": 2},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "idempotency.body_mismatch"

    session.close()
    engine.dispose()


def test_course_service_sql_scoped_idempotency_rejects_body_mismatch_and_replays_legacy_record():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    service = CourseService(courses=repo, idempotency=repo)

    legacy = repo.run_idempotent(
        "courses.create",
        "sqlite-legacy-course",
        lambda: {
            "course": repo.create_course(
                title="SQLite legacy course",
                entry_type="manual_import",
                goal_text="legacy",
                preferred_style="balanced",
            )
        },
    )
    replayed = service.create_course(
        payload=CreateCourseRequest(
            title="SQLite legacy course with new body",
            entry_type="manual_import",
            goal_text="legacy changed",
            preferred_style="exam",
        ),
        idempotency_key="sqlite-legacy-course",
    )
    first = service.create_course(
        payload=CreateCourseRequest(
            title="SQLite fingerprint course A",
            entry_type="manual_import",
            goal_text="fingerprint",
            preferred_style="balanced",
        ),
        idempotency_key="sqlite-fingerprint-course",
    )

    with pytest.raises(ServiceError) as exc_info:
        service.create_course(
            payload=CreateCourseRequest(
                title="SQLite fingerprint course B",
                entry_type="manual_import",
                goal_text="fingerprint",
                preferred_style="balanced",
            ),
            idempotency_key="sqlite-fingerprint-course",
        )

    assert replayed["course"]["courseId"] == legacy["course"]["courseId"]
    assert replayed["course"]["title"] == "SQLite legacy course"
    assert first["course"]["title"] == "SQLite fingerprint course A"
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "idempotency.body_mismatch"

    session.close()
    engine.dispose()


def test_quiz_service_sql_submit_persists_attempt_and_review_refresh_task():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite quiz submit",
        entry_type="manual_import",
        goal_text="验证 submit_quiz service 负责判分",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/quiz-submit.pdf",
            "originalName": "quiz-submit.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:quiz-submit",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "title": "极限定义",
                "textContent": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "plainText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
                "orderNo": 1,
                "tokenCount": 20,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    _, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "SQLite quiz submit 讲义",
            "summary": "用于测验提交验收。",
            "items": [
                {
                    "outlineKey": "section-1",
                    "title": "极限定义",
                    "summary": "理解极限定义。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-1",
                            "title": "极限定义",
                            "summary": "理解极限定义。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segment_key],
                            "topicTags": ["极限"],
                        }
                    ],
                }
            ],
        },
    )
    repo.save_handout_block_result(
        blocks[0]["blockId"],
        {
            "title": "极限定义",
            "summary": "理解极限定义。",
            "contentMd": "极限定义需要同时关注自变量趋近和函数值趋近。",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit-submit",
                    "displayName": "极限定义",
                    "description": "同时关注自变量趋近和函数值趋近。",
                    "difficultyLevel": "medium",
                    "importanceScore": 90,
                }
            ],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentKey": segment_key,
                    "pageNo": 2,
                    "refLabel": "PDF 第 2 页",
                }
            ],
        },
    )
    quiz, _ = repo.create_quiz(course_id)
    repo.save_quiz_generation_result(
        quiz["quizId"],
        {
            "quizType": "chapter_review",
            "questions": [
                {
                    "questionKey": "q1-submit",
                    "questionType": "single_choice",
                    "stemMd": "极限定义关注什么？",
                    "options": ["A. 自变量趋近与函数值趋近", "B. 只关注面积", "C. 只关注常数", "D. 只关注符号"],
                    "correctAnswer": "A",
                    "explanationMd": "依据当前讲义块。",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-limit-submit",
                    "knowledgePointName": "极限定义",
                    "sourceBlockKey": str(blocks[0]["blockId"]),
                    "sourceSegmentKeys": [segment_key],
                }
            ],
        },
        [],
    )
    first_question = repo.get_quiz(quiz["quizId"])["questions"][0]
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )

    result = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest(
            answers=[
                {
                    "questionId": first_question["questionId"],
                    "selectedOption": "A",
                }
            ],
        ),
    )

    assert result["score"] == 1
    assert result["totalScore"] == 1
    assert result["items"] == [
        {
            "questionId": first_question["questionId"],
            "questionKey": "q1-submit",
            "selectedOption": "A",
            "isCorrect": True,
            "obtainedScore": 1,
            "explanationMd": "依据当前讲义块。",
            "knowledgePointKey": "kp-limit-submit",
            "sourceBlockKey": str(blocks[0]["blockId"]),
        }
    ]
    assert "correctAnswer" not in result["items"][0]
    attempts = Base.metadata.tables.get("quiz_attempts")
    async_tasks = Base.metadata.tables.get("async_tasks")
    assert attempts is not None
    assert async_tasks is not None
    attempt_row = session.execute(
        sa.select(attempts).where(attempts.c.id == result["attemptId"])
    ).mappings().one()
    assert attempt_row["score"] == 1
    refresh_task = session.execute(
        sa.select(async_tasks).where(
            async_tasks.c.task_type == "review_refresh",
            async_tasks.c.target_id == result["reviewTaskRunId"],
        )
    ).mappings().one()
    assert refresh_task["payload_json"] == {
        "courseId": course_id,
        "reviewTaskRunId": result["reviewTaskRunId"],
    }
    assert dispatcher.calls == [
        {
            "taskId": refresh_task["id"],
            "payload": refresh_task["payload_json"],
        }
    ]

    session.close()
    engine.dispose()


def test_sql_review_regenerate_uses_latest_attempt_with_active_course_context():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite review regenerate active attempt",
        entry_type="manual_import",
        goal_text="verify manual review regenerate input selection",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    handout, _, _ = repo.create_handout(
        course_id,
        outline={
            "title": "Active handout",
            "summary": "Used by review regenerate.",
            "items": [
                {
                    "outlineKey": "section-active",
                    "title": "Active section",
                    "summary": "Current course context.",
                    "sortNo": 1,
                    "children": [],
                }
            ],
        },
    )
    handout_version_id = handout["handoutVersionId"]

    valid_quiz = Quiz(
        course_id=course_id,
        scope_type="course",
        quiz_mode="objective",
        handout_version_id=handout_version_id,
        source_parse_run_id=parse_run_id,
        quiz_type="chapter_review",
        status="ready",
        question_count=0,
        payload_json={},
    )
    invalid_latest_quiz = Quiz(
        course_id=course_id,
        scope_type="course",
        quiz_mode="objective",
        handout_version_id=None,
        source_parse_run_id=None,
        quiz_type="scoped_objective",
        status="ready",
        question_count=0,
        payload_json={},
    )
    session.add_all([valid_quiz, invalid_latest_quiz])
    session.flush()
    valid_attempt = QuizAttempt(
        user_id=repo.user_id,
        course_id=course_id,
        quiz_id=valid_quiz.id,
        review_task_run_id=None,
        score=1,
        total_score=1,
        accuracy=1.0,
        result_json={"items": []},
    )
    invalid_latest_attempt = QuizAttempt(
        user_id=repo.user_id,
        course_id=course_id,
        quiz_id=invalid_latest_quiz.id,
        review_task_run_id=None,
        score=1,
        total_score=1,
        accuracy=1.0,
        result_json={"items": []},
    )
    session.add_all([valid_attempt, invalid_latest_attempt])
    session.flush()
    assert invalid_latest_attempt.id > valid_attempt.id

    result = repo.create_review_run(course_id)

    run = session.get(ReviewTaskRun, result["reviewTaskRunId"])
    assert run is not None
    assert run.source_quiz_attempt_id == valid_attempt.id
    assert run.payload_json == {"quizAttemptId": valid_attempt.id}
    task = session.get(AsyncTask, result["_reviewRefreshTask"]["taskId"])
    assert task is not None
    assert task.parse_run_id == parse_run_id
    assert task.target_type == "review_task_run"
    assert task.target_id == run.id
    assert task.payload_json == {"courseId": course_id, "reviewTaskRunId": run.id}

    session.close()
    engine.dispose()


def test_sql_review_regenerate_accepts_course_attempt_backed_by_lesson_handout():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite review regenerate lesson handout fallback",
        entry_type="manual_import",
        goal_text="verify course quiz review from lesson handout",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    lesson = repo.create_lesson(course_id=course_id, title="Lesson handout source")
    lesson_id = lesson["lessonId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "scopeType": "lesson",
            "lessonId": lesson_id,
            "usageRole": "lesson_material",
            "objectKey": f"raw/1/{course_id}/lesson-review.pdf",
            "originalName": "lesson-review.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:lesson-review",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "title": "Lesson review source",
                "textContent": "Lesson handout evidence supports review generation.",
                "plainText": "Lesson handout evidence supports review generation.",
                "pageNo": 1,
                "orderNo": 1,
                "tokenCount": 12,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    _handout, _trigger, blocks = repo.create_handout(
        course_id,
        scope_type="lesson",
        lesson_id=lesson_id,
        artifact_kind="lesson_handout",
        outline={
            "title": "Lesson review handout",
            "summary": "Lesson review handout.",
            "items": [
                {
                    "outlineKey": "lesson-review-section",
                    "title": "Lesson review section",
                    "summary": "Lesson review section.",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "lesson-review-block",
                            "title": "Lesson review block",
                            "summary": "Lesson review block.",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segment_key],
                        }
                    ],
                }
            ],
        },
    )
    block_id = blocks[0]["blockId"]
    repo.save_handout_block_result(
        block_id,
        {
            "title": "Lesson review block",
            "summary": "Lesson review block.",
            "contentMd": "Lesson handout evidence supports review generation.",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-lesson-review",
                    "displayName": "Lesson review",
                    "description": "Lesson handout review evidence.",
                    "difficultyLevel": "medium",
                    "importanceScore": 90,
                }
            ],
            "citations": [{"resourceId": resource["resourceId"], "segmentKey": segment_key, "pageNo": 1}],
        },
    )
    quiz, _ = repo.create_quiz(course_id)
    assert quiz["scopeType"] == "course"
    assert session.get(Quiz, quiz["quizId"]).handout_version_id is None
    repo.save_quiz_generation_result(
        quiz["quizId"],
        {
            "quizType": "chapter_review",
            "questions": [
                {
                    "questionKey": "q-lesson-review",
                    "questionType": "single_choice",
                    "stemMd": "What supports review generation?",
                    "options": ["A. Lesson handout", "B. Nothing"],
                    "correctAnswer": "A",
                    "explanationMd": "The lesson handout provides the evidence.",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-lesson-review",
                    "knowledgePointName": "Lesson review",
                    "sourceBlockKey": str(block_id),
                    "sourceSegmentKeys": [segment_key],
                }
            ],
        },
        refs=[
            {
                "questionKey": "q-lesson-review",
                "resourceId": resource["resourceId"],
                "segmentId": segments[0]["segmentId"],
                "segmentKey": segment_key,
                "refType": "citation",
                "pageNo": 1,
                "sortNo": 1,
            }
        ],
    )
    result = repo.save_quiz_attempt_result(
        quiz["quizId"],
        quiz_attempt_result={
            "score": 0,
            "totalScore": 1,
            "accuracy": 0.0,
            "items": [
                {
                    "questionKey": "q-lesson-review",
                    "selectedOption": "B",
                    "correctAnswer": "A",
                    "isCorrect": False,
                    "obtainedScore": 0,
                    "explanationMd": "The lesson handout provides the evidence.",
                    "knowledgePointKey": "kp-lesson-review",
                    "sourceBlockKey": str(block_id),
                }
            ],
            "masteryDelta": [
                {
                    "knowledgePointKey": "kp-lesson-review",
                    "knowledgePoint": "Lesson review",
                    "delta": -0.2,
                    "correctCount": 0,
                    "wrongCount": 1,
                    "sourceQuestionKeys": ["q-lesson-review"],
                }
            ],
        },
        mastery_updates=[
            {
                "knowledgePointKey": "kp-lesson-review",
                "knowledgePoint": "Lesson review",
                "masteryScoreDelta": -0.2,
                "confidenceDelta": -0.04,
                "nextMasteryScore": 0.3,
                "nextConfidenceScore": 0.26,
                "correctCountDelta": 0,
                "wrongCountDelta": 1,
                "reviewPriority": 90,
                "sourceQuestionKeys": ["q-lesson-review"],
                "status": "needs_review",
            }
        ],
    )
    assert result["reviewTaskRunId"] is not None

    dispatcher = _RecordingDispatcher()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )

    regenerated = service.regenerate_review_tasks(course_id=course_id, idempotency_key=None)

    regenerated_run = session.get(ReviewTaskRun, regenerated["entity"]["id"])
    task = session.get(AsyncTask, regenerated["taskId"])
    assert regenerated["status"] == "queued"
    assert regenerated_run is not None
    assert regenerated_run.source_quiz_attempt_id == result["attemptId"]
    assert regenerated_run.scope_type == "course"
    assert task is not None
    assert task.parse_run_id == parse_run_id
    assert dispatcher.calls == [{"taskId": task.id, "payload": {"courseId": course_id, "reviewTaskRunId": regenerated_run.id}}]

    worker_result = run_review_refresh(
        {"taskId": task.id, "courseId": course_id, "reviewTaskRunId": regenerated_run.id},
        session_factory=lambda: session,
    )
    task_views = service.list_review_tasks(course_id=course_id)["items"]

    assert worker_result["status"] == "ready"
    assert len(task_views) == 1
    assert task_views[0]["linkedHandoutBlockId"] == block_id
    assert task_views[0]["jumpRoute"] == f"/courses/{course_id}/review"

    session.close()
    engine.dispose()


def test_review_service_sql_regenerate_returns_not_ready_without_active_course_attempt():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite review regenerate no active attempt",
        entry_type="manual_import",
        goal_text="verify manual review regenerate rejects stale attempt",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    repo.create_handout(
        course_id,
        outline={
            "title": "Active handout",
            "summary": "No matching quiz attempt exists.",
            "items": [
                {
                    "outlineKey": "section-active",
                    "title": "Active section",
                    "summary": "Current course context.",
                    "sortNo": 1,
                    "children": [],
                }
            ],
        },
    )
    invalid_quiz = Quiz(
        course_id=course_id,
        scope_type="course",
        quiz_mode="objective",
        handout_version_id=None,
        source_parse_run_id=None,
        quiz_type="scoped_objective",
        status="ready",
        question_count=0,
        payload_json={},
    )
    session.add(invalid_quiz)
    session.flush()
    session.add(
        QuizAttempt(
            user_id=repo.user_id,
            course_id=course_id,
            quiz_id=invalid_quiz.id,
            review_task_run_id=None,
            score=1,
            total_score=1,
            accuracy=1.0,
            result_json={"items": []},
        )
    )
    session.commit()

    dispatcher = _RecordingDispatcher()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )

    result = service.regenerate_review_tasks(course_id=course_id, idempotency_key=None)

    assert result == {
        "taskId": 0,
        "status": "not_ready",
        "nextAction": "complete_course_quiz",
        "entity": {"type": "course", "id": course_id},
    }
    assert dispatcher.calls == []
    assert session.query(ReviewTaskRun).count() == 0
    assert (
        session.query(AsyncTask)
        .filter(AsyncTask.course_id == course_id, AsyncTask.task_type == "review_refresh")
        .count()
        == 0
    )

    session.close()
    engine.dispose()


def test_sql_quiz_history_lists_latest_attempt():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite quiz history",
        entry_type="manual_import",
        goal_text="verify quiz history",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    other_course = repo.create_course(
        title="Other quiz history",
        entry_type="manual_import",
        goal_text="verify isolation",
        preferred_style="balanced",
    )
    other_course_id = _value(other_course, "courseId", "course_id", "id")
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/quiz-history.pdf",
            "originalName": "quiz-history.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:quiz-history",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "title": "Quiz history evidence",
                "textContent": "Quiz history evidence.",
                "plainText": "Quiz history evidence.",
                "pageNo": 1,
                "orderNo": 1,
                "tokenCount": 20,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    _, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "Quiz history handout",
            "summary": "History handout.",
            "items": [
                {
                    "outlineKey": "section-history",
                    "title": "History",
                    "summary": "History.",
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-history",
                            "title": "History block",
                            "summary": "History block.",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segment_key],
                        }
                    ],
                }
            ],
        },
    )
    repo.save_handout_block_result(
        blocks[0]["blockId"],
        {
            "title": "Quiz history block",
            "summary": "History block.",
            "contentMd": "Quiz history evidence.",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-quiz-history",
                    "displayName": "Quiz history",
                    "description": "History evidence.",
                    "difficultyLevel": "medium",
                    "importanceScore": 90,
                }
            ],
            "citations": [{"resourceId": resource["resourceId"], "segmentKey": segment_key}],
        },
    )
    quiz, _ = repo.create_quiz(course_id)
    repo.save_quiz_generation_result(
        quiz["quizId"],
        {
            "quizType": "chapter_review",
            "questions": [
                {
                    "questionKey": "q1-history",
                    "questionType": "single_choice",
                    "stemMd": "What verifies quiz history?",
                    "options": ["A. evidence", "B. nothing"],
                    "correctAnswer": "A",
                    "explanationMd": "Use history evidence.",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-quiz-history",
                    "knowledgePointName": "Quiz history",
                    "sourceBlockKey": str(blocks[0]["blockId"]),
                    "sourceSegmentKeys": [segment_key],
                }
            ],
        },
        [],
    )
    other_quiz = repo.create_scoped_quiz(
        course_id=other_course_id,
        scope_type="course",
        quiz_payload={"questions": []},
    )
    first_question = repo.get_quiz(quiz["quizId"])["questions"][0]
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=_RecordingDispatcher(),
        async_tasks=repo,
    )

    first_attempt = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest(
            answers=[{"questionId": first_question["questionId"], "selectedOption": "B"}],
        ),
    )
    latest_attempt = service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest(
            answers=[{"questionId": first_question["questionId"], "selectedOption": "A"}],
        ),
    )

    history = repo.list_course_quizzes(course_id)

    assert [item["quizId"] for item in history] == [quiz["quizId"]]
    assert other_quiz["quizId"] not in [item["quizId"] for item in history]
    item = history[0]
    assert item["courseId"] == course_id
    assert item["scopeType"] == "course"
    assert item["lessonId"] is None
    assert item["status"] == "ready"
    assert item["quizMode"] == "objective"
    assert item["questionCount"] == 1
    assert item["createdAt"] is not None
    assert item["updatedAt"] is not None
    assert item["latestAttempt"]["attemptId"] == latest_attempt["attemptId"]
    assert item["latestAttempt"]["score"] == latest_attempt["score"]
    assert item["latestAttempt"]["totalScore"] == latest_attempt["totalScore"]
    assert item["latestAttempt"]["accuracy"] == latest_attempt["accuracy"]
    assert item["latestAttempt"]["attemptId"] != first_attempt["attemptId"]

    session.close()
    engine.dispose()


def test_review_service_sql_reads_persisted_task_evidence_fields():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)

    course = repo.create_course(
        title="SQLite review service",
        entry_type="manual_import",
        goal_text="verify review service evidence fields",
        preferred_style="balanced",
    )
    course_id = _value(course, "courseId", "course_id", "id")
    lesson = repo.create_lesson(course_id=course_id, title="Limit review")
    lesson_id = lesson["lessonId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/review-service.pdf",
            "originalName": "review-service.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:review-service",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = _value(parse_run, "parseRunId", "parse_run_id", "id")
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "title": "Limit definition",
                "textContent": "Limit definition evidence.",
                "plainText": "Limit definition evidence.",
                "pageNo": 2,
                "orderNo": 1,
                "tokenCount": 20,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    _, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "SQLite review handout",
            "summary": "Review service handout.",
            "items": [
                {
                    "outlineKey": "section-review",
                    "title": "Limit",
                    "summary": "Limit definition.",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-review",
                            "title": "Limit definition",
                            "summary": "Review this block.",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segment_key],
                            "topicTags": ["limit"],
                        }
                    ],
                }
            ],
        },
    )
    repo.save_handout_block_result(
        blocks[0]["blockId"],
        {
            "title": "Limit definition",
            "summary": "Review this block.",
            "contentMd": "Limit definition evidence.",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit-review-service",
                    "displayName": "Limit definition",
                    "description": "A traceable review knowledge point.",
                    "difficultyLevel": "medium",
                    "importanceScore": 90,
                }
            ],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentKey": segment_key,
                    "pageNo": 2,
                    "refLabel": "PDF p2",
                }
            ],
        },
    )
    quiz, _ = repo.create_quiz(course_id)
    repo.save_quiz_generation_result(
        quiz["quizId"],
        {
            "quizType": "chapter_review",
            "questions": [
                {
                    "questionKey": "q1-review-service",
                    "questionType": "single_choice",
                    "stemMd": "What should the limit review revisit?",
                    "options": ["A. block", "B. unrelated", "C. none", "D. unknown"],
                    "correctAnswer": "A",
                    "explanationMd": "Use the current handout block.",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-limit-review-service",
                    "knowledgePointName": "Limit definition",
                    "sourceBlockKey": str(blocks[0]["blockId"]),
                    "sourceSegmentKeys": [segment_key],
                }
            ],
        },
        [],
    )
    first_question = repo.get_quiz(quiz["quizId"])["questions"][0]
    quiz_service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=_RecordingDispatcher(),
        async_tasks=repo,
    )
    submit_result = quiz_service.submit_quiz(
        quiz_id=quiz["quizId"],
        payload=SubmitQuizRequest(
            answers=[
                {
                    "questionId": first_question["questionId"],
                    "selectedOption": "A",
                }
            ],
        ),
    )
    evidence_chain = [{"type": "quiz_attempt", "questionKey": "q1-review-service"}]
    repo.save_review_task_run_result(
        submit_result["reviewTaskRunId"],
        {
            "tasks": [
                {
                    "taskKey": "review-service",
                    "taskType": "revisit_block",
                    "scopeType": "lesson",
                    "lessonId": lesson_id,
                    "priorityScore": 93,
                    "reasonText": "Review the traceable weak point.",
                    "recommendedMinutes": 12,
                    "knowledgePointKey": "kp-limit-review-service",
                    "sourceQuestionKeys": ["q1-review-service"],
                    "sourceBlockKey": str(blocks[0]["blockId"]),
                    "sourceSegmentKeys": [segment_key],
                    "reviewOrder": 1,
                    "recommendedAction": {
                        "type": "revisit_block",
                        "targetBlockKey": str(blocks[0]["blockId"]),
                    },
                    "evidenceChain": evidence_chain,
                }
            ]
        },
        [],
    )
    review_service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        lessons=repo,
    )

    task = review_service.list_review_tasks(course_id=course_id)["items"][0]

    assert task["scopeType"] == "lesson"
    assert task["lessonId"] == lesson_id
    assert task["sourceLesson"]["lessonId"] == lesson_id
    assert task["knowledgePointKey"] == "kp-limit-review-service"
    assert task["sourceQuestionKeys"] == ["q1-review-service"]
    assert task["sourceSegmentKeys"] == [segment_key]
    assert task["recommendedAction"]["targetBlockKey"] == str(blocks[0]["blockId"])
    assert task["linkedHandoutBlockId"] == blocks[0]["blockId"]
    assert task["recommendedHandoutBlock"] == {"blockId": blocks[0]["blockId"]}
    assert task["evidenceChain"] == evidence_chain
    assert task["jumpRoute"] == f"/courses/{course_id}/lessons/{lesson_id}/handout"

    dashboard = review_service.get_course_review(course_id=course_id)
    assert dashboard["todayTaskCount"] == 1
    assert dashboard["topTasks"][0]["reviewTaskId"] == task["reviewTaskId"]

    session.close()
    engine.dispose()


def test_sql_lesson_quiz_fallback_uses_lesson_scoped_parsed_resource_segments():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    try:
        course = repo.create_course(
            title="SQLite lesson quiz fallback",
            entry_type="manual_import",
            goal_text="验证课节资源 fallback",
            preferred_style="balanced",
        )
        course_id = _value(course, "courseId", "course_id", "id")
        lesson = repo.create_lesson(course_id=course_id, title="B+ Tree lesson")
        lesson_id = lesson["lessonId"]
        resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/btree.pdf",
                "originalName": "btree.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:btree",
                "scopeType": "lesson",
                "lessonId": lesson_id,
                "usageRole": "lesson_material",
            },
        )
        parse_run, _ = repo.create_parse_run(course_id)
        parse_run_id = parse_run["parseRunId"]
        segments = repo.create_course_segments(
            course_id=course_id,
            resource_id=resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "title": "B+ tree fanout",
                    "textContent": "A B+ tree uses high fanout to reduce lookup depth.",
                    "plainText": "A B+ tree uses high fanout to reduce lookup depth.",
                    "pageNo": 4,
                    "orderNo": 1,
                    "tokenCount": 12,
                }
            ],
        )
        segment_key = segments[0]["segmentKey"]
        repo.mark_parse_run_succeeded(parse_run_id)
        dispatcher = RecordingDispatcher()
        service = QuizService(
            courses=repo,
            lessons=repo,
            quizzes=repo,
            idempotency=repo,
            resources=repo,
            scoped_artifacts=repo,
            task_dispatcher=dispatcher,
            async_tasks=repo,
        )

        trigger = service.generate_lesson_quiz(
            course_id=course_id,
            lesson_id=lesson_id,
            question_count_level="small",
        )

        quiz_id = trigger["entity"]["id"]
        queued = repo.get_quiz(quiz_id)
        assert trigger["status"] == "queued"
        assert queued is not None
        assert queued["status"] == "queued"
        assert queued["scopeType"] == "lesson"
        assert queued["lessonId"] == lesson_id
        assert dispatcher.calls == [
            (
                "quiz_generate",
                trigger["taskId"],
                {
                    "courseId": course_id,
                    "quizId": quiz_id,
                    "questionCountLevel": "small",
                    "scopeType": "lesson",
                    "lessonId": lesson_id,
                    "startLessonId": None,
                    "endLessonId": None,
                },
            )
        ]
        assert segment_key == f"segment-{segments[0]['segmentId']}"
    finally:
        session.close()
        engine.dispose()


def test_sql_lesson_quiz_fallback_rejects_lesson_metadata_only_resource():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    try:
        course = repo.create_course(
            title="SQLite lesson quiz metadata only",
            entry_type="manual_import",
            goal_text="验证 metadata-only 资源不生成 quiz",
            preferred_style="balanced",
        )
        course_id = _value(course, "courseId", "course_id", "id")
        lesson = repo.create_lesson(course_id=course_id, title="Metadata only lesson")
        repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/metadata-only.pdf",
                "originalName": "metadata-only.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:metadata-only",
                "scopeType": "lesson",
                "lessonId": lesson["lessonId"],
                "usageRole": "lesson_material",
            },
        )
        service = QuizService(
            courses=repo,
            lessons=repo,
            quizzes=repo,
            idempotency=repo,
            resources=repo,
            scoped_artifacts=repo,
        )

        with pytest.raises(ServiceError) as exc_info:
            service.generate_lesson_quiz(
                course_id=course_id,
                lesson_id=lesson["lessonId"],
                question_count_level="small",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_code == "quiz.not_ready"
    finally:
        session.close()
        engine.dispose()


def test_sql_lesson_handout_block_refs_reject_course_scoped_citations():
    repository_cls = _discover_sql_repository_class()
    repo, session, engine = _build_sqlite_repository(repository_cls)
    try:
        course = repo.create_course(
            title="SQLite handout citation scope",
            entry_type="manual_import",
            goal_text="验证课时讲义引用不串课程资料",
            preferred_style="balanced",
        )
        course_id = _value(course, "courseId", "course_id", "id")
        lesson = repo.create_lesson(course_id=course_id, title="Scoped lesson")
        lesson_id = lesson["lessonId"]
        course_resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/course-ref.pdf",
                "originalName": "course-ref.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:course-ref",
                "scopeType": "course",
                "usageRole": "course_material",
            },
        )
        lesson_resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/lesson-ref.pdf",
                "originalName": "lesson-ref.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:lesson-ref",
                "scopeType": "lesson",
                "lessonId": lesson_id,
                "usageRole": "lesson_material",
            },
        )
        parse_run, _ = repo.create_parse_run(course_id)
        parse_run_id = parse_run["parseRunId"]
        repo.mark_parse_run_succeeded(parse_run_id)
        course_segment = repo.create_course_segments(
            course_id=course_id,
            resource_id=course_resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "title": "Course scope duplicate topic",
                    "textContent": "Shared B tree scope concept from course material.",
                    "plainText": "Shared B tree scope concept from course material.",
                    "pageNo": 1,
                    "orderNo": 1,
                    "tokenCount": 8,
                }
            ],
        )[0]
        lesson_segment = repo.create_course_segments(
            course_id=course_id,
            resource_id=lesson_resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "title": "Lesson scope source",
                    "textContent": "Shared B tree scope concept from lesson material.",
                    "plainText": "Shared B tree scope concept from lesson material.",
                    "pageNo": 2,
                    "orderNo": 2,
                    "tokenCount": 8,
                }
            ],
        )[0]
        _, _, blocks = repo.create_handout(
            course_id,
            scope_type="lesson",
            lesson_id=lesson_id,
            artifact_kind="lesson_handout",
            outline={
                "title": "Scoped lesson handout",
                "summary": "Scoped lesson handout",
                "items": [
                        {
                            "outlineKey": "scope-section",
                            "title": "Scope section",
                            "summary": "Scope section",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "children": [
                                {
                                    "outlineKey": "scope-block",
                                    "title": "Scope block",
                                    "summary": "Scope block",
                                    "startSec": 0,
                                    "endSec": 60,
                                    "sortNo": 1,
                                "generationStatus": "pending",
                                "sourceSegmentKeys": [lesson_segment["segmentKey"]],
                                "topicTags": [],
                            }
                        ],
                    }
                ],
            },
        )

        saved = repo.save_handout_block_result(
            blocks[0]["blockId"],
            {
                "title": "Scope block",
                "summary": "Scope block",
                "contentMd": "Lesson scoped content.",
                "knowledgePoints": [{"knowledgePointKey": "kp-scope", "displayName": "Scope"}],
                "citations": [
                    {
                        "resourceId": lesson_resource["resourceId"],
                        "segmentKey": lesson_segment["segmentKey"],
                        "pageNo": lesson_segment["pageNo"],
                        "refLabel": "lesson source",
                    },
                    {
                        "resourceId": course_resource["resourceId"],
                        "segmentKey": course_segment["segmentKey"],
                        "pageNo": course_segment["pageNo"],
                        "refLabel": "course source",
                    },
                ],
            },
        )

        assert saved is not None
        assert [citation["resourceId"] for citation in saved["citations"]] == [lesson_resource["resourceId"]]
        assert [citation["pageNo"] for citation in saved["citations"]] == [lesson_segment["pageNo"]]
    finally:
        session.close()
        engine.dispose()
