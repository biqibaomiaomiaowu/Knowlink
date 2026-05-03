from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models
from server.infra.db.base import Base
from server.infra.db.models import AsyncTask, Course, CourseResource, ParseRun, VectorDocument
from server.tasks.parse_pipeline import run_parse_pipeline


@dataclass(frozen=True)
class _FakeParserResult:
    status: str
    normalized_document: dict[str, Any] | None = None
    issues: list[Any] | None = None


class _FakeEmbeddingClient:
    def embed_texts(self, sentences):
        return [[float(index), float(len(sentence))] for index, sentence in enumerate(sentences, start=1)]


def test_parse_pipeline_runner_writes_segments_and_vector_documents(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")

    def fake_parse(resource_type: str, file_path: str | Path):
        assert resource_type == "pdf"
        assert Path(file_path).name == "lecture.pdf"
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "集合是确定对象组成的整体。",
                        "pageNo": 1,
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=lambda: _FakeEmbeddingClient(),
        base_dir=tmp_path,
    )

    assert result["status"] == "succeeded"
    rows = session.execute(sa.select(Base.metadata.tables["course_segments"])).mappings().all()
    assert len(rows) == 1
    assert rows[0]["segment_type"] == "pdf_page_text"
    vectors = session.scalars(sa.select(VectorDocument)).all()
    assert len(vectors) == 1
    assert vectors[0].owner_type == "segment"
    assert vectors[0].embedding == [1.0, 13.0]
    assert session.get(ParseRun, message["parseRunId"]).status == "succeeded"
    assert session.get(AsyncTask, message["taskId"]).status == "succeeded"
    assert _step_statuses(session, message["parseRunId"])["vectorize"] == "succeeded"


def test_parse_pipeline_runner_does_not_fake_vectors_without_embedding_client(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")

    def fake_parse(resource_type: str, file_path: str | Path):
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "函数可以表示变量之间的对应关系。",
                        "pageNo": 1,
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=lambda: None,
        base_dir=tmp_path,
    )

    assert result["status"] == "partial_success"
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 0
    assert session.get(ParseRun, message["parseRunId"]).status == "partial_success"
    assert session.get(AsyncTask, message["taskId"]).status == "partial_success"
    vectorize_task = session.scalar(
        sa.select(AsyncTask).where(AsyncTask.parse_run_id == message["parseRunId"], AsyncTask.step_code == "vectorize")
    )
    assert vectorize_task.status == "failed"
    assert vectorize_task.error_code == "embedding.not_configured"


def test_parse_pipeline_runner_resolves_relative_object_key_from_local_storage_root(
    monkeypatch,
    tmp_path: Path,
):
    storage_root = tmp_path / "storage"
    object_path = storage_root / "raw/1/lecture.pdf"
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(
        session,
        object_path,
        resource_type="pdf",
        object_key="raw/1/lecture.pdf",
    )
    monkeypatch.setenv("KNOWLINK_LOCAL_STORAGE_ROOT", str(storage_root))

    def fake_parse(resource_type: str, file_path: str | Path):
        assert Path(file_path) == object_path
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "相对 objectKey 可以通过本地存储根目录解析。",
                        "pageNo": 1,
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=lambda: _FakeEmbeddingClient(),
        base_dir=tmp_path,
    )

    assert result["status"] == "succeeded"
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 1


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _seed_parse_run(
    session: Session,
    object_path: Path,
    *,
    resource_type: str,
    object_key: str | None = None,
) -> dict[str, int]:
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(b"%PDF-1.4 test")
    course = Course(
        user_id=1,
        title="Worker pipeline course",
        entry_type="manual_import",
        goal_text="verify worker",
        preferred_style="balanced",
        lifecycle_status="resource_ready",
        pipeline_stage="parse",
        pipeline_status="queued",
    )
    session.add(course)
    session.flush()
    resource = CourseResource(
        course_id=course.id,
        resource_type=resource_type,
        object_key=object_key or str(object_path),
        original_name=object_path.name,
        mime_type="application/pdf",
        size_bytes=object_path.stat().st_size,
        checksum="sha256:test",
        ingest_status="ready",
        validation_status="passed",
        processing_status="pending",
        sort_order=0,
    )
    parse_run = ParseRun(course_id=course.id, status="queued", trigger_type="user_action", progress_pct=0)
    session.add_all([resource, parse_run])
    session.flush()
    root_task = AsyncTask(
        course_id=course.id,
        parse_run_id=parse_run.id,
        task_type="parse_pipeline",
        status="queued",
        target_type="parse_run",
        target_id=parse_run.id,
        progress_pct=0,
        payload_json={"courseId": course.id, "parseRunId": parse_run.id, "resourceTypes": [resource_type]},
    )
    session.add(root_task)
    session.flush()
    for step_code, task_type in [
        ("resource_validate", "resource_validate"),
        ("caption_extract", "subtitle_extract"),
        ("document_parse", "doc_parse"),
        ("knowledge_extract", "knowledge_extract"),
        ("vectorize", "embed"),
    ]:
        session.add(
            AsyncTask(
                course_id=course.id,
                parse_run_id=parse_run.id,
                parent_task_id=root_task.id,
                task_type=task_type,
                status="queued",
                progress_pct=0,
                step_code=step_code,
            )
        )
    session.commit()
    return {"taskId": root_task.id, "courseId": course.id, "parseRunId": parse_run.id}


def _step_statuses(session: Session, parse_run_id: int) -> dict[str, str]:
    rows = session.scalars(sa.select(AsyncTask).where(AsyncTask.parse_run_id == parse_run_id)).all()
    return {str(row.step_code): row.status for row in rows if row.step_code}
