"""add lessons and scoped artifacts

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "course_lessons",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("course_id", ID_TYPE, sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("lesson_status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("primary_video_resource_id", ID_TYPE, sa.ForeignKey("course_resources.id"), nullable=True),
        sa.Column("primary_video_start_sec", sa.Integer(), nullable=True),
        sa.Column("primary_video_end_sec", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=80), server_default="manual", nullable=False),
        sa.Column("source_ref_json", sa.JSON(), nullable=True),
        sa.Column("handout_status", sa.String(length=50), server_default="not_generated", nullable=False),
        sa.Column("quiz_status", sa.String(length=50), server_default="not_generated", nullable=False),
        sa.Column("review_status", sa.String(length=50), server_default="not_due", nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=True),
        sa.Column("last_position_sec", sa.Integer(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_action", sa.JSON(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_id", "order_index", name="uq_course_lessons_course_order"),
    )
    op.create_index("ix_course_lessons_course_order", "course_lessons", ["course_id", "order_index"])
    op.create_index("ix_course_lessons_course_status", "course_lessons", ["course_id", "lesson_status"])

    op.create_table(
        "user_lesson_progress",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=False),
        sa.Column("last_position_sec", sa.Integer(), nullable=True),
        sa.Column("last_handout_block_id", ID_TYPE, sa.ForeignKey("handout_blocks.id"), nullable=True),
        sa.Column("handout_read_percent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quiz_status", sa.String(length=50), server_default="not_generated", nullable=False),
        sa.Column("review_status", sa.String(length=50), server_default="not_due", nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "course_id", "lesson_id", name="uq_user_lesson_progress_user_course_lesson"),
    )
    op.create_index("ix_user_lesson_progress_user_activity", "user_lesson_progress", ["user_id", "last_activity_at"])
    op.create_index("ix_user_lesson_progress_course_lesson", "user_lesson_progress", ["course_id", "lesson_id"])

    with op.batch_alter_table("course_resources") as batch:
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False))
        batch.add_column(sa.Column("usage_role", sa.String(length=50), server_default="course_material", nullable=False))
        batch.add_column(sa.Column("source_part_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("visible_to_course_qa", sa.Boolean(), server_default=sa.true(), nullable=False))
        batch.add_column(sa.Column("duration_sec", sa.Integer(), nullable=True))
    op.create_index(
        "ix_course_resources_course_scope_lesson",
        "course_resources",
        ["course_id", "scope_type", "lesson_id"],
    )

    with op.batch_alter_table("handout_versions") as batch:
        batch.add_column(sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False))
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("artifact_kind", sa.String(length=80), server_default="course_summary_handout", nullable=False))

    with op.batch_alter_table("qa_sessions") as batch:
        batch.add_column(sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False))
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch.alter_column("handout_version_id", existing_type=ID_TYPE, nullable=True)
        batch.alter_column("handout_block_id", existing_type=ID_TYPE, nullable=True)

    with op.batch_alter_table("quizzes") as batch:
        batch.add_column(sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False))
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("start_lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("end_lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("quiz_mode", sa.String(length=80), server_default="objective", nullable=False))
        batch.alter_column("handout_version_id", existing_type=ID_TYPE, nullable=True)

    with op.batch_alter_table("mastery_records") as batch:
        batch.drop_constraint("uq_mastery_records_user_course_key", type_="unique")
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
    op.create_index(
        "uq_mastery_records_user_course_key_course",
        "mastery_records",
        ["user_id", "course_id", "knowledge_point_key"],
        unique=True,
        sqlite_where=sa.text("lesson_id IS NULL"),
        postgresql_where=sa.text("lesson_id IS NULL"),
    )
    op.create_index(
        "uq_mastery_records_user_course_lesson_key",
        "mastery_records",
        ["user_id", "course_id", "lesson_id", "knowledge_point_key"],
        unique=True,
        sqlite_where=sa.text("lesson_id IS NOT NULL"),
        postgresql_where=sa.text("lesson_id IS NOT NULL"),
    )

    with op.batch_alter_table("review_task_runs") as batch:
        batch.add_column(sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False))
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("evidence_chain_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("review_tasks") as batch:
        batch.add_column(sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False))
        batch.add_column(sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True))
        batch.add_column(sa.Column("evidence_chain_json", sa.JSON(), nullable=True))

    op.create_table(
        "graph_snapshots",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("course_id", ID_TYPE, sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False),
        sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="placeholder", nullable=False),
        sa.Column("nodes_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("edges_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("citations_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_graph_snapshots_course_scope", "graph_snapshots", ["course_id", "scope_type", "lesson_id"])
    op.create_index("ix_graph_snapshots_course_status", "graph_snapshots", ["course_id", "status"])

    op.create_table(
        "export_runs",
        sa.Column("id", ID_TYPE, primary_key=True, autoincrement=True),
        sa.Column("course_id", ID_TYPE, sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("scope_type", sa.String(length=30), server_default="course", nullable=False),
        sa.Column("lesson_id", ID_TYPE, sa.ForeignKey("course_lessons.id"), nullable=True),
        sa.Column("export_type", sa.String(length=80), server_default="course_summary", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="placeholder", nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_export_runs_course_scope", "export_runs", ["course_id", "scope_type", "lesson_id"])
    op.create_index("ix_export_runs_course_status", "export_runs", ["course_id", "status"])


def _discard_v2_only_quiz_rows() -> None:
    quiz_filter = "scope_type != 'course' OR handout_version_id IS NULL"
    op.execute(
        sa.text(
            f"""
            DELETE FROM quiz_question_refs
            WHERE quiz_question_id IN (
                SELECT id FROM quiz_questions
                WHERE quiz_id IN (SELECT id FROM quizzes WHERE {quiz_filter})
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DELETE FROM quiz_attempt_items
            WHERE attempt_id IN (
                SELECT id FROM quiz_attempts
                WHERE quiz_id IN (SELECT id FROM quizzes WHERE {quiz_filter})
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE review_task_runs
            SET source_quiz_attempt_id = NULL
            WHERE source_quiz_attempt_id IN (
                SELECT id FROM quiz_attempts
                WHERE quiz_id IN (SELECT id FROM quizzes WHERE {quiz_filter})
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE mastery_records
            SET last_quiz_attempt_id = NULL
            WHERE last_quiz_attempt_id IN (
                SELECT id FROM quiz_attempts
                WHERE quiz_id IN (SELECT id FROM quizzes WHERE {quiz_filter})
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DELETE FROM quiz_attempts
            WHERE quiz_id IN (SELECT id FROM quizzes WHERE {quiz_filter})
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DELETE FROM quiz_questions
            WHERE quiz_id IN (SELECT id FROM quizzes WHERE {quiz_filter})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM quizzes WHERE {quiz_filter}"))


def _discard_v2_only_qa_rows() -> None:
    qa_filter = "scope_type != 'course' OR handout_version_id IS NULL OR handout_block_id IS NULL"
    op.execute(
        sa.text(
            f"""
            DELETE FROM qa_message_refs
            WHERE qa_message_id IN (
                SELECT id FROM qa_messages
                WHERE session_id IN (SELECT id FROM qa_sessions WHERE {qa_filter})
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DELETE FROM qa_messages
            WHERE session_id IN (SELECT id FROM qa_sessions WHERE {qa_filter})
            """
        )
    )
    op.execute(sa.text(f"DELETE FROM qa_sessions WHERE {qa_filter}"))


def downgrade() -> None:
    op.drop_index("ix_export_runs_course_status", table_name="export_runs")
    op.drop_index("ix_export_runs_course_scope", table_name="export_runs")
    op.drop_table("export_runs")

    op.drop_index("ix_graph_snapshots_course_status", table_name="graph_snapshots")
    op.drop_index("ix_graph_snapshots_course_scope", table_name="graph_snapshots")
    op.drop_table("graph_snapshots")

    with op.batch_alter_table("review_tasks") as batch:
        batch.drop_column("evidence_chain_json")
        batch.drop_column("lesson_id")
        batch.drop_column("scope_type")

    with op.batch_alter_table("review_task_runs") as batch:
        batch.drop_column("evidence_chain_json")
        batch.drop_column("lesson_id")
        batch.drop_column("scope_type")

    op.drop_index("uq_mastery_records_user_course_lesson_key", table_name="mastery_records")
    op.drop_index("uq_mastery_records_user_course_key_course", table_name="mastery_records")
    with op.batch_alter_table("mastery_records") as batch:
        batch.drop_column("lesson_id")
        batch.create_unique_constraint("uq_mastery_records_user_course_key", ["user_id", "course_id", "knowledge_point_key"])

    _discard_v2_only_quiz_rows()
    with op.batch_alter_table("quizzes") as batch:
        batch.alter_column("handout_version_id", existing_type=ID_TYPE, nullable=False)
        batch.drop_column("quiz_mode")
        batch.drop_column("end_lesson_id")
        batch.drop_column("start_lesson_id")
        batch.drop_column("lesson_id")
        batch.drop_column("scope_type")

    _discard_v2_only_qa_rows()
    with op.batch_alter_table("qa_sessions") as batch:
        batch.alter_column("handout_block_id", existing_type=ID_TYPE, nullable=False)
        batch.alter_column("handout_version_id", existing_type=ID_TYPE, nullable=False)
        batch.drop_column("title")
        batch.drop_column("lesson_id")
        batch.drop_column("scope_type")

    with op.batch_alter_table("handout_versions") as batch:
        batch.drop_column("artifact_kind")
        batch.drop_column("lesson_id")
        batch.drop_column("scope_type")

    op.drop_index("ix_course_resources_course_scope_lesson", table_name="course_resources")
    with op.batch_alter_table("course_resources") as batch:
        batch.drop_column("duration_sec")
        batch.drop_column("visible_to_course_qa")
        batch.drop_column("source_part_id")
        batch.drop_column("usage_role")
        batch.drop_column("scope_type")
        batch.drop_column("lesson_id")

    op.drop_index("ix_user_lesson_progress_course_lesson", table_name="user_lesson_progress")
    op.drop_index("ix_user_lesson_progress_user_activity", table_name="user_lesson_progress")
    op.drop_table("user_lesson_progress")

    op.drop_index("ix_course_lessons_course_status", table_name="course_lessons")
    op.drop_index("ix_course_lessons_course_order", table_name="course_lessons")
    op.drop_table("course_lessons")
