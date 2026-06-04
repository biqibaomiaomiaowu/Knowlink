from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class Quiz(Base, TimestampMixin):
    __tablename__ = "quizzes"
    __table_args__ = (
        Index("ix_quizzes_course_created", "course_id", "created_at"),
        Index("ix_quizzes_course_status", "course_id", "status"),
        Index("ix_quizzes_handout_version", "handout_version_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), default="course", nullable=False)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    start_lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    end_lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    quiz_mode: Mapped[str] = mapped_column(String(80), default="objective", nullable=False)
    handout_version_id: Mapped[int | None] = mapped_column(ForeignKey("handout_versions.id"), nullable=True)
    source_parse_run_id: Mapped[int | None] = mapped_column(ForeignKey("parse_runs.id"), nullable=True)

    quiz_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuizQuestion(Base, TimestampMixin):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "question_key", name="uq_quiz_questions_quiz_key"),
        Index("ix_quiz_questions_quiz_sort", "quiz_id", "sort_no"),
        Index("ix_quiz_questions_knowledge_point", "knowledge_point_key"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)

    question_key: Mapped[str] = mapped_column(String(120), nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), nullable=False)
    stem_md: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation_md: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty_level: Mapped[str] = mapped_column(String(50), nullable=False)
    knowledge_point_key: Mapped[str] = mapped_column(String(120), nullable=False)
    knowledge_point_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_block_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source_segment_keys_json: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False)


class QuizQuestionRef(Base, TimestampMixin):
    __tablename__ = "quiz_question_refs"
    __table_args__ = (
        UniqueConstraint("quiz_question_id", "sort_no", name="uq_quiz_question_refs_question_sort"),
        Index("ix_quiz_question_refs_question_sort", "quiz_question_id", "sort_no"),
        Index("ix_quiz_question_refs_segment", "segment_id"),
        Index("ix_quiz_question_refs_resource", "resource_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    quiz_question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), nullable=False)
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


class QuizAttempt(Base, TimestampMixin):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_quiz_attempts_quiz_created", "quiz_id", "created_at"),
        Index("ix_quiz_attempts_user_course", "user_id", "course_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    review_task_run_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)

    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class QuizAttemptItem(Base, TimestampMixin):
    __tablename__ = "quiz_attempt_items"
    __table_args__ = (
        Index("ix_quiz_attempt_items_attempt_sort", "attempt_id", "sort_no"),
        Index("ix_quiz_attempt_items_question", "quiz_question_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=False)
    quiz_question_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_questions.id"), nullable=True)

    question_key: Mapped[str] = mapped_column(String(120), nullable=False)
    selected_option: Mapped[str] = mapped_column(String(20), nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(20), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    obtained_score: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation_md: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_point_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source_block_key: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False)
