from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from server.domain.services.pipelines import PipelineService
from server.domain.services.quizzes import QuizService
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.schemas.requests import SubmitQuizRequest
from server.tests.test_api import AUTH_HEADERS, create_manual_course, request, upload_ready_pdf


ROOT = Path(__file__).resolve().parents[2]
WEEK2_PIPELINE_STEPS = [
    "resource_validate",
    "caption_extract",
    "document_parse",
    "knowledge_extract",
    "vectorize",
]
PIPELINE_STATUS_VALUES = {
    "idle",
    "queued",
    "running",
    "partial_success",
    "succeeded",
    "failed",
}
STEP_STATUS_VALUES = {
    "queued",
    "running",
    "succeeded",
    "failed",
    "skipped",
    "partial_success",
}


def _post_parse_start(course_id: int, idempotency_key: str) -> tuple[int, dict[str, Any]]:
    return asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/parse/start",
            headers=AUTH_HEADERS | {"idempotency-key": idempotency_key},
        )
    )


class _NoopReviewDispatcher:
    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
        _ = task_id, payload


def _submit_quiz_with_service(repo, quiz_id: int, *, question_id: int, selected_option: str) -> dict[str, Any]:
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=_NoopReviewDispatcher(),
        async_tasks=repo,
    )
    return service.submit_quiz(
        quiz_id=quiz_id,
        payload=SubmitQuizRequest(
            answers=[
                {
                    "questionId": question_id,
                    "selectedOption": selected_option,
                }
            ],
        ),
    )


