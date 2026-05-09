from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class MasteryRecord(Base, TimestampMixin):
    __tablename__ = "mastery_records"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "knowledge_point_key", name="uq_mastery_records_user_course_key"),
        Index("ix_mastery_records_course_priority", "course_id", "review_priority"),
        Index("ix_mastery_records_user_course", "user_id", "course_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    last_quiz_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=True)

    knowledge_point_key: Mapped[str] = mapped_column(String(120), nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(255), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    source_question_keys_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    source_block_key: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ReviewTaskRun(Base, TimestampMixin):
    __tablename__ = "review_task_runs"
    __table_args__ = (
        Index("ix_review_task_runs_course_created", "course_id", "created_at"),
        Index("ix_review_task_runs_course_status", "course_id", "status"),
        Index("ix_review_task_runs_attempt", "source_quiz_attempt_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    source_quiz_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewTask(Base, TimestampMixin):
    __tablename__ = "review_tasks"
    __table_args__ = (
        UniqueConstraint("review_task_run_id", "task_key", name="uq_review_tasks_run_key"),
        Index("ix_review_tasks_course_status_priority", "course_id", "status", "priority_score"),
        Index("ix_review_tasks_run_order", "review_task_run_id", "review_order"),
        Index("ix_review_tasks_knowledge_point", "knowledge_point_key"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    review_task_run_id: Mapped[int] = mapped_column(ForeignKey("review_task_runs.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)

    task_key: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    knowledge_point_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_block_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_question_keys_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    source_segment_keys_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    recommended_action_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    recommended_segment_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    practice_entry_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    review_order: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewTaskRef(Base, TimestampMixin):
    __tablename__ = "review_task_refs"
    __table_args__ = (
        UniqueConstraint("review_task_id", "sort_no", name="uq_review_task_refs_task_sort"),
        Index("ix_review_task_refs_task_sort", "review_task_id", "sort_no"),
        Index("ix_review_task_refs_segment", "segment_id"),
        Index("ix_review_task_refs_resource", "resource_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    review_task_id: Mapped[int] = mapped_column(ForeignKey("review_tasks.id"), nullable=False)
    resource_id: Mapped[int] = mapped_column(ForeignKey("course_resources.id"), nullable=False)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("course_segments.id"), nullable=True)

    ref_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quote_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anchor_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    ref_label: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False)


class UserCourseProgress(Base, TimestampMixin):
    __tablename__ = "user_course_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_user_course_progress_user_course"),
        Index("ix_user_course_progress_user_activity", "user_id", "last_activity_at"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    handout_version_id: Mapped[int | None] = mapped_column(ForeignKey("handout_versions.id"), nullable=True)
    last_handout_block_id: Mapped[int | None] = mapped_column(ForeignKey("handout_blocks.id"), nullable=True)
    last_video_resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)
    last_position_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_doc_resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)
    last_page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_slide_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_anchor_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
