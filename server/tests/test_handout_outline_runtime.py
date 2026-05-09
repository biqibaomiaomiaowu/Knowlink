from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models  # noqa: F401
from server.api.deps import get_handout_service, get_resource_service
from server.app import app
from server.domain.services import HandoutService, ResourceService
from server.infra.db.base import Base
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.infra.storage import ObjectStat
from server.tasks.handouts import run_handout_block_generate, run_handout_generate
from server.tests.test_api import AUTH_HEADERS, request


def test_sql_handout_generate_persists_latest_outline_and_api_read_model():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, segment_keys = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)

        trigger = service.generate_handout(course_id=course_id, idempotency_key=None)
        handout_version_id = trigger["entity"]["id"]
        assert trigger["entity"] == {"type": "handout_version", "id": handout_version_id}

        session.expire_all()
        status = service.get_status(handout_version_id=handout_version_id)
        assert status["status"] == "outline_ready"
        assert status["outlineStatus"] == "ready"
        assert status["readyBlocks"] == 0
        assert status["pendingBlocks"] == 1

        outline = repo.get_latest_outline(course_id)
        assert outline is not None
        assert outline["handoutVersionId"] == handout_version_id
        outline_children = _outline_children(outline)
        assert outline["items"][0]["children"] == outline_children
        assert outline_children[0]["sourceSegmentKeys"] == segment_keys
        assert outline_children[0]["generationStatus"] == "pending"
        assert isinstance(outline_children[0]["blockId"], int)
        blocks = service.get_latest_blocks(course_id=course_id)
        assert blocks["items"][0]["sourceSegmentKeys"] == segment_keys

        with _override_handout_service(service):
            api_status, body = asyncio.run(
                request(
                    "GET",
                    f"/api/v1/courses/{course_id}/handouts/latest/outline",
                    headers=AUTH_HEADERS,
                )
            )

        assert api_status == 200
        assert body["data"]["handoutVersionId"] == handout_version_id
        assert body["data"]["items"][0]["children"][0]["sourceSegmentKeys"] == segment_keys
    finally:
        session.close()
        engine.dispose()


def test_sql_handout_generate_uses_semantic_outline_client_and_document_context():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, segment_keys = _create_course_with_active_video_segments(repo)
        parse_run_id = int(repo.get_course(course_id)["activeParseRunId"])
        pdf_resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/set.pdf",
                "originalName": "set.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:set-pdf",
            },
        )
        repo.create_course_segments(
            course_id=course_id,
            resource_id=pdf_resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "title": "ZF 公理化集合论",
                    "orderNo": 10,
                    "textContent": "补充资料说明 ZF 公理化集合论和文氏图表示。",
                    "pageNo": 3,
                }
            ],
        )
        outline_client = _SemanticOutlineClient()
        service = HandoutService(
            courses=repo,
            handouts=repo,
            idempotency=repo,
            outline_client=outline_client,
        )

        trigger = service.generate_handout(course_id=course_id, idempotency_key=None)
        handout_version_id = trigger["entity"]["id"]

        assert outline_client.document_context is not None
        assert "ZF 公理化集合论" in outline_client.document_context
        assert "文氏图" in outline_client.document_context

        latest = repo.get_latest_handout(course_id)
        assert latest["handoutVersionId"] == handout_version_id
        assert latest["metaJson"] == {"outlineUsedFallback": False, "outlineIssues": []}

        outline = repo.get_latest_outline(course_id)
        child = _outline_children(outline)[0]
        assert outline["items"][0]["title"] == "集合的概念与表示"
        assert child["title"] == "集合论基础"
        assert child["summary"] == "理解集合、元素和属于关系的核心定义。"
        assert child["sourceSegmentKeys"] == segment_keys
        assert isinstance(child["blockId"], int)
    finally:
        session.close()
        engine.dispose()


def test_sql_handout_generate_falls_back_and_records_invalid_outline_issues():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, segment_keys = _create_course_with_active_video_segments(repo)
        service = HandoutService(
            courses=repo,
            handouts=repo,
            idempotency=repo,
            outline_client=_InvalidTimelineOutlineClient(),
        )

        service.generate_handout(course_id=course_id, idempotency_key=None)

        latest = repo.get_latest_handout(course_id)
        assert latest["metaJson"]["outlineUsedFallback"] is True
        assert "outline.time_overlap" in latest["metaJson"]["outlineIssues"]

        outline = repo.get_latest_outline(course_id)
        child = _outline_children(outline)[0]
        assert child["sourceSegmentKeys"] == segment_keys
        assert child["generationStatus"] == "pending"
    finally:
        session.close()
        engine.dispose()