def test_memory_handout_block_generation_metadata_persists_to_read_models():
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Memory metadata 课程",
        entry_type="manual_import",
        goal_text="验证内存讲义块 metadata",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    handout, _, blocks = repo.create_handout(course_id)
    generation_metadata = {"source": "fallback", "reason": "model_unavailable"}

    saved = repo.save_handout_block_result(
        blocks[0]["blockId"],
        {
            "title": "极限定义",
            "summary": "理解极限定义。",
            "contentMd": "极限定义需要同时关注自变量趋近和函数值趋近。",
            "knowledgePoints": [{"knowledgePointKey": "kp-limit", "displayName": "极限"}],
            "citations": [
                {
                    "resourceId": 501,
                    "segmentId": 101,
                    "segmentKey": "mp4-c1",
                    "startSec": 0,
                    "endSec": 60,
                    "refLabel": "视频 00:00-01:00",
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
    internal_block = repo.store.handouts[handout["handoutVersionId"]]["blocks"][0]
    assert internal_block["citations"][0]["segmentId"] == 101
    assert internal_block["citations"][0]["segmentKey"] == "mp4-c1"
    qa_context = repo.get_qa_context(course_id, blocks[0]["blockId"])
    assert qa_context["currentBlock"]["citations"][0]["segmentId"] == 101
    assert qa_context["currentBlock"]["citations"][0]["segmentKey"] == "mp4-c1"


def test_app_import_keeps_basic_scaffold_without_worker_side_effects():
    script = """
import json
import sys
from server.app import app

routes = sorted(getattr(route, "path", "") for route in app.routes)
print(json.dumps({
    "health": "/health" in routes,
    "parse_start": "/api/v1/courses/{courseId}/parse/start" in routes,
    "pipeline_status": "/api/v1/courses/{courseId}/pipeline-status" in routes,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["health"]
    assert payload["parse_start"]
    assert payload["pipeline_status"]
    assert payload["worker_imported"] is False
    assert payload["broker_imported"] is False
    assert payload["dramatiq_imported"] is False


def test_dramatiq_dispatcher_build_is_lazy_in_explicit_dramatiq_mode():
    script = """
import json
import os
import sys

os.environ["KNOWLINK_TASK_QUEUE"] = "dramatiq"
from server.tasks.dispatcher import build_task_dispatcher

dispatcher = build_task_dispatcher()
print(json.dumps({
    "dispatcher_class": dispatcher.__class__.__name__,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {"KNOWLINK_TASK_QUEUE": "dramatiq"},
    )
    payload = json.loads(result.stdout)

    assert payload["dispatcher_class"] == "DramatiqTaskDispatcher"
    assert payload["worker_imported"] is False
    assert payload["broker_imported"] is False
    assert payload["dramatiq_imported"] is False


def test_task_dispatcher_defaults_to_dramatiq_and_rejects_unknown_queue(monkeypatch):
    from server.tasks.dispatcher import DramatiqTaskDispatcher, NoopTaskDispatcher, build_task_dispatcher

    monkeypatch.delenv("KNOWLINK_TASK_QUEUE", raising=False)
    assert isinstance(build_task_dispatcher(), DramatiqTaskDispatcher)

    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "noop")
    assert isinstance(build_task_dispatcher(), NoopTaskDispatcher)

    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "unknown")
    with pytest.raises(RuntimeError, match="Unsupported KNOWLINK_TASK_QUEUE"):
        build_task_dispatcher()


def test_settings_loads_root_dotenv_before_reading_environment(monkeypatch, tmp_path):
    from server.config import settings as settings_module

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KNOWLINK_HOST=127.0.0.9\nKNOWLINK_TASK_QUEUE=noop\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DOTENV_PATH", dotenv_path)
    monkeypatch.delenv("KNOWLINK_DISABLE_DOTENV", raising=False)
    monkeypatch.delenv("KNOWLINK_HOST", raising=False)
    monkeypatch.delenv("KNOWLINK_TASK_QUEUE", raising=False)
    settings_module.get_settings.cache_clear()

    try:
        settings = settings_module.get_settings()
    finally:
        settings_module.get_settings.cache_clear()
        os.environ.pop("KNOWLINK_HOST", None)
        os.environ.pop("KNOWLINK_TASK_QUEUE", None)

    assert settings.host == "127.0.0.9"
    assert settings.task_queue == "noop"


def test_settings_keeps_real_environment_above_dotenv(monkeypatch, tmp_path):
    from server.config import settings as settings_module

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KNOWLINK_HOST=127.0.0.9\nKNOWLINK_TASK_QUEUE=noop\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DOTENV_PATH", dotenv_path)
    monkeypatch.delenv("KNOWLINK_DISABLE_DOTENV", raising=False)
    monkeypatch.setenv("KNOWLINK_HOST", "10.0.0.5")
    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "dramatiq")
    settings_module.get_settings.cache_clear()

    try:
        settings = settings_module.get_settings()
    finally:
        settings_module.get_settings.cache_clear()

    assert settings.host == "10.0.0.5"
    assert settings.task_queue == "dramatiq"


def test_settings_can_disable_root_dotenv_for_test_isolation(monkeypatch, tmp_path):
    from server.config import settings as settings_module

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KNOWLINK_HOST=127.0.0.9\nKNOWLINK_TASK_QUEUE=noop\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DOTENV_PATH", dotenv_path)
    monkeypatch.setenv("KNOWLINK_DISABLE_DOTENV", "1")
    monkeypatch.delenv("KNOWLINK_HOST", raising=False)
    monkeypatch.delenv("KNOWLINK_TASK_QUEUE", raising=False)
    settings_module.get_settings.cache_clear()

    try:
        settings = settings_module.get_settings()
    finally:
        settings_module.get_settings.cache_clear()

    assert settings.host == "0.0.0.0"
    assert settings.task_queue == "dramatiq"


def test_settings_reject_unknown_task_queue_at_startup(monkeypatch):
    from server.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "unknown")

    try:
        with pytest.raises(RuntimeError, match="Unsupported KNOWLINK_TASK_QUEUE"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_production_like_settings_reject_insecure_auth_and_minio_defaults(monkeypatch):
    from server.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("KNOWLINK_ENV", "production")
    monkeypatch.setenv("KNOWLINK_STORAGE_BACKEND", "minio")
    monkeypatch.setenv("KNOWLINK_DEMO_TOKEN", "knowlink-demo-token")
    monkeypatch.setenv("KNOWLINK_MINIO_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("KNOWLINK_MINIO_SECRET_KEY", "minioadmin")

    try:
        with pytest.raises(RuntimeError) as exc_info:
            get_settings()
    finally:
        get_settings.cache_clear()

    message = str(exc_info.value)
    assert "KNOWLINK_DEMO_TOKEN" in message
    assert "KNOWLINK_MINIO_ACCESS_KEY" in message
    assert "KNOWLINK_MINIO_SECRET_KEY" in message


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KNOWLINK_TASK_QUEUE", "noop"),
        ("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "memory"),
        ("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "demo"),
        ("KNOWLINK_STORAGE_BACKEND", "demo"),
        ("KNOWLINK_STORAGE_BACKEND", "fake"),
        ("KNOWLINK_STORAGE_BACKEND", "memory"),
        ("KNOWLINK_STORAGE_BACKEND", "local"),
        ("KNOWLINK_STORAGE_BACKEND", "disabled"),
    ],
)
def test_production_like_settings_reject_lossy_runtime_modes(monkeypatch, name: str, value: str):
    from server.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("KNOWLINK_ENV", "production")
    monkeypatch.setenv("KNOWLINK_DEMO_TOKEN", "production-token")
    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "dramatiq")
    monkeypatch.setenv("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "sql")
    monkeypatch.setenv("KNOWLINK_STORAGE_BACKEND", "minio")
    monkeypatch.setenv("KNOWLINK_MINIO_ACCESS_KEY", "production-access")
    monkeypatch.setenv("KNOWLINK_MINIO_SECRET_KEY", "production-secret")
    monkeypatch.setenv(name, value)

    try:
        with pytest.raises(RuntimeError) as exc_info:
            get_settings()
    finally:
        get_settings.cache_clear()

    message = str(exc_info.value)
    assert name in message
    assert value in message


def test_development_settings_still_allow_explicit_noop_memory_and_demo_modes(monkeypatch):
    from server.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("KNOWLINK_ENV", "development")
    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "noop")
    monkeypatch.setenv("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "memory")
    monkeypatch.setenv("KNOWLINK_STORAGE_BACKEND", "demo")

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.task_queue == "noop"
    assert settings.runtime_repository_backend == "memory"
    assert settings.storage_backend == "demo"


def test_dramatiq_default_actor_path_resolves_parse_pipeline_actor():
    from server.tasks.dispatcher import DramatiqTaskDispatcher

    dispatcher = DramatiqTaskDispatcher()
    actor = dispatcher._load_actor(dispatcher.parse_pipeline_actor_path)

    assert hasattr(actor, "send")


def test_legacy_global_repository_backend_env_is_ignored():
    script = """
import json
from server.config.settings import get_settings

settings = get_settings()
print(json.dumps({
    "runtime_repository_backend": settings.runtime_repository_backend,
    "has_repository_backend": hasattr(settings, "repository_backend"),
}))
"""
    env = os.environ.copy()
    env["KNOWLINK_REPOSITORY_BACKEND"] = "sql"
    env.pop("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "runtime_repository_backend": "memory",
        "has_repository_backend": False,
    }


def test_storage_backend_minio_wires_from_settings_without_connecting():
    script = """
import json

from server.api.deps import _get_object_storage

storage = _get_object_storage()
print(json.dumps({
    "storage_class": storage.__class__.__name__,
    "bucket_name": storage.bucket_name,
    "scheme": storage.client._base_url._url.scheme,
}))
"""
    env = os.environ.copy()
    env["KNOWLINK_STORAGE_BACKEND"] = "minio"
    env["KNOWLINK_MINIO_ENDPOINT"] = "minio.internal:9443"
    env["KNOWLINK_MINIO_ACCESS_KEY"] = "access"
    env["KNOWLINK_MINIO_SECRET_KEY"] = "secret"
    env["KNOWLINK_MINIO_BUCKET"] = "runtime-assets"
    env["KNOWLINK_MINIO_SECURE"] = "true"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "storage_class": "MinioObjectStorage",
        "bucket_name": "runtime-assets",
        "scheme": "https",
    }


def test_runtime_repository_backend_sql_mode_keeps_week2_api_flow_on_sqlite(tmp_path):
    script = """
import asyncio
import json

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import get_engine
from server.tests.test_api import AUTH_HEADERS, request

Base.metadata.create_all(get_engine())

async def main():
    create_status, create_body = await request(
        "POST",
        "/api/v1/courses",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-course"},
        json_body={
            "title": "SQL runtime API course",
            "entryType": "manual_import",
            "goalText": "verify SQL runtime API flow",
            "preferredStyle": "balanced",
        },
    )
    course_id = create_body["data"]["course"]["courseId"]

    upload_status, upload_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/resources/upload-complete",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-upload"},
        json_body={
            "resourceType": "pdf",
            "scopeType": "course",
            "objectKey": f"raw/1/{course_id}/sql-runtime.pdf",
            "originalName": "sql-runtime.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:sql-runtime",
        },
    )
    resources_status, resources_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/resources",
        headers=AUTH_HEADERS,
    )
    parse_status, parse_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/parse/start",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-parse"},
    )
    pipeline_status, pipeline_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/pipeline-status",
        headers=AUTH_HEADERS,
    )

    print(json.dumps({
        "create_status": create_status,
        "upload_status": upload_status,
        "resource_id": upload_body["data"]["resourceId"],
        "resources_status": resources_status,
        "resource_ids": [
            resource["resourceId"]
            for resource in resources_body["data"]["items"]
        ],
        "parse_status": parse_status,
        "parse_entity_type": parse_body["data"]["entity"]["type"],
        "pipeline_status": pipeline_status,
        "pipeline_course_status": pipeline_body["data"]["courseStatus"]["pipelineStatus"],
        "step_codes": [
            step["code"]
            for step in pipeline_body["data"]["steps"]
        ],
    }))

asyncio.run(main())
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'runtime.sqlite3'}"
    env["KNOWLINK_STORAGE_BACKEND"] = "demo"
    env["KNOWLINK_TASK_QUEUE"] = "noop"
    env.pop("KNOWLINK_REPOSITORY_BACKEND", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["create_status"] == 201
    assert payload["upload_status"] == 201
    assert payload["resources_status"] == 200
    assert payload["resource_id"] in payload["resource_ids"]
    assert payload["parse_status"] == 200
    assert payload["parse_entity_type"] == "parse_run"
    assert payload["pipeline_status"] == 200
    assert payload["pipeline_course_status"] in PIPELINE_STATUS_VALUES
    assert payload["step_codes"] == WEEK2_PIPELINE_STEPS


def test_handout_service_uses_sql_runtime_repository_for_api_wiring(tmp_path):
    script = """
import asyncio
import json

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tests.test_api import AUTH_HEADERS, request
from server.tests.test_runtime_wiring_contract import _submit_quiz_with_service

Base.metadata.create_all(get_engine())

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title="SQL handout API course",
        entry_type="manual_import",
        goal_text="verify SQL handout API wiring",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "mp4",
            "objectKey": f"raw/1/{course_id}/outline.mp4",
            "originalName": "outline.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": 2048,
            "checksum": "sha256:outline-video",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(parse_run["parseRunId"])
    repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run["parseRunId"],
        segments=[
            {
                "segmentType": "video_caption",
                "orderNo": 1,
                "textContent": "第一段介绍集合的基本概念。",
                "startSec": 0,
                "endSec": 60,
            },
            {
                "segmentType": "video_caption",
                "orderNo": 2,
                "textContent": "第二段说明元素和属于关系。",
                "startSec": 60,
                "endSec": 120,
            },
        ],
    )
finally:
    session.close()

async def main():
    handout_status, handout_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/handouts/generate",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-handout"},
    )
    outline_status, outline_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/handouts/latest/outline",
        headers=AUTH_HEADERS,
    )
    print(json.dumps({
        "handout_status": handout_status,
        "entity_type": handout_body["data"]["entity"]["type"],
        "outline_status": outline_status,
        "outline_section_count": len(outline_body["data"]["items"]),
        "outline_child_count": len(outline_body["data"]["items"][0]["children"]),
        "outline_generation_status": outline_body["data"]["items"][0]["children"][0]["generationStatus"],
    }))

asyncio.run(main())
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'handout.sqlite3'}"
    env["KNOWLINK_STORAGE_BACKEND"] = "demo"
    env["KNOWLINK_TASK_QUEUE"] = "noop"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload == {
        "handout_status": 200,
        "entity_type": "handout_version",
        "outline_status": 200,
        "outline_section_count": 1,
        "outline_child_count": 1,
        "outline_generation_status": "pending",
    }


