from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class CourseSegment(Base, TimestampMixin):
    __tablename__ = "course_segments"
    __table_args__ = (
        Index("ix_course_segments_course_run_order", "course_id", "parse_run_id", "order_no"),
        Index("ix_course_segments_course_run_start", "course_id", "parse_run_id", "start_sec"),
        Index("ix_course_segments_course_run_page", "course_id", "parse_run_id", "page_no"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    resource_id: Mapped[int] = mapped_column(ForeignKey("course_resources.id"), nullable=False)
    parse_run_id: Mapped[int] = mapped_column(ForeignKey("parse_runs.id"), nullable=False)

    segment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_path: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)

    start_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    formula_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
