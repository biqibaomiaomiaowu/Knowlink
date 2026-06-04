from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class QaSession(Base, TimestampMixin):
    __tablename__ = "qa_sessions"
    __table_args__ = (
        Index("ix_qa_sessions_course_block_updated", "course_id", "handout_block_id", "updated_at"),
        Index("ix_qa_sessions_user_course", "user_id", "course_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), default="course", nullable=False)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    handout_version_id: Mapped[int | None] = mapped_column(ForeignKey("handout_versions.id"), nullable=True)
    handout_block_id: Mapped[int | None] = mapped_column(ForeignKey("handout_blocks.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    context_snapshot_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QaMessage(Base, TimestampMixin):
    __tablename__ = "qa_messages"
    __table_args__ = (
        Index("ix_qa_messages_session_created", "session_id", "created_at"),
        Index("ix_qa_messages_session_role", "session_id", "role"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("qa_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_flag: Mapped[str | None] = mapped_column(String(100), nullable=True)


class QaMessageRef(Base, TimestampMixin):
    __tablename__ = "qa_message_refs"
    __table_args__ = (
        Index("ix_qa_message_refs_message_sort", "qa_message_id", "sort_no"),
        Index("ix_qa_message_refs_segment", "segment_id"),
        Index("ix_qa_message_refs_resource", "resource_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    qa_message_id: Mapped[int] = mapped_column(ForeignKey("qa_messages.id"), nullable=False)
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
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
