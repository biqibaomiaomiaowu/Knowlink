from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.config.settings import get_settings
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    return Config(str(ROOT / "alembic.ini"))


def test_lesson_migration_downgrade_discards_v2_only_qa_and_quiz_placeholders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'lesson-migration.sqlite3'}"
    monkeypatch.setenv("KNOWLINK_DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        config = _alembic_config()
        command.upgrade(config, "head")

        engine = create_engine(db_url)
        try:
            with Session(engine) as session:
                repo = SqlAlchemyRuntimeRepository(session)
                course = repo.create_course(
                    title="数据库系统",
                    entry_type="manual_import",
                    goal_text="期末复习",
                    preferred_style="balanced",
                )
                course_id = int(course["courseId"])
                first = repo.create_lesson(course_id=course_id, title="第 1 节")
                second = repo.create_lesson(course_id=course_id, title="第 2 节")
                repo.create_scoped_artifact(
                    artifact_type="qa_session",
                    course_id=course_id,
                    scope_type="lesson",
                    lesson_id=first["lessonId"],
                )
                repo.create_scoped_artifact(
                    artifact_type="quiz",
                    course_id=course_id,
                    scope_type="lesson_range",
                    start_lesson_id=first["lessonId"],
                    end_lesson_id=second["lessonId"],
                )
        finally:
            engine.dispose()

        command.downgrade(config, "c8d9e0f1a2b3")
    finally:
        get_settings.cache_clear()
