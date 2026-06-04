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
from server.infra.db.models import AsyncTask, Course, CourseResource, CourseSegment, HandoutVersion, ParseRun, VectorDocument
from server.tasks.parse_pipeline import run_parse_pipeline


@dataclass(frozen=True)
class _FakeParserResult:
    status: str
    normalized_document: dict[str, Any] | None = None
    issues: list[Any] | None = None


class _FakeEmbeddingClient:
    model = "fake-embedding"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, sentences):
        self.calls.append(list(sentences))
        return [
            [float(index), float(len(sentence)), *([0.0] * (VectorDocument.EMBEDDING_DIM - 2))]
            for index, sentence in enumerate(sentences, start=1)
        ]


class _WrongDimEmbeddingClient:
    model = "wrong-dim"

    def embed_texts(self, sentences):
        return [[1.0, 2.0] for _sentence in sentences]


class _FakeObjectStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.read_calls: list[str] = []

    def read_object_bytes(self, object_key: str) -> bytes:
        self.read_calls.append(object_key)
        return self.objects[object_key]


class _StreamingFakeObjectStorage(_FakeObjectStorage):
    def __init__(self, objects: dict[str, bytes]) -> None:
        super().__init__(objects)
        self.download_calls: list[tuple[str, Path]] = []

    def download_object_to_file(self, object_key: str, destination_path: str | Path) -> None:
        path = Path(destination_path)
        self.download_calls.append((object_key, path))
        path.write_bytes(self.objects[object_key])


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
    assert vectors[0].embedding == vectors[0].embedding_vector
    assert len(vectors[0].embedding_vector) == VectorDocument.EMBEDDING_DIM
    assert vectors[0].embedding_vector[:2] == [1.0, 13.0]
    assert vectors[0].embedding_model == "fake-embedding"
    assert vectors[0].embedding_dim == VectorDocument.EMBEDDING_DIM
    assert vectors[0].embedding_status == "ready"
    assert vectors[0].embedding_error is None
    assert "pdf_page_text" in vectors[0].search_text
    assert "pdf" in vectors[0].search_text
    assert session.get(ParseRun, message["parseRunId"]).status == "succeeded"
    assert session.get(AsyncTask, message["taskId"]).status == "succeeded"
    assert _step_statuses(session, message["parseRunId"])["vectorize"] == "succeeded"


def test_parse_pipeline_marks_vectorization_failed_on_embedding_dimension_mismatch(tmp_path: Path):
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
                        "textContent": "embedding dimension mismatch",
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
        embedding_client_factory=lambda: _WrongDimEmbeddingClient(),
        base_dir=tmp_path,
    )

    assert result["status"] == "partial_success"
    assert result["vectorDocumentCount"] == 0
    assert {"code": "embedding.dimension_mismatch"} in result["issues"]
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 0
    vectorize_task = session.scalar(
        sa.select(AsyncTask).where(AsyncTask.parse_run_id == message["parseRunId"], AsyncTask.step_code == "vectorize")
    )
    assert vectorize_task.status == "failed"
    assert vectorize_task.error_code == "embedding.dimension_mismatch"


