"""add bilibili import tables

Revision ID: 9f42a7d8c6b1
Revises: 4a6c1d9e8b20
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f42a7d8c6b1"
down_revision: Union[str, Sequence[str], None] = "4a6c1d9e8b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "bilibili_qr_sessions",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("qr_key", sa.String(length=128), nullable=False),
        sa.Column("qr_url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("poll_payload_json", JSON_TYPE, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bilibili_qr_sessions_qr_key", "bilibili_qr_sessions", ["qr_key"], unique=True)
    op.create_index(
        "ix_bilibili_qr_sessions_status_created",
        "bilibili_qr_sessions",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "bilibili_auth_sessions",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("cookies_json", JSON_TYPE, nullable=False),
        sa.Column("csrf", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bilibili_auth_sessions_user_id", "bilibili_auth_sessions", ["user_id"], unique=True)
    op.create_index("ix_bilibili_auth_sessions_status", "bilibili_auth_sessions", ["status"], unique=False)

    op.create_table(
        "bilibili_import_runs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("task_id", ID_TYPE, nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("preview_json", JSON_TYPE, nullable=True),
        sa.Column("selection_json", JSON_TYPE, nullable=True),
        sa.Column("resource_ids_json", JSON_TYPE, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["async_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bilibili_import_runs_course_status",
        "bilibili_import_runs",
        ["course_id", "status"],
        unique=False,
    )
    op.create_index("ix_bilibili_import_runs_task_id", "bilibili_import_runs", ["task_id"], unique=False)
    op.create_index("ix_bilibili_import_runs_source_type", "bilibili_import_runs", ["source_type"], unique=False)

    op.create_table(
        "bilibili_import_items",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("import_run_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("resource_id", ID_TYPE, nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("item_key", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("part_no", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("metadata_json", JSON_TYPE, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["import_run_id"], ["bilibili_import_runs.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bilibili_import_items_run_status",
        "bilibili_import_items",
        ["import_run_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_bilibili_import_items_course_resource",
        "bilibili_import_items",
        ["course_id", "resource_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bilibili_import_items_course_resource", table_name="bilibili_import_items")
    op.drop_index("ix_bilibili_import_items_run_status", table_name="bilibili_import_items")
    op.drop_table("bilibili_import_items")
    op.drop_index("ix_bilibili_import_runs_source_type", table_name="bilibili_import_runs")
    op.drop_index("ix_bilibili_import_runs_task_id", table_name="bilibili_import_runs")
    op.drop_index("ix_bilibili_import_runs_course_status", table_name="bilibili_import_runs")
    op.drop_table("bilibili_import_runs")
    op.drop_index("ix_bilibili_auth_sessions_status", table_name="bilibili_auth_sessions")
    op.drop_index("ix_bilibili_auth_sessions_user_id", table_name="bilibili_auth_sessions")
    op.drop_table("bilibili_auth_sessions")
    op.drop_index("ix_bilibili_qr_sessions_status_created", table_name="bilibili_qr_sessions")
    op.drop_index("ix_bilibili_qr_sessions_qr_key", table_name="bilibili_qr_sessions")
    op.drop_table("bilibili_qr_sessions")
