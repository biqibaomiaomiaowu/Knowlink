from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models  # noqa: F401
from server.ai.qa_types import QaScope
from server.infra.db.base import Base
from server.infra.db.models import (
    Course,
    CourseResource,
    CourseSegment,
    HandoutBlock,
    HandoutVersion,
    ParseRun,
)
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


def test_rrf_merge_combines_vector_and_lexical_hits_by_identity_key():
    from server.ai.qa_pgvector_retrieval import rrf_merge_hits
    from server.ai.qa_types import LexicalSearchHit, VectorSearchHit

    vector_hit = VectorSearchHit(
        identity_key="segment:501",
        score=0.91,
        segment_key="video-superkey",
        resource_id=10,
        text="superkey uniquely identifies a tuple.",
    )
    lexical_hit = LexicalSearchHit(
        identity_key="segment:501",
        score=3.0,
        segment_key="video-superkey",
        resource_id=10,
        text="superkey uniquely identifies a tuple.",
    )

    merged = rrf_merge_hits(vector_hits=[vector_hit], lexical_hits=[lexical_hit])

    assert len(merged) == 1
    assert merged[0].identity_key == "segment:501"
    assert merged[0].segment_key == "video-superkey"
    assert merged[0].resource_id == 10
    assert merged[0].vector_rank == 1
    assert merged[0].lexical_rank == 1


def test_current_block_boost_reorders_without_filtering_far_hit():
    from server.ai.qa_pgvector_retrieval import apply_current_block_boost, rrf_merge_hits
    from server.ai.qa_types import VectorSearchHit

    merged = rrf_merge_hits(
        vector_hits=[
            VectorSearchHit(
                identity_key="segment:far",
                score=0.95,
                segment_key="far-superkey",
                resource_id=10,
                handout_block_id=4007,
                text="far block explains superkey.",
            ),
            VectorSearchHit(
                identity_key="segment:current",
                score=0.80,
                segment_key="current-superkey",
                resource_id=10,
                handout_block_id=4002,
                text="current block explains superkey.",
            ),
        ],
        lexical_hits=[],
    )

    boosted = apply_current_block_boost(merged, current_handout_block_id=4002)

    assert [hit.identity_key for hit in boosted] == ["segment:current", "segment:far"]


def test_hybrid_retrieval_dedupes_same_segment_from_vector_and_lexical():
    from server.ai.qa_pgvector_retrieval import build_hybrid_retrieval_candidates
    from server.ai.qa_types import LexicalSearchHit, VectorSearchHit

    candidates = build_hybrid_retrieval_candidates(
        vector_hits=[
            VectorSearchHit(
                identity_key="segment:501",
                score=0.91,
                segment_key="video-superkey",
                resource_id=10,
                text="superkey uniquely identifies a tuple.",
            )
        ],
        lexical_hits=[
            LexicalSearchHit(
                identity_key="segment:501",
                score=4.0,
                segment_key="video-superkey",
                resource_id=10,
                text="superkey uniquely identifies a tuple.",
            )
        ],
        current_handout_block_id=4002,
    )

    assert [candidate.segment_key for candidate in candidates] == ["video-superkey"]


def test_non_original_handout_candidates_never_have_citations():
    from server.ai.qa_pgvector_retrieval import build_hybrid_retrieval_candidates
    from server.ai.qa_types import LexicalSearchHit, VectorSearchHit

    candidates = build_hybrid_retrieval_candidates(
        vector_hits=[
            VectorSearchHit(
                identity_key="handout:4007",
                score=0.88,
                owner_type="handout_block",
                handout_block_id=4007,
                text="A handout paragraph explains superkey.",
            )
        ],
        lexical_hits=[
            LexicalSearchHit(
                identity_key="handout:4007",
                score=5.0,
                owner_type="handout_block",
                handout_block_id=4007,
                text="A handout paragraph explains superkey.",
            )
        ],
        current_handout_block_id=4002,
    )

    assert len(candidates) == 1
    assert candidates[0].owner_type == "handout_block"
    assert candidates[0].citations == []
    assert candidates[0].refs == []