def test_sql_handout_generate_enqueues_root_task_with_contract_payload_only():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        dispatcher = _RecordingHandoutDispatcher()
        service = HandoutService(
            courses=repo,
            handouts=repo,
            idempotency=repo,
            task_dispatcher=dispatcher,
        )

        trigger = service.generate_handout(
            course_id=course_id,
            idempotency_key="handout-root-payload",
        )
        repeat = service.generate_handout(
            course_id=course_id,
            idempotency_key="handout-root-payload",
        )

        handout_version_id = trigger["entity"]["id"]
        assert repeat == trigger
        assert dispatcher.calls == [
            {
                "taskId": trigger["taskId"],
                "payload": {
                    "courseId": course_id,
                    "handoutVersionId": handout_version_id,
                    "sourceParseRunId": repo.get_course(course_id)["activeParseRunId"],
                },
            }
        ]

        blocks = repo.get_latest_handout(course_id)["blocks"]
        assert [block["status"] for block in blocks] == ["pending"]
        assert all(block["contentMd"] is None for block in blocks)
    finally:
        session.close()
        engine.dispose()


def test_handout_generate_worker_finishes_root_task_without_generating_blocks():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        trigger = service.generate_handout(course_id=course_id, idempotency_key=None)
        handout_version_id = trigger["entity"]["id"]

        result = run_handout_generate(
            {
                "taskId": trigger["taskId"],
                "courseId": course_id,
                "handoutVersionId": handout_version_id,
                "sourceParseRunId": repo.get_course(course_id)["activeParseRunId"],
            },
            session_factory=lambda: session,
        )

        assert result["status"] == "outline_ready"
        assert result["readyBlocks"] == 0
        assert result["pendingBlocks"] == 1

        async_tasks = Base.metadata.tables["async_tasks"]
        task_row = session.execute(
            sa.select(async_tasks).where(async_tasks.c.id == trigger["taskId"])
        ).mappings().one()
        assert task_row["status"] == "succeeded"
        assert task_row["result_json"]["handoutVersionId"] == handout_version_id

        blocks = repo.get_latest_handout(course_id)["blocks"]
        assert [block["status"] for block in blocks] == ["pending"]
        assert all(block["contentMd"] is None for block in blocks)
    finally:
        session.close()
        engine.dispose()


def test_handout_generate_worker_rejects_old_parse_run_after_reparse():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        trigger = service.generate_handout(course_id=course_id, idempotency_key=None)
        old_handout_version_id = trigger["entity"]["id"]
        old_parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        new_parse_run, _ = repo.create_parse_run(course_id)
        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])
        courses = Base.metadata.tables["courses"]
        session.execute(
            sa.update(courses)
            .where(courses.c.id == course_id)
            .values(active_handout_version_id=old_handout_version_id)
        )
        session.commit()

        try:
            run_handout_generate(
                {
                    "taskId": trigger["taskId"],
                    "courseId": course_id,
                    "handoutVersionId": old_handout_version_id,
                    "sourceParseRunId": old_parse_run_id,
                },
                session_factory=lambda: session,
            )
        except ValueError as exc:
            assert "active parse run" in str(exc)
        else:
            raise AssertionError("old parse-run handout root task should fail")
    finally:
        session.close()
        engine.dispose()


