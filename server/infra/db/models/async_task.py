from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class AsyncTask(Base, TimestampMixin):
    __tablename__ = "async_tasks"
    __table_args__ = (
        Index("ix_async_tasks_parse_status", "parse_run_id", "status"),
        Index("ix_async_tasks_parent_status", "parent_task_id", "status"),
        Index("ix_async_tasks_course_type_status", "course_id", "task_type", "status"),
        Index("ix_async_tasks_course_target", "course_id", "target_type", "target_id"),
        Index("ix_async_tasks_resource_status", "resource_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    parse_run_id: Mapped[int | None] = mapped_column(ForeignKey("parse_runs.id"), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)

    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("async_tasks.id"), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    step_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    payload_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