def test_parse_pipeline_persists_mp4_visual_segment_fields(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.mp4", resource_type="mp4")

    def fake_parse(resource_type: str, file_path: str | Path):
        assert resource_type == "mp4"
        assert Path(file_path).name == "lecture.mp4"
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "mp4",
                "segments": [
                    {
                        "segmentKey": "mp4-c1",
                        "segmentType": "video_caption",
                        "textContent": "我们看这个方程。",
                        "startSec": 10,
                        "endSec": 20,
                        "orderNo": 1,
                    },
                    {
                        "segmentKey": "mp4-vf-10-formula-1",
                        "segmentType": "formula",
                        "orderNo": 2,
                        "textContent": "x^2 - 5x + 6 = 0",
                        "formulaText": "x^2 - 5x + 6 = 0",
                        "startSec": 10,
                        "endSec": 20,
                        "imageKey": "frames/mp4/lecture/000010.png",
                        "bboxJson": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.1},
                    },
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
    assert result["segmentCount"] == 2
    segments = session.scalars(sa.select(CourseSegment).order_by(CourseSegment.order_no.asc())).all()
    assert len(segments) == 2
    caption_segment = segments[0]
    assert caption_segment.segment_type == "video_caption"
    assert caption_segment.start_sec == 10
    assert caption_segment.end_sec == 20
    assert caption_segment.text_content == "我们看这个方程。"
    formula_segment = segments[1]
    assert formula_segment.segment_type == "formula"
    assert formula_segment.start_sec == 10
    assert formula_segment.end_sec == 20
    assert formula_segment.image_key == "frames/mp4/lecture/000010.png"
    assert formula_segment.formula_text == "x^2 - 5x + 6 = 0"
    assert formula_segment.bbox_json == {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.1}


def test_parse_pipeline_duplicate_completed_message_does_not_append_artifacts(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")
    parse_calls: list[str] = []
    embedding_clients: list[_FakeEmbeddingClient] = []

    def fake_parse(resource_type: str, file_path: str | Path):
        parse_calls.append(resource_type)
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

    def embedding_factory():
        client = _FakeEmbeddingClient()
        embedding_clients.append(client)
        return client

    first_result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=embedding_factory,
        base_dir=tmp_path,
    )
    second_result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=embedding_factory,
        base_dir=tmp_path,
    )

    assert first_result["status"] == "succeeded"
    assert second_result["status"] == "succeeded"
    assert second_result["segmentCount"] == 1
    assert second_result["vectorDocumentCount"] == 1
    assert parse_calls == ["pdf"]
    assert len(embedding_clients) == 1
    assert embedding_clients[0].calls == [["集合是确定对象组成的整体。"]]
    assert session.scalar(sa.select(sa.func.count()).select_from(CourseSegment)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 1


def test_parse_pipeline_redelivery_of_running_parse_run_replaces_partial_artifacts(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")
    resource = session.scalar(sa.select(CourseResource).where(CourseResource.course_id == message["courseId"]))
    assert resource is not None

    root_task = session.get(AsyncTask, message["taskId"])
    parse_run = session.get(ParseRun, message["parseRunId"])
    root_task.status = "running"
    parse_run.status = "running"
    stale_segment = CourseSegment(
        course_id=message["courseId"],
        resource_id=resource.id,
        parse_run_id=message["parseRunId"],
        segment_type="pdf_page_text",
        text_content="崩溃前已经提交的旧片段。",
        plain_text="崩溃前已经提交的旧片段。",
        page_no=1,
        order_no=1,
        token_count=10,
        is_active=True,
    )
    session.add(stale_segment)
    session.flush()
    session.add(
        VectorDocument(
            course_id=message["courseId"],
            parse_run_id=message["parseRunId"],
            owner_type="segment",
            owner_id=stale_segment.id,
            resource_id=resource.id,
            content_text=stale_segment.text_content,
            metadata_json={"segmentKey": f"segment:{stale_segment.id}", "source": "stale"},
            embedding=[0.0, 0.0],
        )
    )
    session.add(
        VectorDocument(
            course_id=message["courseId"],
            parse_run_id=message["parseRunId"],
            handout_version_id=123,
            owner_type="handout_block",
            owner_id=456,
            content_text="同一 parse run 后续生成的讲义向量不能被 parse 重跑清理。",
            metadata_json={"handoutVersionId": 123, "outlineKey": "legacy-block"},
            embedding=None,
        )
    )
    session.commit()

    def fake_parse(resource_type: str, file_path: str | Path):
        assert resource_type == "pdf"
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-redelivery",
                        "segmentType": "pdf_page_text",
                        "textContent": "重投递后重新生成的片段。",
                        "pageNo": 2,
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
    assert result["segmentCount"] == 1
    assert result["vectorDocumentCount"] == 1
    session.expire_all()
    segments = session.scalars(
        sa.select(CourseSegment).where(CourseSegment.parse_run_id == message["parseRunId"])
    ).all()
    segment_vectors = session.scalars(
        sa.select(VectorDocument).where(
            VectorDocument.parse_run_id == message["parseRunId"],
            VectorDocument.owner_type == "segment",
        )
    ).all()
    handout_vectors = session.scalars(
        sa.select(VectorDocument).where(
            VectorDocument.parse_run_id == message["parseRunId"],
            VectorDocument.owner_type == "handout_block",
        )
    ).all()
    assert [segment.text_content for segment in segments] == ["重投递后重新生成的片段。"]
    assert len(segment_vectors) == 1
    assert segment_vectors[0].owner_id == segments[0].id
    assert [vector.content_text for vector in handout_vectors] == [
        "同一 parse run 后续生成的讲义向量不能被 parse 重跑清理。"
    ]
    assert session.get(ParseRun, message["parseRunId"]).status == "succeeded"
    assert session.get(AsyncTask, message["taskId"]).status == "succeeded"


def test_parse_pipeline_rejects_schema_invalid_normalized_document(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")
    embedding_clients: list[_FakeEmbeddingClient] = []

    def fake_parse(resource_type: str, file_path: str | Path):
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "缺少页码的 PDF 片段不能进入持久化。",
                        "orderNo": 1,
                        "unexpected": "schema drift",
                    }
                ],
            },
            issues=[],
        )

    def embedding_factory():
        client = _FakeEmbeddingClient()
        embedding_clients.append(client)
        return client

    result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=embedding_factory,
        base_dir=tmp_path,
    )

    assert result["status"] == "failed"
    assert any(issue["code"] == "parse.schema_invalid" for issue in result["issues"])
    assert session.scalar(sa.select(sa.func.count()).select_from(CourseSegment)) == 0
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 0
    assert embedding_clients == []

    resource = session.scalar(sa.select(CourseResource).where(CourseResource.course_id == message["courseId"]))
    assert resource.processing_status == "failed"
    assert resource.last_error
    assert "schema" in resource.last_error
    assert session.get(ParseRun, message["parseRunId"]).status == "failed"
    root_task = session.get(AsyncTask, message["taskId"])
    assert root_task.status == "failed"
    assert root_task.error_code == "parse.schema_invalid"
    document_task = session.scalar(
        sa.select(AsyncTask).where(AsyncTask.parse_run_id == message["parseRunId"], AsyncTask.step_code == "document_parse")
    )
    assert document_task.status == "failed"
    assert document_task.error_code == "parse.schema_invalid"