def test_sqlite_lexical_segment_search_filters_to_active_course_parse_segments():
    repo, session, engine = _build_sqlite_repository()
    try:
        course, parse_run, resource = _create_course_parse_and_resource(session)
        stale_parse_run = ParseRun(course_id=course.id, status="succeeded")
        session.add(stale_parse_run)
        session.flush()
        session.add_all(
            [
                CourseSegment(
                    course_id=course.id,
                    resource_id=resource.id,
                    parse_run_id=parse_run.id,
                    segment_type="video_caption",
                    text_content="Alpha beta is the active parse evidence.",
                    plain_text="Alpha beta is the active parse evidence.",
                    order_no=1,
                    token_count=7,
                    start_sec=0,
                    end_sec=30,
                    is_active=True,
                ),
                CourseSegment(
                    course_id=course.id,
                    resource_id=resource.id,
                    parse_run_id=stale_parse_run.id,
                    segment_type="video_caption",
                    text_content="Alpha beta belongs to a stale parse.",
                    plain_text="Alpha beta belongs to a stale parse.",
                    order_no=2,
                    token_count=7,
                    start_sec=30,
                    end_sec=60,
                    is_active=True,
                ),
                CourseSegment(
                    course_id=course.id,
                    resource_id=resource.id,
                    parse_run_id=parse_run.id,
                    segment_type="video_caption",
                    text_content="Alpha beta is inactive.",
                    plain_text="Alpha beta is inactive.",
                    order_no=3,
                    token_count=4,
                    start_sec=60,
                    end_sec=90,
                    is_active=False,
                ),
            ]
        )
        session.commit()

        hits = repo.search_lexical_segments(
            QaScope(course_id=course.id, active_parse_run_id=parse_run.id),
            query="alpha beta",
            limit=5,
        )

        assert [hit.text for hit in hits] == ["Alpha beta is the active parse evidence."]
        assert hits[0].identity_key.startswith("segment:")
        assert hits[0].course_id == course.id
        assert hits[0].parse_run_id == parse_run.id
    finally:
        session.close()
        engine.dispose()


def test_postgresql_lexical_segment_search_uses_search_tsv_with_active_scope_filters():
    session = _PostgresSessionProbe()
    repo = SqlAlchemyRuntimeRepository(session)

    hits = repo.search_lexical_segments(
        QaScope(course_id=101, active_parse_run_id=9001, active_handout_version_id=7001),
        query="superkey",
        limit=5,
    )

    assert hits == []
    statement = session.executed_statements[0]
    assert "vector_documents.search_tsv @@ websearch_to_tsquery" in statement
    assert "vector_documents.course_id" in statement
    assert "vector_documents.parse_run_id" in statement
    assert "vector_documents.owner_type" in statement
    assert "course_segments.is_active IS true" in statement


def test_postgresql_lexical_handout_search_uses_search_tsv_with_active_version_filter():
    session = _PostgresSessionProbe()
    repo = SqlAlchemyRuntimeRepository(session)

    hits = repo.search_lexical_handout_blocks(
        QaScope(course_id=101, active_parse_run_id=9001, active_handout_version_id=7001),
        query="superkey",
        limit=5,
    )

    assert hits == []
    statement = session.executed_statements[0]
    assert "vector_documents.search_tsv @@ websearch_to_tsquery" in statement
    assert "vector_documents.course_id" in statement
    assert "vector_documents.parse_run_id" in statement
    assert "vector_documents.handout_version_id" in statement
    assert "handout_blocks.status" in statement


def test_sqlite_course_wide_original_search_ranks_chinese_and_applies_limit():
    repo, session, engine = _build_sqlite_repository()
    try:
        course, parse_run, resource = _create_course_parse_and_resource(session)
        session.add_all(
            [
                CourseSegment(
                    course_id=course.id,
                    resource_id=resource.id,
                    parse_run_id=parse_run.id,
                    segment_type="video_caption",
                    text_content="超键可以唯一标识一个元组。",
                    plain_text="超键可以唯一标识一个元组。",
                    order_no=1,
                    token_count=8,
                    start_sec=0,
                    end_sec=30,
                    is_active=True,
                ),
                CourseSegment(
                    course_id=course.id,
                    resource_id=resource.id,
                    parse_run_id=parse_run.id,
                    segment_type="video_caption",
                    text_content="候选键和主键是后续内容。",
                    plain_text="候选键和主键是后续内容。",
                    order_no=2,
                    token_count=8,
                    start_sec=30,
                    end_sec=60,
                    is_active=True,
                ),
            ]
        )
        session.commit()

        hits = repo.search_course_wide_original_segments(
            question="超键是什么？",
            course_id=course.id,
            parse_run_id=parse_run.id,
            limit=1,
        )

        assert [hit["textContent"] for hit in hits] == ["超键可以唯一标识一个元组。"]
    finally:
        session.close()
        engine.dispose()


