from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class BilibiliQrSession(Base, TimestampMixin):
    __tablename__ = "bilibili_qr_sessions"
    __table_args__ = (
        Index("ix_bilibili_qr_sessions_qr_key", "qr_key", unique=True),
        Index("ix_bilibili_qr_sessions_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    qr_key: Mapped[str] = mapped_column(String(128), nullable=False)
    qr_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending_scan", nullable=False)
    poll_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BilibiliAuthSession(Base, TimestampMixin):
    __tablename__ = "bilibili_auth_sessions"
    __table_args__ = (
        Index("ix_bilibili_auth_sessions_user_id", "user_id", unique=True),
        Index("ix_bilibili_auth_sessions_status", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    cookies_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    csrf: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BilibiliPreviewSnapshot(Base, TimestampMixin):
    __tablename__ = "bilibili_preview_snapshots"
    __table_args__ = (
        Index("ix_bilibili_preview_snapshots_user_preview", "user_id", "preview_id", unique=True),
        Index("ix_bilibili_preview_snapshots_course_user", "course_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    preview_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    preview_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BilibiliImportRun(Base, TimestampMixin):
    __tablename__ = "bilibili_import_runs"
    __table_args__ = (
        Index("ix_bilibili_import_runs_course_status", "course_id", "status"),
        Index("ix_bilibili_import_runs_task_id", "task_id"),
        Index("ix_bilibili_import_runs_source_type", "source_type"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("async_tasks.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    stage: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preview_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    selection_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    resource_ids_json: Mapped[list[int] | None] = mapped_column(JSON_TYPE, nullable=True)
    recoverable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
    temp_dir: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BilibiliImportItem(Base, TimestampMixin):
    __tablename__ = "bilibili_import_items"
    __table_args__ = (
        Index("ix_bilibili_import_items_run_status", "import_run_id", "status"),
        Index("ix_bilibili_import_items_course_resource", "course_id", "resource_id"),
        Index("ix_bilibili_import_items_course_lesson", "course_id", "lesson_id"),
        Index("ix_bilibili_import_items_run_item_key", "import_run_id", "item_key", unique=True),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("bilibili_import_runs.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    item_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    part_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