def test_sql_ready_handout_block_persists_content_and_normalized_refs():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        pdf_resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/block-ref.pdf",
                "originalName": "block-ref.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 2048,
                "checksum": "sha256:block-ref-pdf",
            },
        )
        pdf_segments = repo.create_course_segments(
            course_id=course_id,
            resource_id=pdf_resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "orderNo": 10,
                    "textContent": "PDF 第 2 页解释集合定义。",
                    "pageNo": 2,
                }
            ],
        )
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]

        saved = repo.save_handout_block_result(
            block["blockId"],
            {
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义\n\n集合是确定对象组成的整体。",
                "sourceSegmentKeys": block["sourceSegmentKeys"],
                "knowledgePoints": [{"knowledgePointKey": "kp-set", "displayName": "集合"}],
                "citations": [
                    {
                        "resourceId": pdf_resource["resourceId"],
                        "segmentKey": pdf_segments[0]["segmentKey"],
                        "refLabel": "模型给错页码时以 segment 为准",
                        "pageNo": 99,
                    },
                    {
                        "resourceId": pdf_resource["resourceId"],
                        "segmentKey": pdf_segments[0]["segmentKey"],
                        "pageNo": 2,
                        "startSec": 0,
                        "endSec": 10,
                    },
                ],
            },
        )

        assert saved is not None
        assert saved["status"] == "ready"
        assert saved["contentMd"].startswith("## 集合定义")
        assert saved["knowledgePoints"] == [{"knowledgePointKey": "kp-set", "displayName": "集合"}]
        assert saved["citations"] == [
            {
                "resourceId": pdf_resource["resourceId"],
                "segmentId": pdf_segments[0]["segmentId"],
                "segmentKey": pdf_segments[0]["segmentKey"],
                "refLabel": "模型给错页码时以 segment 为准",
                "pageNo": 2,
            }
        ]

        handout_block_refs = Base.metadata.tables["handout_block_refs"]
        ref_rows = session.execute(
            sa.select(handout_block_refs).where(
                handout_block_refs.c.handout_block_id == block["blockId"]
            )
        ).mappings().all()
        assert len(ref_rows) == 1
        assert ref_rows[0]["resource_id"] == pdf_resource["resourceId"]
        assert ref_rows[0]["segment_id"] == pdf_segments[0]["segmentId"]
        assert ref_rows[0]["ref_type"] == "pdf_page"
        assert ref_rows[0]["page_no"] == 2
        assert ref_rows[0]["sort_no"] == 1

        status = service.get_status(handout_version_id=repo.get_course(course_id)["activeHandoutVersionId"])
        assert status["status"] == "ready"
        assert status["readyBlocks"] == 1
        assert status["pendingBlocks"] == 0
    finally:
        session.close()
        engine.dispose()


def test_sql_ready_handout_block_refs_reject_non_candidate_segments_and_untrusted_source_keys():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/unrelated.pdf",
                "originalName": "unrelated.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 2048,
                "checksum": "sha256:unrelated-pdf",
            },
        )
        segments = repo.create_course_segments(
            course_id=course_id,
            resource_id=resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "orderNo": 20,
                    "textContent": "完全无关的跨块材料，不应成为当前 block 引用。",
                    "pageNo": 8,
                }
            ],
        )
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]

        saved = repo.save_handout_block_result(
            block["blockId"],
            {
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义",
                "sourceSegmentKeys": [segments[0]["segmentKey"]],
                "knowledgePoints": [],
                "citations": [
                    {
                        "resourceId": resource["resourceId"],
                        "segmentKey": segments[0]["segmentKey"],
                        "pageNo": 8,
                    }
                ],
            },
        )

        assert saved is not None
        assert saved["sourceSegmentKeys"] == block["sourceSegmentKeys"]
        assert saved["citations"] == []
        assert repo.get_latest_handout(course_id)["blocks"][0]["sourceSegmentKeys"] == block["sourceSegmentKeys"]
    finally:
        session.close()
        engine.dispose()


def test_sql_ready_handout_block_result_rejects_old_version_block():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        old_block_id = repo.get_latest_handout(course_id)["blocks"][0]["blockId"]
        service.generate_handout(course_id=course_id, idempotency_key=None)

        assert repo.save_handout_block_result(
            old_block_id,
            {
                "title": "旧版本",
                "summary": "不应写入",
                "contentMd": "## old",
                "citations": [],
            },
        ) is None
    finally:
        session.close()
        engine.dispose()


def test_latest_handout_requires_active_version_not_latest_created_fallback():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)

        courses = Base.metadata.tables["courses"]
        session.execute(
            sa.update(courses)
            .where(courses.c.id == course_id)
            .values(active_handout_version_id=None)
        )
        session.commit()

        assert repo.get_latest_handout(course_id) is None
    finally:
        session.close()
        engine.dispose()


def test_active_handout_reads_reject_stale_parse_run_pointer():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        handout_version_id = repo.get_course(course_id)["activeHandoutVersionId"]
        block_id = repo.get_latest_handout(course_id)["blocks"][0]["blockId"]
        new_parse_run, _ = repo.create_parse_run(course_id)

        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])
        assert repo.get_course(course_id)["activeHandoutVersionId"] is None

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

        assert repo.get_handout(handout_version_id) is None
        assert repo.get_latest_handout(course_id) is None
        assert repo.get_latest_outline(course_id) is None
        assert repo.get_handout_block_status(block_id) is None
        assert repo.get_block_jump_target(block_id) is None
        assert repo.get_current_handout_block(course_id, current_sec=10) is None
    finally:
        session.close()
        engine.dispose()


