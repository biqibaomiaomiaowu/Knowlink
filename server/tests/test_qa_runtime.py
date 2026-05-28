from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, Iterator

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models  # noqa: F401
from server.api.deps import get_qa_service
from server.app import app
from server.domain.services import QaService
from server.infra.db.base import Base
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tests.test_api import AUTH_HEADERS, request
from server.tests.test_handout_outline_runtime import (
    _create_course_with_active_video_segments,
    _create_course_with_overlapping_caption_segments,
    _handout_service,
)


def test_sql_qa_message_persists_session_messages_and_assistant_refs_only():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, pdf_segment = _ready_block_with_pdf_ref(repo)
        service = QaService(courses=repo, qa=repo)

        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block_id, question="集合的定义是什么？")
        )

        assert result["answerType"] == "direct_answer"
        assert result["generationMetadata"] == {
            "source": "fallback",
            "reason": "model_unavailable",
            "evidenceTier": "original_evidence",
        }
        assert result["citations"] == [
            {"resourceId": pdf_segment["resourceId"], "refLabel": "PDF 第 1 页", "pageNo": 1}
        ]

        qa_sessions = Base.metadata.tables["qa_sessions"]
        qa_messages = Base.metadata.tables["qa_messages"]
        qa_message_refs = Base.metadata.tables["qa_message_refs"]
        session_row = session.execute(sa.select(qa_sessions)).mappings().one()
        message_rows = session.execute(
            sa.select(qa_messages).order_by(qa_messages.c.id.asc())
        ).mappings().all()
        ref_rows = session.execute(sa.select(qa_message_refs)).mappings().all()

        assert session_row["course_id"] == course_id
        assert session_row["handout_block_id"] == block_id
        assert session_row["message_count"] == 2
        assert [row["role"] for row in message_rows] == ["user", "assistant"]
        assert message_rows[0]["content_text"] == "集合的定义是什么？"
        assert message_rows[1]["answer_type"] == "direct_answer"
        assert len(ref_rows) == 1
        assert ref_rows[0]["qa_message_id"] == message_rows[1]["id"]
        assert ref_rows[0]["segment_id"] == pdf_segment["segmentId"]
        assert ref_rows[0]["ref_type"] == "pdf_page"

        messages = service.get_session_messages(session_id=result["sessionId"])
        assert [item["role"] for item in messages["items"]] == ["user", "assistant"]
        assert messages["items"][1]["generationMetadata"] == result["generationMetadata"]
        assert messages["items"][1]["citations"] == result["citations"]
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_preserves_handout_context_generation_metadata_without_origin_refs():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id = _ready_block_without_origin_refs(repo, session)
        service = QaService(courses=repo, qa=repo)

        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block_id, question="集合的定义是什么？")
        )

        assert result["answerType"] == "direct_answer"
        assert result["citations"] == []
        assert result["generationMetadata"]["evidenceTier"] == "handout_context"
        assert result["generationMetadata"]["handoutContext"]["title"] == "集合的定义"

        messages = service.get_session_messages(session_id=result["sessionId"])
        assistant_message = messages["items"][1]
        assert assistant_message["generationMetadata"] == result["generationMetadata"]
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_uses_video_source_segment_keys_before_handout_context_without_citations():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, segment_keys = _create_course_with_overlapping_caption_segments(repo)
        course_segments = Base.metadata.tables["course_segments"]
        first_segment_id = int(segment_keys[0].removeprefix("segment-"))
        session.execute(
            sa.update(course_segments)
            .where(course_segments.c.id == first_segment_id)
            .values(text_content="集合的定义是什么？集合是确定对象组成的整体。")
        )
        session.commit()

        handout_service = _handout_service(repo)
        handout_service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        source_ref = _source_video_ref(session, block)
        repo.save_handout_block_result(
            block["blockId"],
            {
                "title": "集合的定义",
                "summary": "集合定义说明。",
                "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
                "sourceSegmentKeys": block["sourceSegmentKeys"],
                "knowledgePoints": [{"knowledgePointKey": "kp-set", "displayName": "集合"}],
                "citations": [],
            },
        )
        service = QaService(courses=repo, qa=repo)

        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block["blockId"], question="集合的定义是什么？")
        )

        assert result["answerType"] == "direct_answer"
        assert result["generationMetadata"]["evidenceTier"] == "original_evidence"
        assert "handoutContext" not in result["generationMetadata"]
        assert result["citations"] == [
            {
                "resourceId": source_ref["resourceId"],
                "refLabel": source_ref["refLabel"],
                "startSec": source_ref["startSec"],
                "endSec": source_ref["endSec"],
            }
        ]
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_insufficient_evidence_returns_empty_citations_and_writes_no_refs():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, _ = _ready_block_with_pdf_ref(repo)
        service = QaService(courses=repo, qa=repo)

        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block_id, question="量子隧穿效应如何证明？")
        )

        qa_message_refs = Base.metadata.tables["qa_message_refs"]
        ref_count = session.scalar(sa.select(sa.func.count()).select_from(qa_message_refs))
        assert result["answerType"] == "insufficient_evidence"
        assert result["citations"] == []
        assert ref_count == 0
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_filters_cross_course_old_parse_run_and_old_handout_version():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, pdf_segment = _ready_block_with_pdf_ref(repo)
        other_course = repo.create_course(
            title="跨课程",
            entry_type="manual_import",
            goal_text="不能被 QA 检索",
            preferred_style="balanced",
        )
        other_resource = repo.create_resource(
            other_course["courseId"],
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{other_course['courseId']}/other.pdf",
                "originalName": "other.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:other",
            },
        )
        other_parse_run, _ = repo.create_parse_run(other_course["courseId"])
        repo.mark_parse_run_succeeded(other_parse_run["parseRunId"])
        repo.create_course_segments(
            course_id=other_course["courseId"],
            resource_id=other_resource["resourceId"],
            parse_run_id=other_parse_run["parseRunId"],
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "集合定义的跨课程资料不能进入当前 QA。",
                    "pageNo": 9,
                }
            ],
        )
        old_parse_resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/old.pdf",
                "originalName": "old.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:old",
            },
        )
        old_parse_run, _ = repo.create_parse_run(course_id)
        old_segment = repo.create_course_segments(
            course_id=course_id,
            resource_id=old_parse_resource["resourceId"],
            parse_run_id=old_parse_run["parseRunId"],
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "集合定义的旧解析资料不能进入当前 QA。",
                    "pageNo": 8,
                }
            ],
        )[0]

        service = QaService(courses=repo, qa=repo)
        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block_id, question="集合的定义是什么？")
        )

        assert result["citations"] == [
            {"resourceId": pdf_segment["resourceId"], "refLabel": "PDF 第 1 页", "pageNo": 1}
        ]
        assert old_segment["resourceId"] not in [item["resourceId"] for item in result["citations"]]
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_uses_active_adjacent_handout_block_vector_content():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_overlapping_caption_segments(repo)
        parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        handout_service = _handout_service(repo)
        handout_service.generate_handout(course_id=course_id, idempotency_key=None)
        blocks = repo.get_latest_handout(course_id)["blocks"]
        current_block, adjacent_block = blocks[0], blocks[1]
        for block in blocks[:2]:
            source_ref = _source_video_ref(session, block)
            repo.save_handout_block_result(
                block["blockId"],
                {
                    "title": block["title"],
                    "summary": block["summary"],
                    "contentMd": "## 普通内容\n\n这里只保留一般说明。",
                    "sourceSegmentKeys": block["sourceSegmentKeys"],
                    "knowledgePoints": [],
                    "citations": [source_ref],
                },
            )
        repo.create_vector_document(
            course_id=course_id,
            parse_run_id=parse_run_id,
            handout_version_id=repo.get_course(course_id)["activeHandoutVersionId"],
            owner_type="handout_block",
            owner_id=adjacent_block["blockId"],
            content_text="向量提示说明集合定义要先判断对象是否确定。",
            metadata_json={"outlineKey": adjacent_block["outlineKey"]},
        )

        result = QaService(courses=repo, qa=repo).create_message(
            payload=_Payload(course_id=course_id, handout_block_id=current_block["blockId"], question="向量提示是什么？")
        )

        assert result["answerType"] == "direct_answer"
        assert "向量提示说明集合定义" in result["answerMd"]
        assert result["citations"] == [
            {
                "resourceId": _source_video_ref(session, adjacent_block)["resourceId"],
                "refLabel": _source_video_ref(session, adjacent_block)["refLabel"],
                "startSec": _source_video_ref(session, adjacent_block)["startSec"],
                "endSec": _source_video_ref(session, adjacent_block)["endSec"],
            }
        ]
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_ignores_non_adjacent_ready_block_even_when_relevant():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_three_blocks(repo)
        parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        handout_service = _handout_service(repo)
        handout_service.generate_handout(course_id=course_id, idempotency_key=None)
        blocks = repo.get_latest_handout(course_id)["blocks"]
        for block in blocks:
            source_ref = _source_video_ref(session, block)
            repo.save_handout_block_result(
                block["blockId"],
                {
                    "title": block["title"],
                    "summary": block["summary"],
                    "contentMd": "## 普通内容",
                    "sourceSegmentKeys": block["sourceSegmentKeys"],
                    "knowledgePoints": [],
                    "citations": [source_ref],
                },
            )
        repo.create_vector_document(
            course_id=course_id,
            parse_run_id=parse_run_id,
            handout_version_id=repo.get_course(course_id)["activeHandoutVersionId"],
            owner_type="handout_block",
            owner_id=blocks[2]["blockId"],
            content_text="远端提示不应被第一个 block 的 QA 命中。",
            metadata_json={"outlineKey": blocks[2]["outlineKey"]},
        )

        result = QaService(courses=repo, qa=repo).create_message(
            payload=_Payload(course_id=course_id, handout_block_id=blocks[0]["blockId"], question="远端提示是什么？")
        )

        assert result["answerType"] == "insufficient_evidence"
        assert result["citations"] == []
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_session_messages_hide_old_handout_version_after_regenerate():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, _ = _ready_block_with_pdf_ref(repo)
        service = QaService(courses=repo, qa=repo)
        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block_id, question="集合的定义是什么？")
        )
        _handout_service(repo).generate_handout(
            course_id=course_id,
            idempotency_key=None,
        )

        assert repo.get_session_messages(result["sessionId"]) is None
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_create_rejects_mismatched_course_active_pointer():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, _ = _ready_block_with_pdf_ref(repo)
        other_course = repo.create_course(
            title="错配课程",
            entry_type="manual_import",
            goal_text="验证 active pointer 边界",
            preferred_style="balanced",
        )
        courses = Base.metadata.tables["courses"]
        session.execute(
            sa.update(courses)
            .where(courses.c.id == other_course["courseId"])
            .values(active_parse_run_id=repo.get_course(course_id)["activeParseRunId"], active_handout_version_id=repo.get_course(course_id)["activeHandoutVersionId"])
        )
        session.commit()

        assert repo.get_qa_context(other_course["courseId"], block_id) is None
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_create_rejects_active_handout_from_old_parse_run():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, _ = _ready_block_with_pdf_ref(repo)
        resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/new-parse.pdf",
                "originalName": "new-parse.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:new-parse",
            },
        )
        new_parse_run, _ = repo.create_parse_run(course_id)
        repo.create_course_segments(
            course_id=course_id,
            resource_id=resource["resourceId"],
            parse_run_id=new_parse_run["parseRunId"],
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "新解析版本。",
                    "pageNo": 1,
                }
            ],
        )
        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])

        assert repo.get_qa_context(course_id, block_id) is None
    finally:
        session.close()
        engine.dispose()