def test_quiz_service_uses_sql_runtime_repository_and_worker_for_api_wiring(tmp_path):
    script = """
import asyncio
import json

import sqlalchemy as sa

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks.quizzes import run_quiz_generate
from server.tasks.reviews import run_review_refresh
from server.tests.test_api import AUTH_HEADERS, request

Base.metadata.create_all(get_engine())

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title="SQL quiz API course",
        entry_type="manual_import",
        goal_text="verify SQL quiz API wiring",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/quiz.pdf",
            "originalName": "quiz.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 2048,
            "checksum": "sha256:quiz-pdf",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(parse_run["parseRunId"])
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run["parseRunId"],
        segments=[
            {
                "segmentType": "pdf_page_text",
                "orderNo": 1,
                "textContent": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "plainText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
            },
        ],
    )
    segment_key = segments[0]["segmentKey"]
    handout, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "极限复习目录",
            "summary": "围绕极限定义组织复习。",
            "items": [
                {
                    "outlineKey": "section-limit",
                    "title": "极限",
                    "summary": "极限定义",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-limit",
                            "title": "极限定义",
                            "summary": "理解极限定义的条件。",
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
            "summary": "理解极限定义的条件。",
            "contentMd": "极限定义需要同时关注自变量趋近和函数值趋近。",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
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
    repo.save_inquiry_answers(
        course_id,
        [
            {"key": "mastery_level", "value": "advanced"},
            {"key": "time_budget_minutes", "value": 120},
            {"key": "handout_style", "value": "exam"},
        ],
    )
finally:
    session.close()

async def main():
    generate_status, generate_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/quizzes/generate",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-quiz"},
        json_body={"questionCountLevel": "large"},
    )
    task_id = generate_body["data"]["taskId"]
    quiz_id = generate_body["data"]["entity"]["id"]
    captured_generation = {}

    def fake_generate_quiz(block_payloads, *, segments, course_context, preferences, question_count_level):
        captured_generation.update({
            "blockCount": len(block_payloads),
            "segmentCount": len(segments),
            "courseTitle": course_context["title"],
            "preferenceSelfLevel": preferences["selfLevel"],
            "questionCountLevel": question_count_level,
            "segmentKey": segments[0]["segmentKey"],
        })
        block_key = str(block_payloads[0]["blockId"])
        segment_key = block_payloads[0]["sourceSegmentKeys"][0]
        return {
            "quizType": "chapter_review",
            "questions": [
                {
                    "questionKey": f"q{index}-kp-limit",
                    "questionType": "single_choice",
                    "stemMd": "关于极限定义，哪项说法符合当前材料？",
                    "options": ["A. 同时关注自变量趋近和函数值趋近。", "B. 只需要记住名称。", "C. 与当前材料无关。", "D. 当前材料没有依据。"],
                    "correctAnswer": "A",
                    "explanationMd": "依据当前课程的极限定义讲义块。",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-limit",
                    "knowledgePointName": "极限定义",
                    "sourceBlockKey": block_key,
                    "sourceSegmentKeys": [segment_key],
                }
                for index in range(1, 6)
            ],
        }

    run_quiz_generate(
        {"taskId": task_id, "courseId": course_id, "quizId": quiz_id, "questionCountLevel": "large"},
        generate_quiz_func=fake_generate_quiz,
    )
    quiz_status, quiz_body = await request(
        "GET",
        f"/api/v1/quizzes/{quiz_id}",
        headers=AUTH_HEADERS,
    )
    first_question_id = quiz_body["data"]["questions"][0]["questionId"]
    submit_status, submit_body = await request(
        "POST",
        f"/api/v1/quizzes/{quiz_id}/attempts",
        headers=AUTH_HEADERS,
        json_body={"answers": [{"questionId": first_question_id, "selectedOption": "A"}]},
    )
    review_task_run_id = submit_body["data"]["reviewTaskRunId"]

    sync_session = create_session()
    try:
        tables = Base.metadata.tables
        review_refresh_task_id = sync_session.execute(
            sa.select(tables["async_tasks"].c.id).where(
                tables["async_tasks"].c.task_type == "review_refresh",
                tables["async_tasks"].c.target_id == review_task_run_id,
            )
        ).scalar_one()
    finally:
        sync_session.close()

    run_review_refresh(
        {
            "taskId": review_refresh_task_id,
            "courseId": course_id,
            "reviewTaskRunId": review_task_run_id,
        }
    )
    review_status, review_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/review-tasks",
        headers=AUTH_HEADERS,
    )
    initial_review_task_id = review_body["data"]["items"][0]["reviewTaskId"]
    run_status, run_body = await request(
        "GET",
        f"/api/v1/review-task-runs/{review_task_run_id}/status",
        headers=AUTH_HEADERS,
    )
    regenerate_status, regenerate_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/review-tasks/regenerate",
        headers=AUTH_HEADERS | {"idempotency-key": "sql-api-review-regenerate"},
    )
    regenerated_run_id = regenerate_body["data"]["entity"]["id"]
    queued_review_status, queued_review_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/review-tasks",
        headers=AUTH_HEADERS,
    )
    queued_old_complete_status, queued_old_complete_body = await request(
        "POST",
        f"/api/v1/review-tasks/{initial_review_task_id}/complete",
        headers=AUTH_HEADERS,
    )

    sync_session = create_session()
    try:
        tables = Base.metadata.tables
        regenerated_task_id = sync_session.execute(
            sa.select(tables["async_tasks"].c.id).where(
                tables["async_tasks"].c.task_type == "review_refresh",
                tables["async_tasks"].c.target_id == regenerated_run_id,
            )
        ).scalar_one()
    finally:
        sync_session.close()

    run_review_refresh(
        {
            "taskId": regenerated_task_id,
            "courseId": course_id,
            "reviewTaskRunId": regenerated_run_id,
        }
    )
    regenerated_status, regenerated_body = await request(
        "GET",
        f"/api/v1/review-task-runs/{regenerated_run_id}/status",
        headers=AUTH_HEADERS,
    )
    regenerated_review_status, regenerated_review_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/review-tasks",
        headers=AUTH_HEADERS,
    )
    stale_complete_status, stale_complete_body = await request(
        "POST",
        f"/api/v1/review-tasks/{initial_review_task_id}/complete",
        headers=AUTH_HEADERS,
    )

    sync_session = create_session()
    try:
        tables = Base.metadata.tables
        question_ref_count = sync_session.execute(sa.select(sa.func.count()).select_from(tables["quiz_question_refs"])).scalar_one()
        attempt_count = sync_session.execute(sa.select(sa.func.count()).select_from(tables["quiz_attempts"])).scalar_one()
        attempt_item_count = sync_session.execute(sa.select(sa.func.count()).select_from(tables["quiz_attempt_items"])).scalar_one()
        mastery_count = sync_session.execute(sa.select(sa.func.count()).select_from(tables["mastery_records"])).scalar_one()
        review_task_count = sync_session.execute(sa.select(sa.func.count()).select_from(tables["review_tasks"])).scalar_one()
        pending_review_task_count = sync_session.execute(
            sa.select(sa.func.count()).select_from(tables["review_tasks"]).where(
                tables["review_tasks"].c.status == "pending",
            )
        ).scalar_one()
        superseded_review_task_count = sync_session.execute(
            sa.select(sa.func.count()).select_from(tables["review_tasks"]).where(
                tables["review_tasks"].c.status == "superseded",
            )
        ).scalar_one()
        review_ref_count = sync_session.execute(sa.select(sa.func.count()).select_from(tables["review_task_refs"])).scalar_one()
    finally:
        sync_session.close()

    complete_status, complete_body = await request(
        "POST",
        f"/api/v1/review-tasks/{regenerated_review_body['data']['items'][0]['reviewTaskId']}/complete",
        headers=AUTH_HEADERS,
    )

    sync_session = create_session()
    try:
        repo = SqlAlchemyRuntimeRepository(sync_session)
        new_parse_run, _ = repo.create_parse_run(course_id)
        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])
    finally:
        sync_session.close()
    stale_review_status, stale_review_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/review-tasks",
        headers=AUTH_HEADERS,
    )

    print(json.dumps({
        "generate_status": generate_status,
        "entity_type": generate_body["data"]["entity"]["type"],
        "quiz_status": quiz_status,
        "quiz_ready_status": quiz_body["data"]["status"],
        "question_count": quiz_body["data"]["questionCount"],
        "captured_generation": captured_generation,
        "submit_status": submit_status,
        "attempt_id": submit_body["data"]["attemptId"],
        "review_task_run_id": review_task_run_id,
        "mastery_delta_count": len(submit_body["data"]["masteryDelta"]),
        "review_status": review_status,
        "review_count": len(review_body["data"]["items"]),
        "review_first_has_segment": review_body["data"]["items"][0]["recommendedSegment"] is not None,
        "review_first_has_practice": review_body["data"]["items"][0]["practiceEntry"] is not None,
        "run_status": run_status,
        "run_ready_status": run_body["data"]["status"],
        "complete_status": complete_status,
        "complete_body": complete_body["data"],
        "regenerate_status": regenerate_status,
        "regenerate_entity_type": regenerate_body["data"]["entity"]["type"],
        "queued_review_status": queued_review_status,
        "queued_review_count": len(queued_review_body["data"]["items"]),
        "queued_old_complete_status": queued_old_complete_status,
        "queued_old_complete_body": queued_old_complete_body["data"],
        "regenerated_status": regenerated_status,
        "regenerated_ready_status": regenerated_body["data"]["status"],
        "regenerated_review_status": regenerated_review_status,
        "regenerated_review_count": len(regenerated_review_body["data"]["items"]),
        "stale_complete_status": stale_complete_status,
        "stale_complete_body": stale_complete_body["data"],
        "stale_review_status": stale_review_status,
        "stale_review_count": len(stale_review_body["data"]["items"]),
        "question_ref_count": question_ref_count,
        "attempt_count": attempt_count,
        "attempt_item_count": attempt_item_count,
        "mastery_count": mastery_count,
        "review_task_count": review_task_count,
        "pending_review_task_count": pending_review_task_count,
        "superseded_review_task_count": superseded_review_task_count,
        "review_ref_count": review_ref_count,
    }))

asyncio.run(main())
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'quiz.sqlite3'}"
    env["KNOWLINK_STORAGE_BACKEND"] = "demo"
    env["KNOWLINK_TASK_QUEUE"] = "noop"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["generate_status"] == 200
    assert payload["entity_type"] == "quiz"
    assert payload["quiz_status"] == 200
    assert payload["quiz_ready_status"] == "ready"
    assert payload["question_count"] == 5
    assert payload["captured_generation"]["blockCount"] == 1
    assert payload["captured_generation"]["segmentCount"] == 1
    assert payload["captured_generation"]["courseTitle"] == "SQL quiz API course"
    assert payload["captured_generation"]["preferenceSelfLevel"] == "advanced"
    assert payload["captured_generation"]["questionCountLevel"] == "large"
    assert payload["captured_generation"]["segmentKey"].startswith("segment-")
    assert payload["submit_status"] == 200
    assert payload["attempt_id"] > 0
    assert payload["review_task_run_id"] > 0
    assert payload["mastery_delta_count"] >= 1
    assert payload["review_status"] == 200
    assert 1 <= payload["review_count"] <= 3
    assert payload["review_first_has_segment"] is True
    assert payload["review_first_has_practice"] is True
    assert payload["run_status"] == 200
    assert payload["run_ready_status"] == "ready"
    assert payload["complete_status"] == 200
    assert payload["complete_body"]["completed"] is True
    assert payload["regenerate_status"] == 200
    assert payload["regenerate_entity_type"] == "review_task_run"
    assert payload["queued_review_status"] == 200
    assert payload["queued_review_count"] == 0
    assert payload["queued_old_complete_status"] == 200
    assert payload["queued_old_complete_body"]["completed"] is False
    assert payload["regenerated_status"] == 200
    assert payload["regenerated_ready_status"] == "ready"
    assert payload["regenerated_review_status"] == 200
    assert 1 <= payload["regenerated_review_count"] <= 3
    assert payload["stale_complete_status"] == 200
    assert payload["stale_complete_body"]["completed"] is False
    assert payload["stale_review_status"] == 200
    assert payload["stale_review_count"] == 0
    assert payload["question_ref_count"] >= 1
    assert payload["attempt_count"] == 1
    assert payload["attempt_item_count"] == payload["question_count"]
    assert payload["mastery_count"] >= 1
    assert payload["review_task_count"] >= payload["pending_review_task_count"]
    assert 1 <= payload["pending_review_task_count"] <= 3
    assert payload["superseded_review_task_count"] >= 1
    assert payload["review_ref_count"] >= 1


def test_stale_quiz_generate_task_does_not_update_current_course_after_reparse(tmp_path):
    script = """