def test_handout_block_generate_is_idempotent_and_does_not_duplicate_generating_task():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        dispatcher = _RecordingHandoutDispatcher()
        service = HandoutService(
            courses=repo,
            handouts=repo,
            idempotency=repo,
            task_dispatcher=dispatcher,
        )
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block_id = repo.get_latest_handout(course_id)["blocks"][0]["blockId"]

        first = service.generate_block(block_id=block_id, idempotency_key="block-generate")
        repeat = service.generate_block(block_id=block_id, idempotency_key="block-generate")
        second_key = service.generate_block(block_id=block_id, idempotency_key="block-generate-2")

        assert first == repeat == second_key
        assert first["entity"] == {"type": "handout_block", "id": block_id}
        assert dispatcher.block_calls == [
            {
                "taskId": first["taskId"],
                "payload": {
                    "courseId": course_id,
                    "handoutVersionId": repo.get_course(course_id)["activeHandoutVersionId"],
                    "handoutBlockId": block_id,
                    "sourceParseRunId": repo.get_course(course_id)["activeParseRunId"],
                },
            }
        ]
        assert service.get_block_status(block_id=block_id)["status"] == "generating"
    finally:
        session.close()
        engine.dispose()


def test_ready_handout_block_generate_returns_status_without_requeue():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(
            courses=repo,
            handouts=repo,
            idempotency=repo,
            task_dispatcher=_RecordingHandoutDispatcher(),
        )
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        repo.save_handout_block_result(
            block["blockId"],
            {
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义",
                "sourceSegmentKeys": block["sourceSegmentKeys"],
                "knowledgePoints": [],
                "citations": [],
            },
        )

        result = service.generate_block(block_id=block["blockId"], idempotency_key="ready-block")

        assert result == {
            "blockId": block["blockId"],
            "outlineKey": block["outlineKey"],
            "status": "ready",
            "startSec": block["startSec"],
            "endSec": block["endSec"],
        }
    finally:
        session.close()
        engine.dispose()


def test_current_block_matches_boundaries_and_prefetches_next_pending_block():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_overlapping_caption_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        blocks = repo.get_latest_handout(course_id)["blocks"]

        first = service.get_current_block(course_id=course_id, current_sec=240)
        boundary = service.get_current_block(course_id=course_id, current_sec=260)
        last_end = service.get_current_block(course_id=course_id, current_sec=320)

        assert first["blockId"] == blocks[0]["blockId"]
        assert first["prefetchBlockId"] == blocks[1]["blockId"]
        assert boundary["blockId"] == blocks[1]["blockId"]
        assert last_end["blockId"] == blocks[1]["blockId"]
    finally:
        session.close()
        engine.dispose()


def test_jump_target_prefers_handout_block_ref_doc_locator_and_keeps_video_time():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        pdf_resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/jump.pdf",
                "originalName": "jump.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 2048,
                "checksum": "sha256:jump-pdf",
            },
        )
        pdf_segment = repo.create_course_segments(
            course_id=course_id,
            resource_id=pdf_resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[{"segmentType": "pdf_page_text", "orderNo": 10, "textContent": "集合定义补充。", "pageNo": 4}],
        )[0]
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        repo.save_handout_block_result(
            block["blockId"],
            {
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义",
                "sourceSegmentKeys": block["sourceSegmentKeys"],
                "knowledgePoints": [],
                "citations": [
                    {
                        "resourceId": pdf_resource["resourceId"],
                        "segmentKey": pdf_segment["segmentKey"],
                        "pageNo": 4,
                    }
                ],
            },
        )

        jump = service.get_jump_target(block_id=block["blockId"])

        assert jump["videoResourceId"] is not None
        assert jump["startSec"] == block["startSec"]
        assert jump["endSec"] == block["endSec"]
        assert jump["docResourceId"] == pdf_resource["resourceId"]
        assert jump["pageNo"] == 4
    finally:
        session.close()
        engine.dispose()