def test_parse_pipeline_schema_invalid_mixed_resources_fails_without_vectorizing(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "invalid.pdf", resource_type="pdf")
    _add_course_resource(session, message["courseId"], tmp_path / "valid.pdf", resource_type="pdf", sort_order=1)
    embedding_clients: list[_FakeEmbeddingClient] = []

    def fake_parse(resource_type: str, file_path: str | Path):
        if Path(file_path).name == "invalid.pdf":
            return _FakeParserResult(
                status="succeeded",
                normalized_document={
                    "resourceType": "pdf",
                    "segments": [
                        {
                            "segmentKey": "pdf-invalid",
                            "segmentType": "pdf_page_text",
                            "textContent": "缺少页码的 PDF 片段不能进入向量化。",
                            "orderNo": 1,
                        }
                    ],
                },
                issues=[],
            )
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-valid",
                        "segmentType": "pdf_page_text",
                        "textContent": "另一个资源虽然有效，也不能在 schema invalid 后继续向量化。",
                        "pageNo": 1,
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    def embedding_factory():
        client = _FakeEmbeddingClient()
        embedding_clients.append(client)
        return client

    result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=embedding_factory,
        base_dir=tmp_path,
    )

    assert result["status"] == "failed"
    assert any(issue["code"] == "parse.schema_invalid" for issue in result["issues"])
    assert result["segmentCount"] == 0
    assert session.scalar(sa.select(sa.func.count()).select_from(CourseSegment)) == 0
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 0
    assert embedding_clients == []
    assert session.get(ParseRun, message["parseRunId"]).status == "failed"
    assert session.get(AsyncTask, message["taskId"]).status == "failed"
    document_task = session.scalar(
        sa.select(AsyncTask).where(AsyncTask.parse_run_id == message["parseRunId"], AsyncTask.step_code == "document_parse")
    )
    assert document_task.status == "failed"
    assert document_task.error_code == "parse.schema_invalid"
    resources = {
        resource.original_name: resource
        for resource in session.scalars(
            sa.select(CourseResource).where(CourseResource.course_id == message["courseId"])
        )
    }
    assert resources["invalid.pdf"].processing_status == "failed"
    assert resources["invalid.pdf"].last_parse_run_id is None
    assert resources["valid.pdf"].processing_status == "failed"
    assert resources["valid.pdf"].last_parse_run_id is None


def test_parse_pipeline_retry_after_failed_parse_run_reexecutes_when_root_requeued(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")
    parse_calls: list[str] = []

    def invalid_parse(resource_type: str, file_path: str | Path):
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-invalid",
                        "segmentType": "pdf_page_text",
                        "textContent": "第一次解析失败。",
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    first_result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=invalid_parse,
        embedding_client_factory=lambda: _FakeEmbeddingClient(),
        base_dir=tmp_path,
    )
    assert first_result["status"] == "failed"

    root_task = session.get(AsyncTask, message["taskId"])
    root_task.status = "queued"
    root_task.progress_pct = 0
    root_task.error_code = None
    root_task.error_message = None
    root_task.result_json = None
    session.commit()

    def valid_parse(resource_type: str, file_path: str | Path):
        parse_calls.append(resource_type)
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-valid",
                        "segmentType": "pdf_page_text",
                        "textContent": "重试后解析成功。",
                        "pageNo": 1,
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    second_result = run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=valid_parse,
        embedding_client_factory=lambda: _FakeEmbeddingClient(),
        base_dir=tmp_path,
    )

    assert second_result["status"] == "succeeded"
    assert parse_calls == ["pdf"]
    assert session.scalar(sa.select(sa.func.count()).select_from(CourseSegment)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 1


def test_parse_pipeline_success_clears_stale_active_handout_version(tmp_path: Path):
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(session, tmp_path / "lecture.pdf", resource_type="pdf")
    stale_version = HandoutVersion(
        course_id=message["courseId"],
        source_parse_run_id=message["parseRunId"] + 100,
        title="旧讲义",
        summary="旧解析来源",
        status="ready",
        outline_status="ready",
        total_blocks=0,
        ready_blocks=0,
        pending_blocks=0,
    )
    session.add(stale_version)
    session.flush()
    course = session.get(Course, message["courseId"])
    course.active_handout_version_id = stale_version.id
    session.commit()

    def fake_parse(resource_type: str, file_path: str | Path):
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "新解析版本。",
                        "pageNo": 1,
                        "orderNo": 1,
                    }
                ],
            },
            issues=[],
        )

    run_parse_pipeline(
        message,
        session_factory=session_factory,
        parse_resource_func=fake_parse,
        embedding_client_factory=lambda: None,
        base_dir=tmp_path,
    )

    session.expire_all()
    assert session.get(Course, message["courseId"]).active_handout_version_id is None


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