def test_sqlite_lexical_handout_search_filters_ready_blocks_to_active_version():
    repo, session, engine = _build_sqlite_repository()
    try:
        course, parse_run, _resource = _create_course_parse_and_resource(session)
        active_version = HandoutVersion(
            course_id=course.id,
            source_parse_run_id=parse_run.id,
            title="Active handout",
            summary="Active summary",
            status="ready",
            outline_status="ready",
            total_blocks=2,
            ready_blocks=1,
            pending_blocks=1,
        )
        stale_version = HandoutVersion(
            course_id=course.id,
            source_parse_run_id=parse_run.id,
            title="Stale handout",
            summary="Stale summary",
            status="ready",
            outline_status="ready",
            total_blocks=1,
            ready_blocks=1,
            pending_blocks=0,
        )
        session.add_all([active_version, stale_version])
        session.flush()
        course.active_handout_version_id = active_version.id
        session.add_all(
            [
                _handout_block(
                    active_version.id,
                    outline_key="active-ready",
                    title="Alpha ready block",
                    content_md="Alpha beta content from the active ready block.",
                    status="ready",
                    sort_no=1,
                ),
                _handout_block(
                    active_version.id,
                    outline_key="active-pending",
                    title="Alpha pending block",
                    content_md="Alpha beta content from a pending block.",
                    status="pending",
                    sort_no=2,
                ),
                _handout_block(
                    stale_version.id,
                    outline_key="stale-ready",
                    title="Alpha stale block",
                    content_md="Alpha beta content from a stale version.",
                    status="ready",
                    sort_no=1,
                ),
            ]
        )
        session.commit()

        hits = repo.search_lexical_handout_blocks(
            QaScope(
                course_id=course.id,
                active_parse_run_id=parse_run.id,
                active_handout_version_id=active_version.id,
            ),
            query="alpha beta",
            limit=5,
        )

        assert [hit.text for hit in hits] == ["Alpha beta content from the active ready block."]
        assert hits[0].identity_key.startswith("handout:")
        assert hits[0].owner_type == "handout_block"
        assert hits[0].course_id == course.id
        assert hits[0].parse_run_id == parse_run.id
        assert hits[0].handout_version_id == active_version.id
    finally:
        session.close()
        engine.dispose()


def _build_sqlite_repository():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    return SqlAlchemyRuntimeRepository(session), session, engine


def _create_course_parse_and_resource(session) -> tuple[Course, ParseRun, CourseResource]:
    course = Course(
        user_id=1,
        title="QA retrieval course",
        entry_type="manual_import",
        goal_text="Test retrieval filters",
        preferred_style="balanced",
        lifecycle_status="active",
        pipeline_stage="completed",
        pipeline_status="succeeded",
    )
    session.add(course)
    session.flush()
    parse_run = ParseRun(course_id=course.id, status="succeeded")
    resource = CourseResource(
        course_id=course.id,
        resource_type="mp4",
        object_key=f"raw/1/{course.id}/retrieval.mp4",
        original_name="retrieval.mp4",
        mime_type="video/mp4",
        size_bytes=1024,
        checksum=f"sha256:retrieval-{course.id}",
        ingest_status="ready",
        validation_status="valid",
        processing_status="succeeded",
    )
    session.add_all([parse_run, resource])
    session.flush()
    course.active_parse_run_id = parse_run.id
    session.flush()
    return course, parse_run, resource


def _handout_block(
    handout_version_id: int,
    *,
    outline_key: str,
    title: str,
    content_md: str,
    status: str,
    sort_no: int,
) -> HandoutBlock:
    return HandoutBlock(
        handout_version_id=handout_version_id,
        outline_key=outline_key,
        title=title,
        summary=title,
        status=status,
        content_md=content_md,
        sort_no=sort_no,
        source_segment_keys_json=[],
        knowledge_points_json=[],
        citations_json=[],
    )


class _PostgresSessionProbe:
    def __init__(self) -> None:
        self.executed_statements: list[str] = []

    def get_bind(self):
        return _PostgresBind()

    def execute(self, statement, params=None):
        self.executed_statements.append(str(statement))
        return _EmptyResult()


class _PostgresBind:
    dialect = type("Dialect", (), {"name": "postgresql"})()


class _EmptyResult:
    def all(self):
        return []
