"""add handout outline read model

Revision ID: 8b7d4f2a91c0
Revises: 1b319cfadeb3
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8b7d4f2a91c0"
down_revision: Union[str, Sequence[str], None] = "1b319cfadeb3"
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
        "handout_versions",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("source_parse_run_id", ID_TYPE, nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("outline_status", sa.String(length=50), nullable=False),
        sa.Column("total_blocks", sa.Integer(), nullable=False),
        sa.Column("ready_blocks", sa.Integer(), nullable=False),
        sa.Column("pending_blocks", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta_json", JSON_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["source_parse_run_id"], ["parse_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_handout_versions_course_created",
        "handout_versions",
        ["course_id", "created_at"],
    )
    op.create_index(
        "ix_handout_versions_course_status",
        "handout_versions",
        ["course_id", "status"],
    )
    op.create_index(
        "ix_handout_versions_source_parse",
        "handout_versions",
        ["source_parse_run_id"],
    )

    op.create_table(
        "handout_outlines",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("handout_version_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("source_parse_run_id", ID_TYPE, nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("outline_json", JSON_TYPE, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["handout_version_id"], ["handout_versions.id"]),
        sa.ForeignKeyConstraint(["source_parse_run_id"], ["parse_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handout_version_id", name="uq_handout_outlines_version"),
    )
    op.create_index(
        "ix_handout_outlines_course_parse",
        "handout_outlines",
        ["course_id", "source_parse_run_id"],
    )

    op.create_table(
        "handout_blocks",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("handout_version_id", ID_TYPE, nullable=False),
        sa.Column("outline_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=True),
        sa.Column("start_sec", sa.Integer(), nullable=True),
        sa.Column("end_sec", sa.Integer(), nullable=True),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        sa.Column("source_segment_keys_json", JSON_TYPE, nullable=False),
        sa.Column("knowledge_points_json", JSON_TYPE, nullable=True),
        sa.Column("citations_json", JSON_TYPE, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["handout_version_id"], ["handout_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "handout_version_id",
            "outline_key",
            name="uq_handout_blocks_version_outline",
        ),
    )
    op.create_index(
        "ix_handout_blocks_version_sort",
        "handout_blocks",
        ["handout_version_id", "sort_no"],
    )
    op.create_index(
        "ix_handout_blocks_version_status",
        "handout_blocks",
        ["handout_version_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_handout_blocks_version_status", table_name="handout_blocks")
    op.drop_index("ix_handout_blocks_version_sort", table_name="handout_blocks")
    op.drop_table("handout_blocks")
    op.drop_index("ix_handout_outlines_course_parse", table_name="handout_outlines")
    op.drop_table("handout_outlines")
    op.drop_index("ix_handout_versions_source_parse", table_name="handout_versions")
    op.drop_index("ix_handout_versions_course_status", table_name="handout_versions")
    op.drop_index("ix_handout_versions_course_created", table_name="handout_versions")
    op.drop_table("handout_versions")