def test_parse_pipeline_runner_downloads_raw_object_key_from_object_storage(
    monkeypatch,
    tmp_path: Path,
):
    object_key = "raw/1/101/temp/pdf/lecture.pdf"
    missing_local_path = tmp_path / "local-missing" / "lecture.pdf"
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(
        session,
        missing_local_path,
        resource_type="pdf",
        object_key=object_key,
    )
    missing_local_path.unlink()
    storage = _FakeObjectStorage({object_key: b"%PDF-1.4 minio object"})
    monkeypatch.setenv("KNOWLINK_WORKER_CACHE_DIR", str(tmp_path / "worker-cache"))

    def fake_parse(resource_type: str, file_path: str | Path):
        resolved_path = Path(file_path)
        assert resource_type == "pdf"
        assert resolved_path != missing_local_path
        assert resolved_path.is_file()
        assert resolved_path.suffix == ".pdf"
        assert resolved_path.read_bytes() == b"%PDF-1.4 minio object"
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "MinIO 对象会先落到 worker 本地缓存再解析。",
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
        object_storage=storage,
        base_dir=tmp_path,
    )

    assert result["status"] == "succeeded"
    assert storage.read_calls == [object_key]
    assert session.scalar(sa.select(sa.func.count()).select_from(VectorDocument)) == 1


def test_parse_pipeline_runner_streams_raw_object_key_to_worker_cache_when_supported(
    monkeypatch,
    tmp_path: Path,
):
    object_key = "raw/1/101/temp/pdf/streamed.pdf"
    missing_local_path = tmp_path / "local-missing" / "streamed.pdf"
    session_factory = _session_factory()
    session = session_factory()
    message = _seed_parse_run(
        session,
        missing_local_path,
        resource_type="pdf",
        object_key=object_key,
    )
    missing_local_path.unlink()
    storage = _StreamingFakeObjectStorage({object_key: b"%PDF-1.4 streamed object"})
    monkeypatch.setenv("KNOWLINK_WORKER_CACHE_DIR", str(tmp_path / "worker-cache"))

    def fake_parse(resource_type: str, file_path: str | Path):
        resolved_path = Path(file_path)
        assert resource_type == "pdf"
        assert resolved_path.is_file()
        assert resolved_path.read_bytes() == b"%PDF-1.4 streamed object"
        return _FakeParserResult(
            status="succeeded",
            normalized_document={
                "resourceType": "pdf",
                "segments": [
                    {
                        "segmentKey": "pdf-p1",
                        "segmentType": "pdf_page_text",
                        "textContent": "对象存储支持文件下载时不经过整对象内存缓冲。",
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
        object_storage=storage,
        base_dir=tmp_path,
    )

    assert result["status"] == "succeeded"
    assert storage.read_calls == []
    assert len(storage.download_calls) == 1
    assert storage.download_calls[0][0] == object_key
    assert storage.download_calls[0][1].is_file()


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


def _add_course_resource(
    session: Session,
    course_id: int,
    object_path: Path,
    *,
    resource_type: str,
    sort_order: int,
) -> CourseResource:
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(b"%PDF-1.4 test")
    resource = CourseResource(
        course_id=course_id,
        resource_type=resource_type,
        object_key=str(object_path),
        original_name=object_path.name,
        mime_type="application/pdf",
        size_bytes=object_path.stat().st_size,
        checksum=f"sha256:{object_path.name}",
        ingest_status="ready",
        validation_status="passed",
        processing_status="pending",
        sort_order=sort_order,
    )
    session.add(resource)
    session.commit()
    return resource


def _step_statuses(session: Session, parse_run_id: int) -> dict[str, str]:
    rows = session.scalars(sa.select(AsyncTask).where(AsyncTask.parse_run_id == parse_run_id)).all()
    return {str(row.step_code): row.status for row in rows if row.step_code}