def test_ready_handout_jump_target_video_resource_can_resolve_playback_url():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        handout_service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        handout_service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        saved = repo.save_handout_block_result(
            block["blockId"],
            {
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义",
                "sourceSegmentKeys": block["sourceSegmentKeys"],
                "knowledgePoints": [],
                "citations": [],
            },
        )
        assert saved is not None
        assert saved["status"] == "ready"
        resource_service = ResourceService(
            courses=repo,
            resources=repo,
            idempotency=repo,
            storage=_PlaybackObjectStorage(),
        )

        with _override_handout_service(handout_service), _override_resource_service(resource_service):
            jump_status, jump_body = asyncio.run(
                request(
                    "GET",
                    f"/api/v1/handout-blocks/{block['blockId']}/jump-target",
                    headers=AUTH_HEADERS,
                )
            )
            video_resource_id = jump_body["data"]["videoResourceId"]
            playback_status, playback_body = asyncio.run(
                request(
                    "GET",
                    f"/api/v1/course-resources/{video_resource_id}/playback",
                    headers=AUTH_HEADERS,
                )
            )

        assert jump_status == 200
        assert video_resource_id is not None
        assert playback_status == 200
        assert playback_body["data"]["resourceId"] == video_resource_id
        assert playback_body["data"]["resourceType"] == "mp4"
        assert playback_body["data"]["playbackUrl"].startswith("http://127.0.0.1:9000/knowlink/")
        assert f"raw/1/{course_id}/outline.mp4" in playback_body["data"]["playbackUrl"]
        assert "method=get" in playback_body["data"]["playbackUrl"]
        assert "minio:9000" not in playback_body["data"]["playbackUrl"]
        assert playback_body["data"]["mimeType"] == "video/mp4"
        assert playback_body["data"]["durationSec"] is None
    finally:
        session.close()
        engine.dispose()


def test_handout_block_worker_generates_one_block_refs_and_vector_document():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        trigger, _ = repo.prepare_handout_block_generation(block["blockId"])
        source_segment_key = block["sourceSegmentKeys"][0]
        source_segment_id = int(source_segment_key.removeprefix("segment-"))

        def fake_generate_block(outline_item, segments, preferences=None, client=None):
            assert outline_item["outlineKey"] == block["outlineKey"]
            assert any(segment["segmentKey"] == source_segment_key for segment in segments)
            return {
                "outlineKey": block["outlineKey"],
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义\n\n集合是确定对象组成的整体。",
                "sourceSegmentKeys": [source_segment_key],
                "knowledgePoints": [{"knowledgePointKey": "kp-set", "displayName": "集合"}],
                "citations": [
                    {
                        "resourceId": 1,
                        "segmentId": source_segment_id,
                        "startSec": block["startSec"],
                        "endSec": min(block["endSec"], block["startSec"] + 20),
                    }
                ],
            }

        result = run_handout_block_generate(
            {
                "taskId": trigger["taskId"],
                "courseId": course_id,
                "handoutVersionId": repo.get_course(course_id)["activeHandoutVersionId"],
                "handoutBlockId": block["blockId"],
                "sourceParseRunId": repo.get_course(course_id)["activeParseRunId"],
            },
            session_factory=lambda: session,
            generate_block_func=fake_generate_block,
        )

        assert result["status"] == "ready"
        saved_block = repo.get_latest_handout(course_id)["blocks"][0]
        assert saved_block["status"] == "ready"
        assert saved_block["contentMd"].startswith("## 集合定义")
        assert saved_block["citations"][0]["segmentId"] == source_segment_id

        vector_documents = Base.metadata.tables["vector_documents"]
        vector_row = session.execute(
            sa.select(vector_documents).where(
                vector_documents.c.owner_type == "handout_block",
                vector_documents.c.owner_id == block["blockId"],
            )
        ).mappings().one()
        assert vector_row["course_id"] == course_id
        assert vector_row["handout_version_id"] == repo.get_course(course_id)["activeHandoutVersionId"]
        assert "集合定义" in vector_row["content_text"]
    finally:
        session.close()
        engine.dispose()


def test_handout_block_worker_duplicate_delivery_does_not_rerun_ready_block():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        trigger, _ = repo.prepare_handout_block_generation(block["blockId"])
        source_segment_key = block["sourceSegmentKeys"][0]
        source_segment_id = int(source_segment_key.removeprefix("segment-"))
        calls = 0

        def fake_generate_block(outline_item, segments, preferences=None, client=None):
            nonlocal calls
            calls += 1
            return {
                "outlineKey": block["outlineKey"],
                "title": "集合定义",
                "summary": "理解集合定义。",
                "contentMd": "## 集合定义",
                "sourceSegmentKeys": [source_segment_key],
                "knowledgePoints": [],
                "citations": [
                    {
                        "resourceId": 1,
                        "segmentId": source_segment_id,
                        "startSec": block["startSec"],
                        "endSec": min(block["endSec"], block["startSec"] + 20),
                    }
                ],
            }

        message = {
            "taskId": trigger["taskId"],
            "courseId": course_id,
            "handoutVersionId": repo.get_course(course_id)["activeHandoutVersionId"],
            "handoutBlockId": block["blockId"],
            "sourceParseRunId": repo.get_course(course_id)["activeParseRunId"],
        }
        first = run_handout_block_generate(
            message,
            session_factory=lambda: session,
            generate_block_func=fake_generate_block,
        )
        duplicate = run_handout_block_generate(
            message,
            session_factory=lambda: session,
            generate_block_func=fake_generate_block,
        )

        assert first["status"] == "ready"
        assert duplicate["status"] == "ready"
        assert calls == 1
    finally:
        session.close()
        engine.dispose()


