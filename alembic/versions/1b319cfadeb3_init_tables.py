"""init week2 runtime tables

Revision ID: 1b319cfadeb3
Revises:
Create Date: 2026-04-26 18:45:37.335822

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1b319cfadeb3"
down_revision: Union[str, Sequence[str], None] = None
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
        "courses",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("entry_type", sa.String(length=50), nullable=False),
        sa.Column("catalog_id", sa.String(length=100), nullable=True),
        sa.Column("goal_text", sa.Text(), nullable=True),
        sa.Column("exam_at", TS_TYPE, nullable=True),
        sa.Column("preferred_style", sa.String(length=50), nullable=False),
        sa.Column("cover_url", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=50), nullable=False),
        sa.Column("pipeline_stage", sa.String(length=50), nullable=False),
        sa.Column("pipeline_status", sa.String(length=50), nullable=False),
        sa.Column("active_parse_run_id", ID_TYPE, nullable=True),
        sa.Column("active_handout_version_id", ID_TYPE, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("meta_json", JSON_TYPE, nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_courses_user_lifecycle", "courses", ["user_id", "lifecycle_status"])
    op.create_index("ix_courses_user_updated", "courses", ["user_id", "updated_at"])

    op.create_table(
        "parse_runs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("source_parse_run_id", ID_TYPE, nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("summary_json", JSON_TYPE, nullable=True),
        sa.Column("started_at", TS_TYPE, nullable=True),
        sa.Column("finished_at", TS_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parse_runs_course_created", "parse_runs", ["course_id", "created_at"])
    op.create_index("ix_parse_runs_course_status", "parse_runs", ["course_id", "status"])

    op.create_table(
        "course_resources",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("origin_url", sa.String(length=1000), nullable=True),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("preview_key", sa.String(length=500), nullable=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", ID_TYPE, nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("ingest_status", sa.String(length=50), nullable=False),
        sa.Column("validation_status", sa.String(length=50), nullable=False),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("last_parse_run_id", ID_TYPE, nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("parse_policy_json", JSON_TYPE, nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_course_resources_checksum", "course_resources", ["checksum"])
    op.create_index(
        "ix_course_resources_course_ingest",
        "course_resources",
        ["course_id", "ingest_status"],
    )
    op.create_index(
        "ix_course_resources_course_processing",
        "course_resources",
        ["course_id", "processing_status"],
    )
    op.create_index(
        "ix_course_resources_course_validation",
        "course_resources",
        ["course_id", "validation_status"],
    )

    op.create_table(
        "async_tasks",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("parse_run_id", ID_TYPE, nullable=True),
        sa.Column("resource_id", ID_TYPE, nullable=True),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("parent_task_id", ID_TYPE, nullable=True),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", ID_TYPE, nullable=True),
        sa.Column("step_code", sa.String(length=100), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSON_TYPE, nullable=True),
        sa.Column("result_json", JSON_TYPE, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", TS_TYPE, nullable=True),
        sa.Column("finished_at", TS_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["parse_run_id"], ["parse_runs.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.ForeignKeyConstraint(["parent_task_id"], ["async_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_async_tasks_course_target",
        "async_tasks",
        ["course_id", "target_type", "target_id"],
    )
    op.create_index(
        "ix_async_tasks_course_type_status",
        "async_tasks",
        ["course_id", "task_type", "status"],
    )
    op.create_index("ix_async_tasks_parent_status", "async_tasks", ["parent_task_id", "status"])
    op.create_index("ix_async_tasks_parse_status", "async_tasks", ["parse_run_id", "status"])
    op.create_index("ix_async_tasks_resource_status", "async_tasks", ["resource_id", "status"])

    op.create_table(
        "course_segments",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("resource_id", ID_TYPE, nullable=False),
        sa.Column("parse_run_id", ID_TYPE, nullable=False),
        sa.Column("segment_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("section_path", JSON_TYPE, nullable=True),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=True),
        sa.Column("end_sec", sa.Float(), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("slide_no", sa.Integer(), nullable=True),
        sa.Column("image_key", sa.String(length=500), nullable=True),
        sa.Column("formula_text", sa.Text(), nullable=True),
        sa.Column("bbox_json", JSON_TYPE, nullable=True),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["parse_run_id"], ["parse_runs.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_course_segments_course_run_order",
        "course_segments",
        ["course_id", "parse_run_id", "order_no"],
    )
    op.create_index(
        "ix_course_segments_course_run_page",
        "course_segments",
        ["course_id", "parse_run_id", "page_no"],
    )
    op.create_index(
        "ix_course_segments_course_run_start",
        "course_segments",
        ["course_id", "parse_run_id", "start_sec"],
    )

    op.create_table(
        "learning_preferences",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("goal_type", sa.String(length=50), nullable=False),
        sa.Column("self_level", sa.String(length=50), nullable=False),
        sa.Column("time_budget_minutes", sa.Integer(), nullable=False),
        sa.Column("exam_at", TS_TYPE, nullable=True),
        sa.Column("preferred_style", sa.String(length=50), nullable=False),
        sa.Column("example_density", sa.String(length=50), nullable=False),
        sa.Column("formula_detail_level", sa.String(length=50), nullable=False),
        sa.Column("language_style", sa.String(length=50), nullable=False),
        sa.Column("focus_knowledge_json", JSON_TYPE, nullable=True),
        sa.Column("inquiry_answers_json", JSON_TYPE, nullable=False),
        sa.Column("confirmed_at", TS_TYPE, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", name="uq_learning_preferences_user_course"),
    )
    op.create_index("ix_learning_preferences_course", "learning_preferences", ["course_id"])

    op.create_table(
        "vector_documents",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("parse_run_id", ID_TYPE, nullable=True),
        sa.Column("handout_version_id", ID_TYPE, nullable=True),
        sa.Column("owner_type", sa.String(length=50), nullable=False),
        sa.Column("owner_id", ID_TYPE, nullable=False),
        sa.Column("resource_id", ID_TYPE, nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSON_TYPE, nullable=False),
        sa.Column("embedding", JSON_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["parse_run_id"], ["parse_runs.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vector_documents_course_parse",
        "vector_documents",
        ["course_id", "parse_run_id"],
    )
    op.create_index("ix_vector_documents_owner", "vector_documents", ["owner_type", "owner_id"])
    op.create_index("ix_vector_documents_resource", "vector_documents", ["resource_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("result_json", JSON_TYPE, nullable=True),
        *timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action", "key", name="uq_idempotency_records_action_key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_vector_documents_resource", table_name="vector_documents")
    op.drop_index("ix_vector_documents_owner", table_name="vector_documents")
    op.drop_index("ix_vector_documents_course_parse", table_name="vector_documents")
    op.drop_table("vector_documents")
    op.drop_index("ix_learning_preferences_course", table_name="learning_preferences")
    op.drop_table("learning_preferences")
    op.drop_index("ix_course_segments_course_run_start", table_name="course_segments")
    op.drop_index("ix_course_segments_course_run_page", table_name="course_segments")
    op.drop_index("ix_course_segments_course_run_order", table_name="course_segments")
    op.drop_table("course_segments")
    op.drop_index("ix_async_tasks_resource_status", table_name="async_tasks")
    op.drop_index("ix_async_tasks_parse_status", table_name="async_tasks")
    op.drop_index("ix_async_tasks_parent_status", table_name="async_tasks")
    op.drop_index("ix_async_tasks_course_type_status", table_name="async_tasks")
    op.drop_index("ix_async_tasks_course_target", table_name="async_tasks")
    op.drop_table("async_tasks")
    op.drop_index("ix_course_resources_course_validation", table_name="course_resources")
    op.drop_index("ix_course_resources_course_processing", table_name="course_resources")
    op.drop_index("ix_course_resources_course_ingest", table_name="course_resources")
    op.drop_index("ix_course_resources_checksum", table_name="course_resources")
    op.drop_table("course_resources")
    op.drop_index("ix_parse_runs_course_status", table_name="parse_runs")
    op.drop_index("ix_parse_runs_course_created", table_name="parse_runs")
    op.drop_table("parse_runs")
    op.drop_index("ix_courses_user_updated", table_name="courses")
    op.drop_index("ix_courses_user_lifecycle", table_name="courses")
    op.drop_table("courses")