import json

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.models import AsyncTask, Course, Quiz
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks.quizzes import run_quiz_generate

Base.metadata.create_all(get_engine())

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title="SQL stale quiz course",
        entry_type="manual_import",
        goal_text="verify stale quiz worker isolation",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/stale-quiz.pdf",
            "originalName": "stale-quiz.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:stale-quiz",
        },
    )
    old_parse, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(old_parse["parseRunId"])
    old_segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=old_parse["parseRunId"],
        segments=[
            {
                "segmentType": "pdf_page_text",
                "orderNo": 1,
                "textContent": "旧解析片段。",
                "plainText": "旧解析片段。",
                "pageNo": 1,
            }
        ],
    )
    _, _, old_blocks = repo.create_handout(
        course_id,
        outline={
            "title": "旧目录",
            "summary": "旧讲义。",
            "items": [
                {
                    "outlineKey": "old-section",
                    "title": "旧章节",
                    "summary": "旧章节。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "old-block",
                            "title": "旧讲义块",
                            "summary": "旧讲义块。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [old_segments[0]["segmentKey"]],
                            "topicTags": [],
                        }
                    ],
                }
            ],
        },
    )
    repo.save_handout_block_result(
        old_blocks[0]["blockId"],
        {
            "title": "旧讲义块",
            "summary": "旧讲义块。",
            "contentMd": "旧解析片段。",
            "knowledgePoints": [{"knowledgePointKey": "old-kp", "displayName": "旧知识点"}],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentKey": old_segments[0]["segmentKey"],
                    "pageNo": 1,
                    "refLabel": "PDF 第 1 页",
                }
            ],
        },
    )
    _, trigger = repo.create_quiz(course_id)
    task_id = trigger["taskId"]
    quiz_id = trigger["entity"]["id"]

    new_parse, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(new_parse["parseRunId"])
finally:
    session.close()

result = run_quiz_generate({"taskId": task_id, "courseId": course_id, "quizId": quiz_id})

session = create_session()
try:
    course_row = session.get(Course, course_id)
    task_row = session.get(AsyncTask, task_id)
    quiz_row = session.get(Quiz, quiz_id)
    print(json.dumps({
        "result_status": result["status"],
        "course_pipeline_stage": course_row.pipeline_stage,
        "course_pipeline_status": course_row.pipeline_status,
        "course_last_error": course_row.last_error,
        "active_parse_run_id": course_row.active_parse_run_id,
        "active_handout_version_id": course_row.active_handout_version_id,
        "task_status": task_row.status,
        "quiz_status": quiz_row.status,
    }))
finally:
    session.close()
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'stale-quiz.sqlite3'}"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["result_status"] == "failed"
    assert payload["task_status"] == "failed"
    assert payload["quiz_status"] == "failed"
    assert payload["course_pipeline_stage"] == "parse"
    assert payload["course_pipeline_status"] == "succeeded"
    assert payload["course_last_error"] is None
    assert payload["active_handout_version_id"] is None


