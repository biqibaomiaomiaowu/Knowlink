from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class ExportRun(Base, TimestampMixin):
    __tablename__ = "export_runs"
    __table_args__ = (
        Index("ix_export_runs_course_scope", "course_id", "scope_type", "lesson_id"),
        Index("ix_export_runs_course_status", "course_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), default="course", nullable=False)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    export_type: Mapped[str] = mapped_column(String(80), default="course_summary", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="placeholder", nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
