from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models  # noqa: F401
from server.api.deps import get_handout_service
from server.app import app
from server.domain.services import HandoutService
from server.infra.db.base import Base
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
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
        assert outline["items"][0]["sourceSegmentKeys"] == segment_keys
        assert outline["items"][0]["generationStatus"] == "pending"
        assert isinstance(outline["items"][0]["blockId"], int)
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
        assert body["data"]["items"][0]["sourceSegmentKeys"] == segment_keys
    finally:
        session.close()
        engine.dispose()


def test_sql_handout_generate_repairs_cross_group_caption_overlap():
    repo, session, engine = _build_sqlite_repository()
    try:
        course_id, segment_keys = _create_course_with_overlapping_caption_segments(repo)
        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)

        service.generate_handout(course_id=course_id, idempotency_key=None)

        session.expire_all()
        outline = repo.get_latest_outline(course_id)
        assert outline is not None
        assert [item["sourceSegmentKeys"] for item in outline["items"]] == [
            [segment_keys[0]],
            [segment_keys[1], segment_keys[2]],
        ]
        first, second = outline["items"]
        assert first["startSec"] == 0
        assert first["endSec"] == 200
        assert second["startSec"] == 200
        assert second["endSec"] == 320
        assert first["endSec"] <= second["startSec"]
        assert [item["sortNo"] for item in outline["items"]] == [1, 2]
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

        service = HandoutService(courses=repo, handouts=repo, idempotency=repo)
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