def test_quiz_generate_worker_marks_failed_without_saving_questions_on_deepseek_error(tmp_path):
    script = """
import json

import sqlalchemy as sa

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.models import AsyncTask, Course, Quiz
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks.quizzes import run_quiz_generate

Base.metadata.create_all(get_engine())

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title="SQL failed quiz course",
        entry_type="manual_import",
        goal_text="verify failed DeepSeek quiz path",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/failed-quiz.pdf",
            "originalName": "failed-quiz.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:failed-quiz",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(parse_run["parseRunId"])
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run["parseRunId"],
        segments=[
            {
                "segmentType": "pdf_page_text",
                "orderNo": 1,
                "textContent": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "plainText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
            }
        ],
    )
    _, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "失败测验目录",
            "summary": "用于失败路径验证。",
            "items": [
                {
                    "outlineKey": "section-failed",
                    "title": "极限",
                    "summary": "极限定义。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-failed",
                            "title": "极限定义",
                            "summary": "极限定义。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segments[0]["segmentKey"]],
                            "topicTags": [],
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
            "summary": "极限定义。",
            "contentMd": "极限定义需要同时关注自变量趋近和函数值趋近。",
            "knowledgePoints": [{"knowledgePointKey": "kp-limit", "displayName": "极限定义"}],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentKey": segments[0]["segmentKey"],
                    "pageNo": 2,
                    "refLabel": "PDF 第 2 页",
                }
            ],
        },
    )
    _, trigger = repo.create_quiz(course_id, question_count_level="small")
    task_id = trigger["taskId"]
    quiz_id = trigger["entity"]["id"]
finally:
    session.close()

def failing_generate(*args, **kwargs):
    raise RuntimeError("deepseek timeout")

result = run_quiz_generate(
    {"taskId": task_id, "courseId": course_id, "quizId": quiz_id, "questionCountLevel": "small"},
    generate_quiz_func=failing_generate,
)

session = create_session()
try:
    tables = Base.metadata.tables
    course_row = session.get(Course, course_id)
    task_row = session.get(AsyncTask, task_id)
    quiz_row = session.get(Quiz, quiz_id)
    question_count = session.execute(sa.select(sa.func.count()).select_from(tables["quiz_questions"])).scalar_one()
    print(json.dumps({
        "result_status": result["status"],
        "task_status": task_row.status,
        "quiz_status": quiz_row.status,
        "course_pipeline_status": course_row.pipeline_status,
        "question_count": question_count,
        "task_error": task_row.error_message,
    }))
finally:
    session.close()
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'failed-quiz.sqlite3'}"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["result_status"] == "failed"
    assert payload["task_status"] == "failed"
    assert payload["quiz_status"] == "failed"
    assert payload["course_pipeline_status"] == "failed"
    assert payload["question_count"] == 0
    assert "deepseek timeout" in payload["task_error"]


def test_home_and_progress_use_sql_runtime_repository_for_api_wiring(tmp_path):
    script = """
import asyncio
import json

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tests.test_api import AUTH_HEADERS, request
from server.tests.test_runtime_wiring_contract import _submit_quiz_with_service

