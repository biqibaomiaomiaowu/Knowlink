from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class CourseResource(Base, TimestampMixin):
    __tablename__ = "course_resources"
    __table_args__ = (
        Index("ix_course_resources_course_ingest", "course_id", "ingest_status"),
        Index("ix_course_resources_course_validation", "course_id", "validation_status"),
        Index("ix_course_resources_course_processing", "course_id", "processing_status"),
        Index("ix_course_resources_checksum", "checksum"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)

    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="upload", nullable=False)
    origin_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    preview_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)

    ingest_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    processing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    last_parse_run_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_policy_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