def test_old_version_block_status_and_jump_target_are_not_visible():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        old_block_id = repo.get_latest_handout(course_id)["blocks"][0]["blockId"]
        service.generate_handout(course_id=course_id, idempotency_key=None)

        assert repo.get_handout_block_status(old_block_id) is None
        assert repo.get_block_jump_target(old_block_id) is None
    finally:
        session.close()
        engine.dispose()


def test_handout_block_worker_failure_refreshes_version_status_counts():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        trigger, _ = repo.prepare_handout_block_generation(block["blockId"])

        def fail_generate_block(outline_item, segments, preferences=None, client=None):
            raise RuntimeError("boom")

        result = run_handout_block_generate(
            {
                "taskId": trigger["taskId"],
                "courseId": course_id,
                "handoutVersionId": repo.get_course(course_id)["activeHandoutVersionId"],
                "handoutBlockId": block["blockId"],
                "sourceParseRunId": repo.get_course(course_id)["activeParseRunId"],
            },
            session_factory=lambda: session,
            generate_block_func=fail_generate_block,
        )

        status = service.get_status(handout_version_id=repo.get_course(course_id)["activeHandoutVersionId"])
        assert result["status"] == "failed"
        assert status["status"] == "failed"
        assert status["readyBlocks"] == 0
        assert status["pendingBlocks"] == 0
    finally:
        session.close()
        engine.dispose()


def test_handout_block_worker_rejects_old_parse_run_after_reparse():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
        service.generate_handout(course_id=course_id, idempotency_key=None)
        block = repo.get_latest_handout(course_id)["blocks"][0]
        old_handout_version_id = repo.get_course(course_id)["activeHandoutVersionId"]
        trigger, _ = repo.prepare_handout_block_generation(block["blockId"])
        old_parse_run_id = repo.get_course(course_id)["activeParseRunId"]
        resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/new-parse.pdf",
                "originalName": "new-parse.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:new-parse-block",
            },
        )
        new_parse_run, _ = repo.create_parse_run(course_id)
        repo.create_course_segments(
            course_id=course_id,
            resource_id=resource["resourceId"],
            parse_run_id=new_parse_run["parseRunId"],
            segments=[{"segmentType": "pdf_page_text", "orderNo": 1, "textContent": "新解析版本。", "pageNo": 1}],
        )
        repo.mark_parse_run_succeeded(new_parse_run["parseRunId"])
        courses = Base.metadata.tables["courses"]
        session.execute(
            sa.update(courses)
            .where(courses.c.id == course_id)
            .values(active_handout_version_id=old_handout_version_id)
        )
        session.commit()

        try:
            run_handout_block_generate(
                {
                    "taskId": trigger["taskId"],
                    "courseId": course_id,
                    "handoutVersionId": old_handout_version_id,
                    "handoutBlockId": block["blockId"],
                    "sourceParseRunId": old_parse_run_id,
                },
                session_factory=lambda: session,
                generate_block_func=lambda *args, **kwargs: {},
            )
        except ValueError as exc:
            assert "active parse run" in str(exc)
        else:
            raise AssertionError("old parse-run handout block task should fail")
    finally:
        session.close()
        engine.dispose()


def test_latest_handout_blocks_read_active_version_only_after_regenerate():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, _ = _create_course_with_active_video_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)

        first = service.generate_handout(course_id=course_id, idempotency_key=None)
        first_block_id = repo.get_latest_handout(course_id)["blocks"][0]["blockId"]
        second = service.generate_handout(course_id=course_id, idempotency_key=None)

        latest_blocks = service.get_latest_blocks(course_id=course_id)["items"]

        assert first["entity"]["id"] != second["entity"]["id"]
        assert latest_blocks[0]["handoutVersionId"] == second["entity"]["id"]
        assert latest_blocks[0]["blockId"] != first_block_id
    finally:
        session.close()
        engine.dispose()