Base.metadata.create_all(get_engine())

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title="SQL dashboard course",
        entry_type="manual_import",
        goal_text="verify SQL dashboard and progress wiring",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/dashboard.pdf",
            "originalName": "dashboard.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:dashboard",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(parse_run["parseRunId"])
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run["parseRunId"],
        segments=[
            {
                "segmentType": "pdf_page_text",
                "orderNo": 1,
                "textContent": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "plainText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    _, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "首页聚合目录",
            "summary": "用于首页聚合验证。",
            "items": [
                {
                    "outlineKey": "section-dashboard",
                    "title": "极限",
                    "summary": "极限定义。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-dashboard",
                            "title": "极限定义",
                            "summary": "理解极限定义的条件。",
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
            "summary": "理解极限定义的条件。",
            "contentMd": "极限定义需要同时关注自变量趋近和函数值趋近。",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit-dashboard",
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
    quiz_payload = {
        "quizType": "chapter_review",
        "questions": [
            {
                "questionKey": "q1-dashboard",
                "questionType": "single_choice",
                "stemMd": "极限定义关注什么？",
                "options": ["自变量趋近与函数值趋近", "只关注图像", "只关注常数", "只关注面积"],
                "correctAnswer": "B",
                "explanationMd": "这里故意提交错选项以生成复习优先级。",
                "difficultyLevel": "medium",
                "knowledgePointKey": "kp-limit-dashboard",
                "knowledgePointName": "极限定义",
                "sourceBlockKey": str(blocks[0]["blockId"]),
                "sourceSegmentKeys": [segment_key],
            }
        ],
    }
    repo.save_quiz_generation_result(
        quiz["quizId"],
        quiz_payload,
        [
            {
                "questionKey": "q1-dashboard",
                "resourceId": resource["resourceId"],
                "segmentId": segments[0]["segmentId"],
                "segmentKey": segment_key,
                "refType": "pdf_page",
                "quoteText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
                "refLabel": "PDF 第 2 页",
                "sortNo": 1,
            }
        ],
    )
    first_question_id = repo.get_quiz(quiz["quizId"])["questions"][0]["questionId"]
    attempt = _submit_quiz_with_service(
        repo,
        quiz["quizId"],
        question_id=first_question_id,
        selected_option="A",
    )
    review_run_id = attempt["reviewTaskRunId"]
    repo.save_review_task_run_result(
        review_run_id,
        {
            "tasks": [
                {
                    "taskKey": "review-dashboard",
                    "taskType": "revisit_block",
                    "priorityScore": 96,
                    "reasonText": "错题知识点建议优先回看。",
                    "recommendedMinutes": 12,
                    "knowledgePointKey": "kp-limit-dashboard",
                    "sourceQuestionKeys": ["q1-dashboard"],
                    "sourceBlockKey": str(blocks[0]["blockId"]),
                    "sourceSegmentKeys": [segment_key],
                    "reviewOrder": 1,
                    "recommendedAction": {"type": "revisit_block", "targetBlockKey": str(blocks[0]["blockId"])},
                }
            ]
        },
        [
            {
                "taskKey": "review-dashboard",
                "resourceId": resource["resourceId"],
                "segmentId": segments[0]["segmentId"],
                "segmentKey": segment_key,
                "refType": "pdf_page",
                "quoteText": "极限定义需要同时关注自变量趋近和函数值趋近。",
                "pageNo": 2,
                "refLabel": "PDF 第 2 页",
                "sortNo": 1,
            }
        ],
    )
finally:
    session.close()

async def main():
    progress_status, progress_body = await request(
        "POST",
        f"/api/v1/courses/{course_id}/progress",
        headers=AUTH_HEADERS,
        json_body={
            "lastPositionSec": 240,
            "lastAnchorKey": "dashboard-anchor",
            "lastActivityAt": "2000-01-01T00:00:00+00:00",
        },
    )
    read_progress_status, read_progress_body = await request(
        "GET",
        f"/api/v1/courses/{course_id}/progress",
        headers=AUTH_HEADERS,
    )
    dashboard_status, dashboard_body = await request(
        "GET",
        "/api/v1/home/dashboard",
        headers=AUTH_HEADERS,
    )
    dashboard = dashboard_body["data"]
    print(json.dumps({
        "progress_status": progress_status,
        "progress": progress_body["data"],
        "read_progress_status": read_progress_status,
        "read_progress": read_progress_body["data"],
        "dashboard_status": dashboard_status,
        "recent_title": dashboard["recentCourses"][0]["title"],
        "top_review_count": len(dashboard["topReviewTasks"]),
        "top_review_priority": dashboard["topReviewTasks"][0]["priorityScore"],
        "daily_points": dashboard["dailyRecommendedKnowledgePoints"],
        "learning_stats": dashboard["learningStats"],
    }))

asyncio.run(main())
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'dashboard.sqlite3'}"
    env["KNOWLINK_STORAGE_BACKEND"] = "demo"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["progress_status"] == 200
    assert payload["progress"]["courseId"] > 0
    assert payload["progress"]["lastPositionSec"] == 240
    assert payload["progress"]["lastAnchorKey"] == "dashboard-anchor"
    assert not payload["progress"]["lastActivityAt"].startswith("2000-01-01")
    assert payload["read_progress_status"] == 200
    assert payload["read_progress"] == payload["progress"]
    assert payload["dashboard_status"] == 200
    assert payload["recent_title"] == "SQL dashboard course"
    assert payload["top_review_count"] == 1
    assert payload["top_review_priority"] == 96
    assert payload["daily_points"][0]["knowledgePoint"] == "极限定义"
    assert payload["daily_points"][0]["targetCourseId"] == payload["progress"]["courseId"]
    assert payload["learning_stats"]["streakDays"] >= 1
    assert payload["learning_stats"]["completedCourses"] == 1
    assert payload["learning_stats"]["reviewTasksCompleted"] == 0
    assert payload["learning_stats"]["totalLearningMinutes"] >= 4


def test_progress_rejects_cross_course_and_cross_user_references(tmp_path):
    script = """
import asyncio
import json

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tests.test_api import AUTH_HEADERS, request

Base.metadata.create_all(get_engine())

def create_course_context(repo, *, title, checksum):
    course = repo.create_course(
        title=title,
        entry_type="manual_import",
        goal_text="verify progress ownership",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/{checksum}.pdf",
            "originalName": f"{checksum}.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": f"sha256:{checksum}",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(parse_run["parseRunId"])
    handout, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": f"{title} 目录",
            "summary": "用于 progress ownership 验证。",
            "items": [
                {
                    "outlineKey": f"section-{checksum}",
                    "title": "章节",
                    "summary": "章节。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": f"block-{checksum}",
                            "title": "讲义块",
                            "summary": "讲义块。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [],
                            "topicTags": [],
                        }
                    ],
                }
            ],
        },
    )
    return {
        "courseId": course_id,
        "resourceId": resource["resourceId"],
        "handoutVersionId": handout["handoutVersionId"],
        "blockId": blocks[0]["blockId"],
    }

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    owner_course = create_course_context(repo, title="Owner progress course", checksum="owner-progress")
    foreign_course = create_course_context(repo, title="Foreign progress course", checksum="foreign-progress")
    other_user_repo = SqlAlchemyRuntimeRepository(session, user_id=2)
    other_user_course = create_course_context(
        other_user_repo,
        title="Other user progress course",
        checksum="other-user-progress",
    )
    cross_user_rejected = False
    try:
        repo.update_progress(
            owner_course["courseId"],
            {"lastVideoResourceId": other_user_course["resourceId"]},
        )
    except ValueError:
        cross_user_rejected = True
finally:
    session.close()

async def main():
    valid_status, valid_body = await request(
        "POST",
        f"/api/v1/courses/{owner_course['courseId']}/progress",
        headers=AUTH_HEADERS,
        json_body={
            "handoutVersionId": owner_course["handoutVersionId"],
            "lastHandoutBlockId": owner_course["blockId"],
            "lastDocResourceId": owner_course["resourceId"],
            "lastPageNo": 2,
        },
    )
    sync_session = create_session()
    try:
        repo = SqlAlchemyRuntimeRepository(sync_session)
        new_parse_run, _ = repo.create_parse_run(owner_course["courseId"])
        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])
    finally:
        sync_session.close()

    stale_status, stale_body = await request(
        "POST",
        f"/api/v1/courses/{owner_course['courseId']}/progress",
        headers=AUTH_HEADERS,
        json_body={
            "handoutVersionId": owner_course["handoutVersionId"],
            "lastHandoutBlockId": owner_course["blockId"],
            "lastDocResourceId": owner_course["resourceId"],
            "lastPageNo": 3,
        },
    )
    invalid_status, invalid_body = await request(
        "POST",
        f"/api/v1/courses/{owner_course['courseId']}/progress",
        headers=AUTH_HEADERS,
        json_body={
            "handoutVersionId": foreign_course["handoutVersionId"],
            "lastHandoutBlockId": foreign_course["blockId"],
            "lastVideoResourceId": foreign_course["resourceId"],
            "lastDocResourceId": foreign_course["resourceId"],
        },
    )
    read_status, read_body = await request(
        "GET",
        f"/api/v1/courses/{owner_course['courseId']}/progress",
        headers=AUTH_HEADERS,
    )
    print(json.dumps({
        "valid_status": valid_status,
        "valid_progress": valid_body["data"],
        "stale_status": stale_status,
        "stale_error_code": stale_body.get("errorCode"),
        "invalid_status": invalid_status,
        "invalid_error_code": invalid_body.get("errorCode"),
        "read_status": read_status,
        "read_progress": read_body["data"],
        "cross_user_rejected": cross_user_rejected,
    }))

asyncio.run(main())
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'progress-ownership.sqlite3'}"
    env["KNOWLINK_STORAGE_BACKEND"] = "demo"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["valid_status"] == 200
    assert payload["stale_status"] == 400
    assert payload["stale_error_code"] == "progress.invalid_reference"
    assert payload["invalid_status"] == 400
    assert payload["invalid_error_code"] == "progress.invalid_reference"
    assert payload["read_status"] == 200
    assert payload["read_progress"]["handoutVersionId"] is None
    assert payload["read_progress"]["lastHandoutBlockId"] is None
    assert payload["read_progress"]["lastAnchorKey"] is None
    assert payload["read_progress"]["lastDocResourceId"] == payload["valid_progress"]["lastDocResourceId"]
    assert payload["read_progress"]["lastPageNo"] == payload["valid_progress"]["lastPageNo"]
    assert payload["cross_user_rejected"] is True


def test_stale_review_refresh_cannot_supersede_newer_active_run(tmp_path):
    script = """
import json

import sqlalchemy as sa

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.session import create_session, get_engine
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks.reviews import run_review_refresh
from server.tests.test_runtime_wiring_contract import _submit_quiz_with_service

Base.metadata.create_all(get_engine())

session = create_session()
try:
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title="SQL stale review course",
        entry_type="manual_import",
        goal_text="verify stale review publish isolation",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/review.pdf",
            "originalName": "review.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": "sha256:review",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    repo.mark_parse_run_succeeded(parse_run["parseRunId"])
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run["parseRunId"],
        segments=[
            {
                "segmentType": "pdf_page_text",
                "orderNo": 1,
                "textContent": "复习任务来源片段。",
                "plainText": "复习任务来源片段。",
                "pageNo": 3,
            }
        ],
    )
    segment_key = segments[0]["segmentKey"]
    _, _, blocks = repo.create_handout(
        course_id,
        outline={
            "title": "复习目录",
            "summary": "复习目录。",
            "items": [
                {
                    "outlineKey": "section-review",
                    "title": "复习章节",
                    "summary": "复习章节。",
                    "startSec": 0,
                    "endSec": 60,
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "block-review",
                            "title": "复习块",
                            "summary": "复习块。",
                            "startSec": 0,
                            "endSec": 60,
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [segment_key],
                            "topicTags": [],
                        }
                    ],
                }
            ],
        },
    )
    repo.save_handout_block_result(
        blocks[0]["blockId"],
        {
            "title": "复习块",
            "summary": "复习块。",
            "contentMd": "复习任务来源片段。",
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-review",
                    "displayName": "复习知识点",
                    "description": "复习任务来源片段。",
                    "difficultyLevel": "medium",
                    "importanceScore": 90,
                }
            ],
            "citations": [
                {
                    "resourceId": resource["resourceId"],
                    "segmentKey": segment_key,
                    "pageNo": 3,
                    "refLabel": "PDF 第 3 页",
                }
            ],
        },
    )
    quiz, _ = repo.create_quiz(course_id)
    quiz_payload = {
        "quizType": "chapter_review",
        "questions": [
            {
                "questionKey": "q1-review",
                "questionType": "single_choice",
                "stemMd": "哪项正确？",
                "options": ["A", "B", "C", "D"],
                "correctAnswer": "A",
                "explanationMd": "依据复习块。",
                "difficultyLevel": "medium",
                "knowledgePointKey": "kp-review",
                "knowledgePointName": "复习知识点",
                "sourceBlockKey": str(blocks[0]["blockId"]),
                "sourceSegmentKeys": [segment_key],
            }
        ],
    }
    repo.save_quiz_generation_result(
        quiz["quizId"],
        quiz_payload,
        [
            {
                "questionKey": "q1-review",
                "resourceId": resource["resourceId"],
                "segmentId": segments[0]["segmentId"],
                "segmentKey": segment_key,
                "refType": "pdf_page",
                "quoteText": "复习任务来源片段。",
                "pageNo": 3,
                "refLabel": "PDF 第 3 页",
                "sortNo": 1,
            }
        ],
    )
    first_question_id = repo.get_quiz(quiz["quizId"])["questions"][0]["questionId"]
    attempt = _submit_quiz_with_service(
        repo,
        quiz["quizId"],
        question_id=first_question_id,
        selected_option="A",
    )
    old_run_id = attempt["reviewTaskRunId"]
    tables = Base.metadata.tables
    old_task_id = session.execute(
        sa.select(tables["async_tasks"].c.id).where(
            tables["async_tasks"].c.task_type == "review_refresh",
            tables["async_tasks"].c.target_id == old_run_id,
        )
    ).scalar_one()
    new_run = repo.create_review_run(course_id)
    new_run_id = new_run["reviewTaskRunId"]

    current_payload = {
        "tasks": [
            {
                "taskKey": "review-current",
                "taskType": "redo_quiz",
                "priorityScore": 90,
                "reasonText": "当前复习任务。",
                "recommendedMinutes": 10,
                "knowledgePointKey": "kp-review",
                "sourceQuestionKeys": ["q1-review"],
                "sourceBlockKey": str(blocks[0]["blockId"]),
                "sourceSegmentKeys": [segment_key],
                "reviewOrder": 1,
                "recommendedAction": {"type": "redo_quiz", "targetBlockKey": str(blocks[0]["blockId"])},
            }
        ]
    }
    stale_payload = {
        "tasks": [
            {
                "taskKey": "review-stale",
                "taskType": "revisit_block",
                "priorityScore": 80,
                "reasonText": "旧复习任务。",
                "recommendedMinutes": 10,
                "knowledgePointKey": "kp-review",
                "sourceQuestionKeys": ["q1-review"],
                "sourceBlockKey": str(blocks[0]["blockId"]),
                "sourceSegmentKeys": [segment_key],
                "reviewOrder": 1,
                "recommendedAction": {"type": "revisit_block", "targetBlockKey": str(blocks[0]["blockId"])},
            }
        ]
    }
    refs = [
        {
            "taskKey": "review-current",
            "resourceId": resource["resourceId"],
            "segmentId": segments[0]["segmentId"],
            "segmentKey": segment_key,
            "refType": "pdf_page",
            "quoteText": "复习任务来源片段。",
            "pageNo": 3,
            "refLabel": "PDF 第 3 页",
            "sortNo": 1,
        }
    ]
    repo.save_review_task_run_result(new_run_id, current_payload, refs)
    _ = stale_payload
    stale_result = run_review_refresh(
        {
            "taskId": old_task_id,
            "courseId": course_id,
            "reviewTaskRunId": old_run_id,
        },
    )
    listed = repo.list_review_tasks(course_id)

    statuses = [
        dict(row)
        for row in session.execute(
            sa.select(
                tables["review_tasks"].c.task_key,
                tables["review_tasks"].c.status,
                tables["review_tasks"].c.review_task_run_id,
            ).order_by(tables["review_tasks"].c.id)
        ).mappings().all()
    ]
    old_status = session.execute(
        sa.select(tables["review_task_runs"].c.status).where(tables["review_task_runs"].c.id == old_run_id)
    ).scalar_one()
    old_task_status = session.execute(
        sa.select(tables["async_tasks"].c.status).where(tables["async_tasks"].c.id == old_task_id)
    ).scalar_one()

    failed_old_run = repo.create_review_run(course_id)
    failed_old_run_id = failed_old_run["reviewTaskRunId"]
    failed_old_task_id = session.execute(
        sa.select(tables["async_tasks"].c.id).where(
            tables["async_tasks"].c.task_type == "review_refresh",
            tables["async_tasks"].c.target_id == failed_old_run_id,
        )
    ).scalar_one()
    failed_new_run = repo.create_review_run(course_id)
    failed_new_run_id = failed_new_run["reviewTaskRunId"]
    session.execute(
        sa.update(tables["review_task_runs"]).where(tables["review_task_runs"].c.id == failed_new_run_id).values(
            status="failed",
            error_code="review.refresh_failed",
            error_message="forced failure for late-save test",
        )
    )
    session.commit()
    failed_newer_result = run_review_refresh(
        {
            "taskId": failed_old_task_id,
            "courseId": course_id,
            "reviewTaskRunId": failed_old_run_id,
        },
    )
    failed_old_status = session.execute(
        sa.select(tables["review_task_runs"].c.status).where(tables["review_task_runs"].c.id == failed_old_run_id)
    ).scalar_one()
    failed_old_task_status = session.execute(
        sa.select(tables["async_tasks"].c.status).where(tables["async_tasks"].c.id == failed_old_task_id)
    ).scalar_one()
    failed_old_task_count = session.execute(
        sa.select(sa.func.count()).select_from(tables["review_tasks"]).where(
            tables["review_tasks"].c.review_task_run_id == failed_old_run_id,
        )
    ).scalar_one()
    print(json.dumps({
        "stale_result": stale_result,
        "listed_keys": [item["reviewTaskId"] for item in listed],
        "listed_count": len(listed),
        "statuses": statuses,
        "old_status": old_status,
        "old_task_status": old_task_status,
        "new_run_id": new_run_id,
        "failed_newer_result": failed_newer_result,
        "failed_old_status": failed_old_status,
        "failed_old_task_status": failed_old_task_status,
        "failed_old_task_count": failed_old_task_count,
    }))
