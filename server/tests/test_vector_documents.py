from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.infra.db.base import Base
from server.infra.db.models import Course, HandoutBlock, HandoutVersion, ParseRun, VectorDocument
from server.tasks.handouts import _replace_handout_block_vector
from server.tasks.vector_backfill import rebuild_vector_documents


def test_vector_document_exposes_hybrid_qa_embedding_fields():
    columns = VectorDocument.__table__.c

    assert VectorDocument.EMBEDDING_DIM == 1536

    for column_name in (
        "embedding",
        "embedding_vector",
        "embedding_model",
        "embedding_dim",
        "embedding_status",
        "embedding_error",
        "search_text",
    ):
        assert column_name in columns

    assert columns["embedding_status"].default.arg == "pending"
    assert columns["embedding_status"].server_default.arg == "pending"
    assert columns["search_text"].default.arg == ""
    assert columns["search_text"].server_default.arg == ""


def test_vector_document_sqlite_create_all_supports_vector_fallback():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def test_handout_block_vector_replace_uses_active_scope_and_pending_search_text():
    session_factory = _sqlite_session_factory()
    session = session_factory()
    try:
        course = Course(user_id=1, title="Vector course", entry_type="manual_import")
        session.add(course)
        session.flush()
        parse_run = ParseRun(course_id=course.id, status="succeeded")
        session.add(parse_run)
        session.flush()
        version = HandoutVersion(
            course_id=course.id,
            source_parse_run_id=parse_run.id,
            title="Active handout",
            summary="active",
            status="outline_ready",
            outline_status="ready",
        )
        other_version = HandoutVersion(
            course_id=course.id,
            source_parse_run_id=parse_run.id,
            title="Other handout",
            summary="other",
            status="outline_ready",
            outline_status="ready",
        )
        session.add_all([version, other_version])
        session.flush()
        block = HandoutBlock(
            handout_version_id=version.id,
            outline_key="b1",
            title="Superkey 定义",
            summary="candidate key",
            status="ready",
            content_md="Superkey uniquely identifies tuples.",
            sort_no=1,
            source_segment_keys_json=["segment-1"],
            knowledge_points_json=[{"knowledgePointKey": "kp-superkey"}],
            citations_json=[],
        )
        session.add(block)
        session.flush()
        session.add(
            VectorDocument(
                course_id=course.id,
                parse_run_id=parse_run.id,
                handout_version_id=other_version.id,
                owner_type="handout_block",
                owner_id=block.id,
                content_text="other version must remain",
                metadata_json={"handoutVersionId": other_version.id},
                embedding_status="pending",
                search_text="other version must remain",
            )
        )
        session.commit()

        _replace_handout_block_vector(
            session,
            {"blockId": block.id},
            course=course,
            version=version,
        )
        session.commit()

        rows = session.query(VectorDocument).order_by(VectorDocument.handout_version_id.asc()).all()
        assert len(rows) == 2
        active_row = next(row for row in rows if row.handout_version_id == version.id)
        other_row = next(row for row in rows if row.handout_version_id == other_version.id)
        assert other_row.content_text == "other version must remain"
        assert active_row.embedding_status == "pending"
        assert active_row.embedding is None
        assert active_row.embedding_vector is None
        assert active_row.embedding_model is None
        assert active_row.embedding_dim is None
        assert active_row.embedding_error is None
        assert "superkey" in active_row.search_text
        assert "candidate" in active_row.search_text
        assert "kp-superkey" in active_row.search_text
    finally:
        session.close()
        session.bind.dispose()


def test_handout_block_vector_replace_writes_ready_embedding_when_client_is_available():
    session_factory = _sqlite_session_factory()
    session = session_factory()
    try:
        course, version, block = _create_handout_vector_scope(session)

        _replace_handout_block_vector(
            session,
            {"blockId": block.id},
            course=course,
            version=version,
            embedding_client=_FakeEmbeddingClient(),
        )
        session.commit()

        row = session.query(VectorDocument).one()
        assert row.embedding_status == "ready"
        assert row.embedding_model == "fake-embedding"
        assert row.embedding_dim == 1536
        assert row.embedding_vector == [0.01] * 1536
        assert row.embedding == [0.01] * 1536
        assert row.embedding_error is None
    finally:
        session.close()
        session.bind.dispose()


def test_handout_block_vector_replace_records_failed_status_for_wrong_embedding_dimension():
    session_factory = _sqlite_session_factory()
    session = session_factory()
    try:
        course, version, block = _create_handout_vector_scope(session)

        _replace_handout_block_vector(
            session,
            {"blockId": block.id},
            course=course,
            version=version,
            embedding_client=_WrongDimEmbeddingClient(),
        )
        session.commit()

        row = session.query(VectorDocument).one()
        assert row.embedding_status == "failed"
        assert row.embedding_vector is None
        assert row.embedding_dim is None
        assert "expected 1536" in row.embedding_error
    finally:
        session.close()
        session.bind.dispose()


def test_vector_backfill_rebuild_search_text_without_embedding_provider():
    session_factory = _sqlite_session_factory()
    session = session_factory()
    try:
        course = Course(user_id=1, title="Backfill course", entry_type="manual_import")
        session.add(course)
        session.flush()
        session.add(
            VectorDocument(
                course_id=course.id,
                owner_type="segment",
                owner_id=1,
                content_text="Superkey 唯一标识元组",
                metadata_json={"segmentType": "pdf_page_text"},
                embedding_status="ready",
                search_text="",
            )
        )
        session.commit()

        result = rebuild_vector_documents(session=session, rebuild_embeddings=False)

        row = session.query(VectorDocument).one()
        assert result == {"updated": 1, "embeddingBackfill": "skipped"}
        assert row.embedding_status == "pending"
        assert "superkey" in row.search_text
        assert "唯一" in row.search_text
        assert "pdf_page_text" in row.search_text
    finally:
        session.close()
        session.bind.dispose()


def _sqlite_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _create_handout_vector_scope(session):
    course = Course(user_id=1, title="Vector course", entry_type="manual_import")
    session.add(course)
    session.flush()
    parse_run = ParseRun(course_id=course.id, status="succeeded")
    session.add(parse_run)
    session.flush()
    version = HandoutVersion(
        course_id=course.id,
        source_parse_run_id=parse_run.id,
        title="Active handout",
        summary="active",
        status="outline_ready",
        outline_status="ready",
    )
    session.add(version)
    session.flush()
    block = HandoutBlock(
        handout_version_id=version.id,
        outline_key="b1",
        title="Superkey definition",
        summary="candidate key",
        status="ready",
        content_md="Superkey uniquely identifies tuples.",
        sort_no=1,
        source_segment_keys_json=["segment-1"],
        knowledge_points_json=[{"knowledgePointKey": "kp-superkey"}],
        citations_json=[],
    )
    session.add(block)
    session.commit()
    return course, version, block


class _FakeEmbeddingClient:
    model = "fake-embedding"

    def embed_texts(self, sentences):
        return [[0.01] * 1536 for _sentence in sentences]


class _WrongDimEmbeddingClient:
    model = "wrong-dim"

    def embed_texts(self, sentences):
        return [[0.01, 0.02] for _sentence in sentences]
