from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class LearningPreference(Base, TimestampMixin):
    __tablename__ = "learning_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_learning_preferences_user_course"),
        Index("ix_learning_preferences_course", "course_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)

    goal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    self_level: Mapped[str] = mapped_column(String(50), nullable=False)
    time_budget_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferred_style: Mapped[str] = mapped_column(String(50), nullable=False)
    example_density: Mapped[str] = mapped_column(String(50), nullable=False)
    formula_detail_level: Mapped[str] = mapped_column(String(50), nullable=False)
    language_style: Mapped[str] = mapped_column(String(50), default="friendly", nullable=False)
    focus_knowledge_json: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    inquiry_answers_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