def test_sql_qa_session_messages_hide_old_parse_run_after_reparse():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, _ = _ready_block_with_pdf_ref(repo)
        service = QaService(courses=repo, qa=repo)
        result = service.create_message(
            payload=_Payload(course_id=course_id, handout_block_id=block_id, question="集合的定义是什么？")
        )
        handout_version_id = repo.get_course(course_id)["activeHandoutVersionId"]
        new_parse_run, _ = repo.create_parse_run(course_id)

        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])
        courses = Base.metadata.tables["courses"]
        session.execute(
            sa.update(courses)
            .where(courses.c.id == course_id)
            .values(
                active_parse_run_id=new_parse_run["parseRunId"],
                active_handout_version_id=handout_version_id,
            )
        )
        session.commit()

        assert repo.get_session_messages(result["sessionId"]) is None
    finally:
        session.close()
        engine.dispose()


def test_qa_service_uses_sql_runtime_repository_for_api_wiring():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, block_id, _ = _ready_block_with_pdf_ref(repo)
        service = QaService(courses=repo, qa=repo)

        with _override_qa_service(service):
            status, body = asyncio.run(
                request(
                    "POST",
                    "/api/v1/qa/messages",
                    headers=AUTH_HEADERS,
                    json_body={
                        "courseId": course_id,
                        "handoutBlockId": block_id,
                        "question": "集合的定义是什么？",
                    },
                )
            )

        assert status == 200
        assert body["data"]["sessionId"] > 0
        assert body["data"]["citations"]
    finally:
        session.close()
        engine.dispose()