finally:
    session.close()
"""
    env = os.environ.copy()
    env["KNOWLINK_RUNTIME_REPOSITORY_BACKEND"] = "sql"
    env["KNOWLINK_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'stale-review.sqlite3'}"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)

    assert payload["stale_result"]["status"] == "skipped"
    assert payload["listed_count"] == 1
    assert payload["old_status"] == "skipped"
    assert payload["old_task_status"] == "skipped"
    assert payload["failed_newer_result"]["status"] == "skipped"
    assert payload["failed_old_status"] == "skipped"
    assert payload["failed_old_task_status"] == "skipped"
    assert payload["failed_old_task_count"] == 0
    assert payload["statuses"] == [
        {
            "task_key": "review-current",
            "status": "pending",
            "review_task_run_id": payload["new_run_id"],
        }
    ]


def test_domain_services_do_not_import_worker_or_dramatiq_directly():
    service_dir = ROOT / "server/domain/services"
    forbidden_tokens = ("server.tasks", "dramatiq")

    violations: list[str] = []
    for path in sorted(service_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if f"import {token}" in text or f"from {token}" in text:
                violations.append(f"{path.relative_to(ROOT)} imports {token}")

    assert violations == []


def test_parse_start_idempotently_returns_root_parse_task_and_parse_run_entity():
    course_id, _ = create_manual_course(
        idempotency_key="runtime-contract-parse-course",
        title="Week 2 解析根任务课",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key="runtime-contract-parse-upload",
        suffix="runtime-contract-parse",
    )

    first_status, first = _post_parse_start(course_id, "runtime-contract-parse-start")
    second_status, second = _post_parse_start(course_id, "runtime-contract-parse-start")

    assert first_status == 200
    assert second_status == 200
    assert first["data"] == second["data"]

    trigger = first["data"]
    assert isinstance(trigger["taskId"], int)
    assert trigger["taskId"] > 0
    assert trigger["status"] == "queued"
    assert trigger["nextAction"] == "poll"
    assert trigger["entity"]["type"] == "parse_run"
    assert isinstance(trigger["entity"]["id"], int)

    parse_status, parse_run = asyncio.run(
        request(
            "GET",
            f"/api/v1/parse-runs/{trigger['entity']['id']}",
            headers=AUTH_HEADERS,
        )
    )
    assert parse_status == 200
    assert parse_run["data"]["parseRunId"] == trigger["entity"]["id"]
    assert parse_run["data"]["courseId"] == course_id
    assert parse_run["data"]["status"] in PIPELINE_STATUS_VALUES | {"canceled", "superseded"}
    assert 0 <= parse_run["data"]["progressPct"] <= 100


def test_pipeline_status_uses_week2_fixed_steps_and_status_enums_after_parse():
    course_id, _ = create_manual_course(
        idempotency_key="runtime-contract-pipeline-course",
        title="Week 2 五步流水线课",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key="runtime-contract-pipeline-upload",
        suffix="runtime-contract-pipeline",
    )
    parse_status, _ = _post_parse_start(course_id, "runtime-contract-pipeline-start")
    assert parse_status == 200

    status, body = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/pipeline-status",
            headers=AUTH_HEADERS,
        )
    )
    assert status == 200

    data = body["data"]
    assert data["courseStatus"]["pipelineStatus"] in PIPELINE_STATUS_VALUES
    assert 0 <= data["progressPct"] <= 100
    assert [step["code"] for step in data["steps"]] == WEEK2_PIPELINE_STEPS
    assert {step["status"] for step in data["steps"]} <= STEP_STATUS_VALUES
    for step in data["steps"]:
        assert step["label"]
        assert "pending" not in step["status"]


@dataclass
class _TaskBackedPipelineRepo:
    expected_pipeline_status: str
    step_statuses: dict[str, str]

    def get_course(self, course_id: int) -> dict[str, Any]:
        return {
            "courseId": course_id,
            "lifecycleStatus": "resource_ready",
            "pipelineStage": "parse",
            "pipelineStatus": "idle",
        }

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return [{"resourceId": 501, "resourceType": "pdf"}]

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        raise AssertionError("aggregation tests should not create parse runs")

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return None

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any]:
        return {"parseRunId": 9001, "courseId": course_id, "status": "running", "progressPct": 40}

    def run_idempotent(self, action: str, key: str | None, factory):
        return factory()

    def _async_tasks(self) -> list[dict[str, Any]]:
        tasks = [
            {
                "taskId": 7001,
                "id": 7001,
                "courseId": 101,
                "course_id": 101,
                "parseRunId": 9001,
                "parse_run_id": 9001,
                "taskType": "parse_pipeline",
                "task_type": "parse_pipeline",
                "status": self.expected_pipeline_status,
                "parentTaskId": None,
                "parent_task_id": None,
                "targetType": "parse_run",
                "target_type": "parse_run",
                "targetId": 9001,
                "target_id": 9001,
                "stepCode": None,
                "step_code": None,
                "progressPct": 100
                if self.expected_pipeline_status in {"succeeded", "partial_success"}
                else 40,
                "progress_pct": 100
                if self.expected_pipeline_status in {"succeeded", "partial_success"}
                else 40,
            }
        ]
        task_types = {
            "resource_validate": "resource_validate",
            "caption_extract": "asr",
            "document_parse": "doc_parse",
            "knowledge_extract": "knowledge_extract",
            "vectorize": "embed",
        }
        for index, code in enumerate(WEEK2_PIPELINE_STEPS, start=1):
            status = self.step_statuses[code]
            tasks.append(
                {
                    "taskId": 7001 + index,
                    "id": 7001 + index,
                    "courseId": 101,
                    "course_id": 101,
                    "parseRunId": 9001,
                    "parse_run_id": 9001,
                    "taskType": task_types[code],
                    "task_type": task_types[code],
                    "status": status,
                    "parentTaskId": 7001,
                    "parent_task_id": 7001,
                    "targetType": "parse_run",
                    "target_type": "parse_run",
                    "targetId": 9001,
                    "target_id": 9001,
                    "stepCode": code,
                    "step_code": code,
                    "progressPct": 100 if status in {"succeeded", "skipped", "partial_success"} else 50,
                    "progress_pct": 100 if status in {"succeeded", "skipped", "partial_success"} else 50,
                    "resultJson": {"nonBlockingFailure": status == "partial_success"},
                    "result_json": {"non_blocking_failure": status == "partial_success"},
                    "errorCode": "demo.failure" if status == "failed" else None,
                    "error_code": "demo.failure" if status == "failed" else None,
                    "errorMessage": "contract scenario" if status == "failed" else None,
                    "error_message": "contract scenario" if status == "failed" else None,
                }
            )
        return tasks

    def list_async_tasks(self, *, course_id: int | None = None, parse_run_id: int | None = None):
        return self._async_tasks()

    def list_async_tasks_for_course(self, course_id: int):
        return self._async_tasks()

    def list_tasks_for_parse_run(self, parse_run_id: int):
        return self._async_tasks()

    def list_pipeline_steps(self, course_id: int) -> list[dict[str, Any]]:
        return [
            {
                "code": code,
                "label": {
                    "resource_validate": "资源校验",
                    "caption_extract": "字幕提取",
                    "document_parse": "文档解析",
                    "knowledge_extract": "目录抽取",
                    "vectorize": "向量化",
                }[code],
                "status": self.step_statuses[code],
                "progressPct": 100 if self.step_statuses[code] in {"succeeded", "skipped"} else 50,
                "message": "contract scenario",
                "failedResourceIds": [501] if self.step_statuses[code] == "failed" else [],
            }
            for code in WEEK2_PIPELINE_STEPS
        ]

    def aggregate_pipeline_status(self, course_id: int) -> dict[str, Any]:
        return {
            "pipelineStatus": self.expected_pipeline_status,
            "progressPct": 100 if self.expected_pipeline_status in {"succeeded", "partial_success"} else 40,
        }


class _NoopTaskDispatcher:
    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        raise AssertionError("status aggregation should not enqueue parse tasks")


class _CommitAwareParseStartRepo:
    def __init__(self) -> None:
        self.course = {
            "courseId": 201,
            "lifecycleStatus": "resource_ready",
            "pipelineStage": "idle",
            "pipelineStatus": "idle",
        }
        self.resources = [{"resourceId": 501, "resourceType": "pdf"}]
        self.parse_runs: dict[int, dict[str, Any]] = {}
        self.tasks: dict[int, dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str], dict[str, object]] = {}
        self.next_parse_run_id = 9000
        self.next_task_id = 7000
        self.in_factory = False
        self.committed = False

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.resources

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        self.next_parse_run_id += 1
        parse_run = {
            "parseRunId": self.next_parse_run_id,
            "courseId": course_id,
            "status": "queued",
            "progressPct": 0,
        }
        self.parse_runs[self.next_parse_run_id] = parse_run
        return parse_run, {}

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return self.parse_runs.get(parse_run_id)

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        if not self.parse_runs:
            return None
        return self.parse_runs[max(self.parse_runs)]

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        self.in_factory = True
        value = factory()
        self.in_factory = False
        self.committed = True
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

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
        self.next_task_id += 1
        task = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": parse_run_id,
            "taskType": task_type,
            "status": status,
            "progressPct": progress_pct,
            "payloadJson": payload_json or {},
            "parentTaskId": parent_task_id,
            "targetType": target_type,
            "targetId": target_id,
            "stepCode": step_code,
        }
        self.tasks[self.next_task_id] = task
        return task

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            task
            for task in self.tasks.values()
            if task["courseId"] == course_id
            and (parse_run_id is None or task["parseRunId"] == parse_run_id)
        ]

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        payload_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
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
        return task


class _CommitAwareDispatcher:
    def __init__(self, repo: _CommitAwareParseStartRepo) -> None:
        self.repo = repo
        self.calls: list[dict[str, Any]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        assert self.repo.in_factory is False
        assert self.repo.committed is True
        self.calls.append({"taskId": task_id, "payload": payload})


def test_parse_start_enqueues_after_idempotent_commit_and_not_on_duplicate_key():
    repo = _CommitAwareParseStartRepo()
    dispatcher = _CommitAwareDispatcher(repo)
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=dispatcher,
        idempotency=repo,
    )

    first = service.start_parse(course_id=201, idempotency_key="commit-aware-parse-start")
    second = service.start_parse(course_id=201, idempotency_key="commit-aware-parse-start")

    assert first == second
    assert dispatcher.calls == [
        {
            "taskId": first["taskId"],
            "payload": {
                "courseId": 201,
                "parseRunId": first["entity"]["id"],
                "resourceTypes": ["pdf"],
            },
        }
    ]


def test_pipeline_status_service_reflects_week2_aggregation_semantics():
    repo = _TaskBackedPipelineRepo(
        expected_pipeline_status="partial_success",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "skipped",
            "document_parse": "succeeded",
            "knowledge_extract": "succeeded",
            "vectorize": "partial_success",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopTaskDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=101)

    assert data["courseStatus"]["pipelineStatus"] == "partial_success"
    assert data["progressPct"] == 100
    assert [step["code"] for step in data["steps"]] == WEEK2_PIPELINE_STEPS
    assert [step["status"] for step in data["steps"]] == [
        "succeeded",
        "skipped",
        "succeeded",
        "succeeded",
        "partial_success",
    ]


def test_pipeline_status_child_partial_overrides_succeeded_root_task():
    repo = _TaskBackedPipelineRepo(
        expected_pipeline_status="succeeded",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "skipped",
            "document_parse": "succeeded",
            "knowledge_extract": "succeeded",
            "vectorize": "partial_success",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopTaskDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=101)

    assert data["courseStatus"]["pipelineStatus"] == "partial_success"


def test_pipeline_status_service_can_surface_all_step_status_values():
    repo = _TaskBackedPipelineRepo(
        expected_pipeline_status="running",
        step_statuses={
            "resource_validate": "succeeded",
            "caption_extract": "running",
            "document_parse": "failed",
            "knowledge_extract": "queued",
            "vectorize": "partial_success",
        },
    )
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=_NoopTaskDispatcher(),
        idempotency=repo,
    )

    data = service.get_pipeline_status(course_id=102)
    statuses = {step["status"] for step in data["steps"]}

    assert data["courseStatus"]["pipelineStatus"] == "running"
    assert statuses == {"succeeded", "running", "failed", "queued", "partial_success"}
