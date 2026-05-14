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

from server.domain.services.pipelines import PipelineService
from server.domain.services.quizzes import QuizService
from server.infra.db.base import Base
from server.schemas.requests import SubmitQuizRequest


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