def _ready_block_with_pdf_ref(repo: SqlAlchemyRuntimeRepository) -> tuple[int, int, dict[str, Any]]:
    course_id, _ = _create_course_with_active_video_segments(repo)
    parse_run_id = repo.get_course(course_id)["activeParseRunId"]
    pdf_resource = repo.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "objectKey": f"raw/1/{course_id}/qa.pdf",
            "originalName": "qa.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 2048,
            "checksum": "sha256:qa-pdf",
        },
    )
    pdf_segment = repo.create_course_segments(
        course_id=course_id,
        resource_id=pdf_resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {
                "segmentType": "pdf_page_text",
                "orderNo": 10,
                "textContent": "集合是确定对象组成的整体，这个定义用于判断元素是否属于集合。",
                "pageNo": 1,
            }
        ],
    )[0]
    handout_service = _handout_service(repo)
    handout_service.generate_handout(course_id=course_id, idempotency_key=None)
    block = repo.get_latest_handout(course_id)["blocks"][0]
    repo.save_handout_block_result(
        block["blockId"],
        {
            "title": "集合",
            "summary": "理解集合定义。",
            "contentMd": "## 集合\n\n集合是确定对象组成的整体。",
            "sourceSegmentKeys": block["sourceSegmentKeys"],
            "knowledgePoints": [{"knowledgePointKey": "kp-set", "displayName": "集合"}],
            "citations": [
                {
                    "resourceId": pdf_segment["resourceId"],
                    "segmentKey": pdf_segment["segmentKey"],
                    "pageNo": 1,
                    "refLabel": "PDF 第 1 页",
                }
            ],
        },
    )
    return course_id, block["blockId"], pdf_segment