def test_sql_handout_generate_merges_cross_group_caption_overlap():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, segment_keys = _create_course_with_overlapping_caption_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)

        service.generate_handout(course_id=course_id, idempotency_key=None)

        session.expire_all()
        outline = repo.get_latest_outline(course_id)
        assert outline is not None
        children = _outline_children(outline)
        assert [item["sourceSegmentKeys"] for item in children] == [
            [segment_keys[0], segment_keys[1]],
            [segment_keys[2]],
        ]
        first, second = children
        assert first["startSec"] == 0
        assert first["endSec"] == 250
        assert second["startSec"] == 260
        assert second["endSec"] == 320
        assert first["endSec"] <= second["startSec"]
        assert [item["sortNo"] for item in children] == [1, 2]
    finally:
        session.close()
        engine.dispose()


def test_latest_outline_returns_404_without_active_handout():
    repo, session, engine = _build_sqlite_repository()
    try:
        course = repo.create_course(
            title="无讲义课程",
            entry_type="manual_import",
            goal_text="验证无 active handout",
            preferred_style="balanced",
        )
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)

        with _override_handout_service(service):
            status, body = asyncio.run(
                request(
                    "GET",
                    f"/api/v1/courses/{course['courseId']}/handouts/latest/outline",
                    headers=AUTH_HEADERS,
                )
            )

        assert status == 404
        assert body["errorCode"] == "handout.no_active_version"
    finally:
        session.close()
        engine.dispose()


def test_sql_handout_generate_does_not_forge_video_timeline_without_caption_segments():
    repo, session, engine = _build_sqlite_repository()
    try:
        course = repo.create_course(
            title="纯文档课程",
            entry_type="manual_import",
            goal_text="不能伪造视频时间轴",
            preferred_style="balanced",
        )
        course_id = course["courseId"]
        resource = repo.create_resource(
            course_id,
            {
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/doc-only.pdf",
                "originalName": "doc-only.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:doc-only",
            },
        )
        parse_run, _ = repo.create_parse_run(course_id)
        parse_run_id = parse_run["parseRunId"]
        repo.mark_parse_run_succeeded(parse_run_id)
        repo.create_course_segments(
            course_id=course_id,
            resource_id=resource["resourceId"],
            parse_run_id=parse_run_id,
            segments=[
                {
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "纯文档片段",
                    "pageNo": 1,
                }
            ],
        )

        dispatcher = _RecordingHandoutDispatcher()
        service = HandoutService(
            courses=repo,
            handouts=repo,
            idempotency=repo,
            task_dispatcher=dispatcher,
        )
        trigger = service.generate_handout(course_id=course_id, idempotency_key=None)
        latest = repo.get_latest_handout(course_id)

        assert trigger["entity"]["type"] == "handout_version"
        assert trigger["status"] == "failed"
        assert trigger["nextAction"] == "none"
        assert latest is not None
        assert latest["status"] == "failed"
        assert latest["outlineStatus"] == "failed"
        assert latest["totalBlocks"] == 0
        assert latest["errorCode"] == "handout_outline.no_video_caption"
        assert repo.get_latest_outline(course_id) is None
        handout_tasks = [
            task
            for task in repo.list_async_tasks(course_id=course_id)
            if task["taskType"] == "handout_generate"
        ]
        assert len(handout_tasks) == 1
        assert handout_tasks[0]["status"] == "failed"
        assert handout_tasks[0]["errorCode"] == "handout_outline.no_video_caption"
        assert dispatcher.calls == []
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


