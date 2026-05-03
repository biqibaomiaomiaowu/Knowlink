from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class HandoutVersion(Base, TimestampMixin):
    __tablename__ = "handout_versions"
    __table_args__ = (
        Index("ix_handout_versions_course_created", "course_id", "created_at"),
        Index("ix_handout_versions_course_status", "course_id", "status"),
        Index("ix_handout_versions_source_parse", "source_parse_run_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    source_parse_run_id: Mapped[int | None] = mapped_column(ForeignKey("parse_runs.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    outline_status: Mapped[str] = mapped_column(String(50), nullable=False)
    total_blocks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ready_blocks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_blocks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)


class HandoutOutline(Base, TimestampMixin):
    __tablename__ = "handout_outlines"
    __table_args__ = (
        UniqueConstraint("handout_version_id", name="uq_handout_outlines_version"),
        Index("ix_handout_outlines_course_parse", "course_id", "source_parse_run_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    handout_version_id: Mapped[int] = mapped_column(ForeignKey("handout_versions.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    source_parse_run_id: Mapped[int | None] = mapped_column(ForeignKey("parse_runs.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outline_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class HandoutBlock(Base, TimestampMixin):
    __tablename__ = "handout_blocks"
    __table_args__ = (
        UniqueConstraint("handout_version_id", "outline_key", name="uq_handout_blocks_version_outline"),
        Index("ix_handout_blocks_version_sort", "handout_version_id", "sort_no"),
        Index("ix_handout_blocks_version_status", "handout_version_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    handout_version_id: Mapped[int] = mapped_column(ForeignKey("handout_versions.id"), nullable=False)

    outline_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_segment_keys_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    knowledge_points_json: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    citations_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