def _ready_block_without_origin_refs(repo: SqlAlchemyRuntimeRepository, session) -> tuple[int, int]:
    course_id, _ = _create_course_with_active_video_segments(repo)
    handout_service = _handout_service(repo)
    handout_service.generate_handout(course_id=course_id, idempotency_key=None)
    block = repo.get_latest_handout(course_id)["blocks"][0]
    repo.save_handout_block_result(
        block["blockId"],
        {
            "title": "集合的定义",
            "summary": "集合定义说明。",
            "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
            "sourceSegmentKeys": [],
            "knowledgePoints": [{"knowledgePointKey": "kp-set", "displayName": "集合"}],
            "citations": [],
        },
    )

    handout_blocks = Base.metadata.tables["handout_blocks"]
    session.execute(
        sa.update(handout_blocks)
        .where(handout_blocks.c.id == block["blockId"])
        .values(source_segment_keys_json=[])
    )
    session.commit()
    return course_id, block["blockId"]


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


def _source_video_ref(session, block: dict[str, Any]) -> dict[str, Any]:
    segment_id = int(block["sourceSegmentKeys"][0].removeprefix("segment-"))
    course_segments = Base.metadata.tables["course_segments"]
    row = session.execute(
        sa.select(course_segments).where(course_segments.c.id == segment_id)
    ).mappings().one()
    return {
        "resourceId": row["resource_id"],
        "segmentKey": block["sourceSegmentKeys"][0],
        "startSec": int(row["start_sec"]),
        "endSec": int(row["end_sec"]),
        "refLabel": f"视频 {int(row['start_sec']):02d}s-{int(row['end_sec']):02d}s",
    }


def _create_course_with_three_blocks(repo: SqlAlchemyRuntimeRepository) -> tuple[int, list[str]]:
    course = repo.create_course(
        title="三段讲义课程",
        entry_type="manual_import",
        goal_text="验证 QA 相邻块边界",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "mp4",
            "objectKey": f"raw/1/{course_id}/three.mp4",
            "originalName": "three.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": 2048,
            "checksum": "sha256:three-video",
        },
    )
    parse_run, _ = repo.create_parse_run(course_id)
    parse_run_id = parse_run["parseRunId"]
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
        segments=[
            {"segmentType": "video_caption", "orderNo": 1, "textContent": "第一段。", "startSec": 0, "endSec": 200},
            {"segmentType": "video_caption", "orderNo": 2, "textContent": "第二段。", "startSec": 200, "endSec": 400},
            {"segmentType": "video_caption", "orderNo": 3, "textContent": "第三段。", "startSec": 400, "endSec": 600},
        ],
    )
    return course_id, [segment["segmentKey"] for segment in segments]


@contextmanager
def _override_qa_service(service: QaService) -> Iterator[None]:
    previous_overrides: dict[Any, Any] = dict(app.dependency_overrides)

    async def _service_override() -> QaService:
        return service

    app.dependency_overrides[get_qa_service] = _service_override
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


class _Payload:
    def __init__(self, *, course_id: int, handout_block_id: int, question: str) -> None:
        self.course_id = course_id
        self.handout_block_id = handout_block_id
        self.question = question
