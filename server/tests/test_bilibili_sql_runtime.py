from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from server.infra.db.base import Base
from server.infra.db.models import BilibiliAuthSession, BilibiliImportRun, BilibiliQrSession
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
        status="pending",
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

    updated = repo.update_bilibili_import_run(
        import_run["importRunId"],
        status="downloading",
        progress_pct=40,
        stage="download",
        task_id=7201,
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
    assert updated["preview"] == {"title": "单视频预览"}
    assert updated["selection"] == {"partIds": [1]}
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
        status="pending",
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

    updated = repo.update_bilibili_import_run(
        import_run["importRunId"],
        status="imported",
        progress_pct=100,
        stage="done",
        resource_ids=[501],
    )

    assert qr_session["qrKey"] == "qr-sql-1"
    assert saved_auth["csrf"] == "sql-csrf"
    assert loaded_auth == saved_auth
    assert updated is not None
    assert updated["sourceType"] == "single_video"
    assert updated["status"] == "imported"
    assert updated["progressPct"] == 100
    assert updated["stage"] == "done"
    assert updated["resourceIds"] == [501]
    assert updated["finishedAt"] is not None
    assert repo.get_bilibili_import_run(import_run["importRunId"]) == updated
    assert repo.list_bilibili_import_runs(course["courseId"]) == [updated]
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliQrSession)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliAuthSession)) == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(BilibiliImportRun)) == 1


def _build_sql_repo() -> tuple[SqlAlchemyRuntimeRepository, Session]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return SqlAlchemyRuntimeRepository(session), session
