from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class CourseLesson(Base, TimestampMixin):
    __tablename__ = "course_lessons"
    __table_args__ = (
        UniqueConstraint("course_id", "order_index", name="uq_course_lessons_course_order"),
        Index("ix_course_lessons_course_order", "course_id", "order_index"),
        Index("ix_course_lessons_course_status", "course_id", "lesson_status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    primary_video_resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)
    primary_video_start_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_video_end_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_type: Mapped[str] = mapped_column(String(80), default="manual", nullable=False)
    source_ref_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    handout_status: Mapped[str] = mapped_column(String(50), default="not_generated", nullable=False)
    quiz_status: Mapped[str] = mapped_column(String(50), default="not_generated", nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="not_due", nullable=False)
    mastery_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    last_position_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserLessonProgress(Base, TimestampMixin):
    __tablename__ = "user_lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "lesson_id", name="uq_user_lesson_progress_user_course_lesson"),
        Index("ix_user_lesson_progress_user_activity", "user_id", "last_activity_at"),
        Index("ix_user_lesson_progress_course_lesson", "course_id", "lesson_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("course_lessons.id"), nullable=False)

    last_position_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_handout_block_id: Mapped[int | None] = mapped_column(ForeignKey("handout_blocks.id"), nullable=True)
    handout_read_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quiz_status: Mapped[str] = mapped_column(String(50), default="not_generated", nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="not_due", nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
