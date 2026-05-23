from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from server.infra.db.base import Base
from server.infra.db.models import (
    BilibiliAuthSession,
    BilibiliImportRun,
    BilibiliPreviewSnapshot,
    BilibiliQrSession,
)
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


def test_memory_bilibili_import_lifecycle() -> None:
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="B站导入测试课",
        entry_type="manual_import",
        goal_text="验证运行时仓储",
        preferred_style="balanced",
    )

    qr_session = repo.create_bilibili_qr_session(
        qr_key="qr-memory-1",
        qr_url="https://passport.bilibili.com/qrcode",
    )
    saved_auth = repo.save_bilibili_auth_session(
        cookies_json={"SESSDATA": "memory-session"},
        csrf="memory-csrf",
        expires_at=None,
    )
    loaded_auth = repo.get_bilibili_auth_session()
    import_run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="single_video",
        preview={"title": "单视频预览"},
        selection={"partIds": [1]},
    )
    preview_snapshot = repo.save_bilibili_preview_snapshot(
        preview_id="bili_preview_memory",
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="single_video",
        preview={"previewId": "bili_preview_memory", "title": "单视频预览"},
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    assert qr_session["status"] == "pending_scan"
    assert import_run["status"] == "pending"
    assert import_run["stage"] == "queued"
    assert import_run["recoverable"] is False
    assert import_run["tempDir"] is None

    updated = repo.update_bilibili_import_run(
        import_run["importRunId"],
        status="downloading",
        progress_pct=40,
        stage="download",
        task_id=7201,
        recoverable=True,
        temp_dir="runtime/bilibili/9101",
    )
    runs = repo.list_bilibili_import_runs(course["courseId"])

    assert qr_session["qrKey"] == "qr-memory-1"
    assert saved_auth["csrf"] == "memory-csrf"
    assert loaded_auth == saved_auth
    assert updated is not None
    assert updated["sourceType"] == "single_video"
    assert updated["status"] == "downloading"
    assert updated["progressPct"] == 40
    assert updated["stage"] == "download"
    assert updated["taskId"] == 7201
    assert updated["recoverable"] is True
    assert updated["tempDir"] == "runtime/bilibili/9101"
    assert updated["preview"] == {"title": "单视频预览"}
    assert updated["selection"] == {"partIds": [1]}
    assert repo.get_bilibili_preview_snapshot("bili_preview_memory") == preview_snapshot
    assert repo.get_bilibili_import_run(import_run["importRunId"]) == updated
    assert runs == [updated]


def test_sql_bilibili_import_lifecycle_round_trips() -> None:
    repo, session = _build_sql_repo()
    course = repo.create_course(
        title="B站 SQL 导入测试课",
        entry_type="manual_import",
        goal_text="验证 SQL 运行时仓储",
        preferred_style="balanced",
    )

    qr_session = repo.create_bilibili_qr_session(
        qr_key="qr-sql-1",
        qr_url="https://passport.bilibili.com/qrcode",
    )
    saved_auth = repo.save_bilibili_auth_session(
        cookies_json={"SESSDATA": "sql-session"},
        csrf="sql-csrf",
        expires_at=None,
    )
    loaded_auth = repo.get_bilibili_auth_session()
    import_run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="single_video",
        preview={"title": "SQL 单视频预览"},
        selection={"partIds": [1]},
    )
    preview_snapshot = repo.save_bilibili_preview_snapshot(
        preview_id="bili_preview_sql",
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="single_video",
        preview={"previewId": "bili_preview_sql", "title": "SQL 单视频预览"},
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    assert qr_session["status"] == "pending_scan"
    assert import_run["status"] == "pending"
    assert import_run["stage"] == "queued"
    assert import_run["recoverable"] is False
    assert import_run["tempDir"] is None

    updated = repo.update_bilibili_import_run(
        import_run["importRunId"],
        status="imported",
        progress_pct=100,
        stage="done",
        resource_ids=[501],
        recoverable=True,
        temp_dir="runtime/bilibili/9101",
    )

    assert qr_session["qrKey"] == "qr-sql-1"
    assert saved_auth["csrf"] == "sql-csrf"
    assert loaded_auth == saved_auth
    raw_auth = session.scalar(sa.select(BilibiliAuthSession))
    assert raw_auth is not None
    assert raw_auth.cookies_json != {"SESSDATA": "sql-session"}
    assert "sql-session" not in repr(raw_auth.cookies_json)
    assert raw_auth.csrf != "sql-csrf"
    assert "sql-csrf" not in repr(raw_auth.csrf)
    assert updated is not None
    assert updated["sourceType"] == "single_video"
    assert updated["status"] == "imported"
    assert updated["progressPct"] == 100
    assert updated["stage"] == "done"
    assert updated["resourceIds"] == [501]
    assert updated["recoverable"] is True
    assert updated["tempDir"] == "runtime/bilibili/9101"
    assert updated["finishedAt"] is not None
    assert repo.get_bilibili_preview_snapshot("bili_preview_sql") == preview_snapshot
    assert repo.get_bilibili_import_run(import_run["importRunId"]) == updated
    assert repo.list_bilibili_import_runs(course["courseId"]) == [updated]
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliQrSession)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliAuthSession)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliPreviewSnapshot)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliImportRun)) == 1
    columns = BilibiliImportRun.__table__.columns
    assert not columns["recoverable"].nullable
    assert columns["temp_dir"].nullable


def test_sql_bilibili_preview_snapshots_are_scoped_by_user() -> None:
    repo, session = _build_sql_repo()
    other_user_repo = SqlAlchemyRuntimeRepository(session, user_id=2)
    course = repo.create_course(
        title="B站 SQL preview 用户隔离课",
        entry_type="manual_import",
        goal_text="验证 previewId 用户隔离",
        preferred_style="balanced",
    )

    first = repo.save_bilibili_preview_snapshot(
        preview_id="bili_preview_shared",
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BVfirst/",
        source_type="single_video",
        preview={"previewId": "bili_preview_shared", "title": "用户一预览"},
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    second = other_user_repo.save_bilibili_preview_snapshot(
        preview_id="bili_preview_shared",
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BVsecond/",
        source_type="single_video",
        preview={"previewId": "bili_preview_shared", "title": "用户二预览"},
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    assert first["previewSnapshotId"] != second["previewSnapshotId"]
    assert repo.get_bilibili_preview_snapshot("bili_preview_shared")["sourceUrl"].endswith("/BVfirst/")
    assert other_user_repo.get_bilibili_preview_snapshot("bili_preview_shared")["sourceUrl"].endswith("/BVsecond/")
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliPreviewSnapshot)) == 2


def _build_sql_repo() -> tuple[SqlAlchemyRuntimeRepository, Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return SqlAlchemyRuntimeRepository(session), session
