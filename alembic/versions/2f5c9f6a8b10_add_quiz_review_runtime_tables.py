"""add quiz review runtime tables

Revision ID: 2f5c9f6a8b10
Revises: 0d4ea7c5f2a9
Create Date: 2026-05-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2f5c9f6a8b10"
down_revision: Union[str, Sequence[str], None] = "0d4ea7c5f2a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
TS_TYPE = sa.DateTime(timezone=True)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS_TYPE, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS_TYPE, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "quizzes",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("handout_version_id", ID_TYPE, nullable=False),
        sa.Column("source_parse_run_id", ID_TYPE, nullable=True),
        sa.Column("quiz_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSON_TYPE, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["handout_version_id"], ["handout_versions.id"]),
        sa.ForeignKeyConstraint(["source_parse_run_id"], ["parse_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quizzes_course_created", "quizzes", ["course_id", "created_at"])
    op.create_index("ix_quizzes_course_status", "quizzes", ["course_id", "status"])
    op.create_index("ix_quizzes_handout_version", "quizzes", ["handout_version_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("quiz_id", ID_TYPE, nullable=False),
        sa.Column("question_key", sa.String(length=120), nullable=False),
        sa.Column("question_type", sa.String(length=50), nullable=False),
        sa.Column("stem_md", sa.Text(), nullable=False),
        sa.Column("options_json", JSON_TYPE, nullable=False),
        sa.Column("correct_answer", sa.String(length=20), nullable=False),
        sa.Column("explanation_md", sa.Text(), nullable=False),
        sa.Column("difficulty_level", sa.String(length=50), nullable=False),
        sa.Column("knowledge_point_key", sa.String(length=120), nullable=False),
        sa.Column("knowledge_point_name", sa.String(length=255), nullable=False),
        sa.Column("source_block_key", sa.String(length=120), nullable=False),
        sa.Column("source_segment_keys_json", JSON_TYPE, nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_id", "question_key", name="uq_quiz_questions_quiz_key"),
    )
    op.create_index("ix_quiz_questions_knowledge_point", "quiz_questions", ["knowledge_point_key"])
    op.create_index("ix_quiz_questions_quiz_sort", "quiz_questions", ["quiz_id", "sort_no"])

    op.create_table(
        "quiz_question_refs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("quiz_question_id", ID_TYPE, nullable=False),
        sa.Column("resource_id", ID_TYPE, nullable=False),
        sa.Column("segment_id", ID_TYPE, nullable=True),
        sa.Column("ref_type", sa.String(length=50), nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("slide_no", sa.Integer(), nullable=True),
        sa.Column("anchor_key", sa.String(length=255), nullable=True),
        sa.Column("start_sec", sa.Integer(), nullable=True),
        sa.Column("end_sec", sa.Integer(), nullable=True),
        sa.Column("bbox_json", JSON_TYPE, nullable=True),
        sa.Column("ref_label", sa.String(length=255), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["quiz_question_id"], ["quiz_questions.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["course_segments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_question_id", "sort_no", name="uq_quiz_question_refs_question_sort"),
    )
    op.create_index("ix_quiz_question_refs_question_sort", "quiz_question_refs", ["quiz_question_id", "sort_no"])
    op.create_index("ix_quiz_question_refs_resource", "quiz_question_refs", ["resource_id"])
    op.create_index("ix_quiz_question_refs_segment", "quiz_question_refs", ["segment_id"])

    op.create_table(
        "quiz_attempts",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("quiz_id", ID_TYPE, nullable=False),
        sa.Column("review_task_run_id", ID_TYPE, nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("result_json", JSON_TYPE, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempts_quiz_created", "quiz_attempts", ["quiz_id", "created_at"])
    op.create_index("ix_quiz_attempts_user_course", "quiz_attempts", ["user_id", "course_id"])

    op.create_table(
        "quiz_attempt_items",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("attempt_id", ID_TYPE, nullable=False),
        sa.Column("quiz_question_id", ID_TYPE, nullable=True),
        sa.Column("question_key", sa.String(length=120), nullable=False),
        sa.Column("selected_option", sa.String(length=20), nullable=False),
        sa.Column("correct_answer", sa.String(length=20), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("obtained_score", sa.Integer(), nullable=False),
        sa.Column("explanation_md", sa.Text(), nullable=False),
        sa.Column("knowledge_point_key", sa.String(length=120), nullable=False),
        sa.Column("source_block_key", sa.String(length=120), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"]),
        sa.ForeignKeyConstraint(["quiz_question_id"], ["quiz_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempt_items_attempt_sort", "quiz_attempt_items", ["attempt_id", "sort_no"])
    op.create_index("ix_quiz_attempt_items_question", "quiz_attempt_items", ["quiz_question_id"])

    op.create_table(
        "mastery_records",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("last_quiz_attempt_id", ID_TYPE, nullable=True),
        sa.Column("knowledge_point_key", sa.String(length=120), nullable=False),
        sa.Column("knowledge_point", sa.String(length=255), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("wrong_count", sa.Integer(), nullable=False),
        sa.Column("review_priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_question_keys_json", JSON_TYPE, nullable=False),
        sa.Column("source_block_key", sa.String(length=120), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["last_quiz_attempt_id"], ["quiz_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", "knowledge_point_key", name="uq_mastery_records_user_course_key"),
    )
    op.create_index("ix_mastery_records_course_priority", "mastery_records", ["course_id", "review_priority"])
    op.create_index("ix_mastery_records_user_course", "mastery_records", ["user_id", "course_id"])

    op.create_table(
        "review_task_runs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("source_quiz_attempt_id", ID_TYPE, nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("generated_count", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSON_TYPE, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("finished_at", TS_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["source_quiz_attempt_id"], ["quiz_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_task_runs_attempt", "review_task_runs", ["source_quiz_attempt_id"])
    op.create_index("ix_review_task_runs_course_created", "review_task_runs", ["course_id", "created_at"])
    op.create_index("ix_review_task_runs_course_status", "review_task_runs", ["course_id", "status"])

    op.create_table(
        "review_tasks",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("review_task_run_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("task_key", sa.String(length=120), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("recommended_minutes", sa.Integer(), nullable=False),
        sa.Column("knowledge_point_key", sa.String(length=120), nullable=True),
        sa.Column("source_block_key", sa.String(length=120), nullable=True),
        sa.Column("source_question_keys_json", JSON_TYPE, nullable=False),
        sa.Column("source_segment_keys_json", JSON_TYPE, nullable=False),
        sa.Column("recommended_action_json", JSON_TYPE, nullable=True),
        sa.Column("recommended_segment_json", JSON_TYPE, nullable=True),
        sa.Column("practice_entry_json", JSON_TYPE, nullable=True),
        sa.Column("review_order", sa.Integer(), nullable=False),
        sa.Column("intensity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("completed_at", TS_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["review_task_run_id"], ["review_task_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_task_run_id", "task_key", name="uq_review_tasks_run_key"),
    )
    op.create_index(
        "ix_review_tasks_course_status_priority",
        "review_tasks",
        ["course_id", "status", "priority_score"],
    )
    op.create_index("ix_review_tasks_knowledge_point", "review_tasks", ["knowledge_point_key"])
    op.create_index("ix_review_tasks_run_order", "review_tasks", ["review_task_run_id", "review_order"])

    op.create_table(
        "review_task_refs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("review_task_id", ID_TYPE, nullable=False),
        sa.Column("resource_id", ID_TYPE, nullable=False),
        sa.Column("segment_id", ID_TYPE, nullable=True),
        sa.Column("ref_type", sa.String(length=50), nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("slide_no", sa.Integer(), nullable=True),
        sa.Column("anchor_key", sa.String(length=255), nullable=True),
        sa.Column("start_sec", sa.Integer(), nullable=True),
        sa.Column("end_sec", sa.Integer(), nullable=True),
        sa.Column("bbox_json", JSON_TYPE, nullable=True),
        sa.Column("ref_label", sa.String(length=255), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.ForeignKeyConstraint(["review_task_id"], ["review_tasks.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["course_segments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_task_id", "sort_no", name="uq_review_task_refs_task_sort"),
    )
    op.create_index("ix_review_task_refs_resource", "review_task_refs", ["resource_id"])
    op.create_index("ix_review_task_refs_segment", "review_task_refs", ["segment_id"])
    op.create_index("ix_review_task_refs_task_sort", "review_task_refs", ["review_task_id", "sort_no"])

    op.create_table(
        "user_course_progress",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("handout_version_id", ID_TYPE, nullable=True),
        sa.Column("last_handout_block_id", ID_TYPE, nullable=True),
        sa.Column("last_video_resource_id", ID_TYPE, nullable=True),
        sa.Column("last_position_sec", sa.Integer(), nullable=True),
        sa.Column("last_doc_resource_id", ID_TYPE, nullable=True),
        sa.Column("last_page_no", sa.Integer(), nullable=True),
        sa.Column("last_slide_no", sa.Integer(), nullable=True),
        sa.Column("last_anchor_key", sa.String(length=255), nullable=True),
        sa.Column("last_activity_at", TS_TYPE, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["handout_version_id"], ["handout_versions.id"]),
        sa.ForeignKeyConstraint(["last_doc_resource_id"], ["course_resources.id"]),
        sa.ForeignKeyConstraint(["last_handout_block_id"], ["handout_blocks.id"]),
        sa.ForeignKeyConstraint(["last_video_resource_id"], ["course_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_user_course_progress_user_course"),
    )
    op.create_index(
        "ix_user_course_progress_user_activity",
        "user_course_progress",
        ["user_id", "last_activity_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_course_progress_user_activity", table_name="user_course_progress")
    op.drop_table("user_course_progress")
    op.drop_index("ix_review_task_refs_task_sort", table_name="review_task_refs")
    op.drop_index("ix_review_task_refs_segment", table_name="review_task_refs")
    op.drop_index("ix_review_task_refs_resource", table_name="review_task_refs")
    op.drop_table("review_task_refs")
    op.drop_index("ix_review_tasks_run_order", table_name="review_tasks")
    op.drop_index("ix_review_tasks_knowledge_point", table_name="review_tasks")
    op.drop_index("ix_review_tasks_course_status_priority", table_name="review_tasks")
    op.drop_table("review_tasks")
    op.drop_index("ix_review_task_runs_course_status", table_name="review_task_runs")
    op.drop_index("ix_review_task_runs_course_created", table_name="review_task_runs")
    op.drop_index("ix_review_task_runs_attempt", table_name="review_task_runs")
    op.drop_table("review_task_runs")
    op.drop_index("ix_mastery_records_user_course", table_name="mastery_records")
    op.drop_index("ix_mastery_records_course_priority", table_name="mastery_records")
    op.drop_table("mastery_records")
    op.drop_index("ix_quiz_attempt_items_question", table_name="quiz_attempt_items")
    op.drop_index("ix_quiz_attempt_items_attempt_sort", table_name="quiz_attempt_items")
    op.drop_table("quiz_attempt_items")
    op.drop_index("ix_quiz_attempts_user_course", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_quiz_created", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_index("ix_quiz_question_refs_segment", table_name="quiz_question_refs")
    op.drop_index("ix_quiz_question_refs_resource", table_name="quiz_question_refs")
    op.drop_index("ix_quiz_question_refs_question_sort", table_name="quiz_question_refs")
    op.drop_table("quiz_question_refs")
    op.drop_index("ix_quiz_questions_quiz_sort", table_name="quiz_questions")
    op.drop_index("ix_quiz_questions_knowledge_point", table_name="quiz_questions")
    op.drop_table("quiz_questions")
    op.drop_index("ix_quizzes_handout_version", table_name="quizzes")
    op.drop_index("ix_quizzes_course_status", table_name="quizzes")
    op.drop_index("ix_quizzes_course_created", table_name="quizzes")
    op.drop_table("quizzes")
