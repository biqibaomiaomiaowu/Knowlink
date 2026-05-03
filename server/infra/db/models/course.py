from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class Course(Base, TimestampMixin):
    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_user_updated", "user_id", "updated_at"),
        Index("ix_courses_user_lifecycle", "user_id", "lifecycle_status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    catalog_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferred_style: Mapped[str] = mapped_column(String(50), default="balanced", nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    lifecycle_status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    pipeline_stage: Mapped[str] = mapped_column(String(50), default="idle", nullable=False)
    pipeline_status: Mapped[str] = mapped_column(String(50), default="idle", nullable=False)

    active_parse_run_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    active_handout_version_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