def _create_course_with_active_video_segments(
    repo: SqlAlchemyRuntimeRepository,
) -> tuple[int, list[str]]:
    course = repo.create_course(
        title="视频讲义目录课程",
        entry_type="manual_import",
        goal_text="验证 outline read model",
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
    parse_run_id = parse_run["parseRunId"]
    repo.mark_parse_run_succeeded(parse_run_id)
    segments = repo.create_course_segments(
        course_id=course_id,
        resource_id=resource["resourceId"],
        parse_run_id=parse_run_id,
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
    return course_id, [segment["segmentKey"] for segment in segments]


def _create_course_with_overlapping_caption_segments(
    repo: SqlAlchemyRuntimeRepository,
) -> tuple[int, list[str]]:
    course = repo.create_course(
        title="重叠字幕目录课程",
        entry_type="manual_import",
        goal_text="验证跨分组 overlap 修复",
        preferred_style="balanced",
    )
    course_id = course["courseId"]
    resource = repo.create_resource(
        course_id,
        {
            "resourceType": "mp4",
            "objectKey": f"raw/1/{course_id}/overlap.mp4",
            "originalName": "overlap.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": 2048,
            "checksum": "sha256:overlap-video",
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
            {
                "segmentType": "video_caption",
                "orderNo": 1,
                "textContent": "第一组字幕拉长到三分钟以上。",
                "startSec": 0,
                "endSec": 200,
            },
            {
                "segmentType": "video_caption",
                "orderNo": 2,
                "textContent": "ASR 第二组字幕与前一组重叠。",
                "startSec": 190,
                "endSec": 250,
            },
            {
                "segmentType": "video_caption",
                "orderNo": 3,
                "textContent": "第二组后续字幕。",
                "startSec": 260,
                "endSec": 320,
            },
        ],
    )
    return course_id, [segment["segmentKey"] for segment in segments]


def _outline_children(outline: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for section in outline.get("items") or []:
        if isinstance(section, dict) and isinstance(section.get("children"), list):
            children.extend(child for child in section["children"] if isinstance(child, dict))
    return children


@contextmanager
def _override_handout_service(service: HandoutService) -> Iterator[None]:
    previous_overrides: dict[Any, Any] = dict(app.dependency_overrides)

    async def _service_override() -> HandoutService:
        return service

    app.dependency_overrides[get_handout_service] = _service_override
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@contextmanager
def _override_resource_service(service: ResourceService) -> Iterator[None]:
    previous_overrides: dict[Any, Any] = dict(app.dependency_overrides)

    async def _service_override() -> ResourceService:
        return service

    app.dependency_overrides[get_resource_service] = _service_override
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


class _PlaybackObjectStorage:
    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        return f"http://127.0.0.1:9000/knowlink/{object_key}?method=put"

    def presigned_get_url(self, object_key: str, *, expires: timedelta) -> str:
        return f"http://127.0.0.1:9000/knowlink/{object_key}?method=get"

    def stat_object(self, object_key: str) -> ObjectStat:
        return ObjectStat(size_bytes=None, checksum_required=False)

    def read_object_bytes(self, object_key: str) -> bytes:
        return b""


class _SemanticOutlineClient:
    def __init__(self) -> None:
        self.document_context: str | None = None

    def generate_outline(self, caption_segments, *, title, summary, document_context=None):
        self.document_context = document_context
        source_keys = [str(segment["segmentKey"]) for segment in caption_segments]
        return {
            "title": "集合论语义目录",
            "summary": "按集合论概念组织的视频讲义目录。",
            "items": [
                {
                    "outlineKey": "section-set-basics",
                    "title": "集合的概念与表示",
                    "summary": "从集合定义过渡到集合表示。",
                    "startSec": min(int(segment["startSec"]) for segment in caption_segments),
                    "endSec": max(int(segment["endSec"]) for segment in caption_segments),
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "set-basics",
                            "title": "集合论基础",
                            "summary": "理解集合、元素和属于关系的核心定义。",
                            "startSec": min(int(segment["startSec"]) for segment in caption_segments),
                            "endSec": max(int(segment["endSec"]) for segment in caption_segments),
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": source_keys,
                            "topicTags": ["集合", "元素"],
                        }
                    ],
                }
            ],
        }


class _InvalidTimelineOutlineClient:
    def generate_outline(self, caption_segments, *, title, summary, document_context=None):
        first = caption_segments[0]
        second = caption_segments[-1]
        return {
            "title": "非法目录",
            "summary": "非法时间线。",
            "items": [
                {
                    "outlineKey": "bad-section",
                    "title": "非法分组",
                    "summary": "非法分组。",
                    "startSec": int(first["startSec"]),
                    "endSec": int(second["endSec"]),
                    "sortNo": 1,
                    "children": [
                        {
                            "outlineKey": "bad-1",
                            "title": "集合定义",
                            "summary": "第一段。",
                            "startSec": int(first["startSec"]),
                            "endSec": int(second["endSec"]),
                            "sortNo": 1,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [str(first["segmentKey"]), str(second["segmentKey"])],
                            "topicTags": [],
                        },
                        {
                            "outlineKey": "bad-2",
                            "title": "属于关系",
                            "summary": "第二段。",
                            "startSec": int(second["startSec"]),
                            "endSec": int(second["endSec"]),
                            "sortNo": 2,
                            "generationStatus": "pending",
                            "sourceSegmentKeys": [str(second["segmentKey"])],
                            "topicTags": [],
                        },
                    ],
                },
            ],
        }


class _RecordingHandoutDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.block_calls: list[dict[str, object]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        raise AssertionError("handout tests should not enqueue parse pipeline")

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append({"taskId": task_id, "payload": payload})

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.block_calls.append({"taskId": task_id, "payload": payload})
