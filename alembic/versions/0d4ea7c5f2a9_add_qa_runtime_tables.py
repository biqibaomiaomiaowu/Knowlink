"""add qa runtime tables

Revision ID: 0d4ea7c5f2a9
Revises: 74d9bc0a9e1c
Create Date: 2026-05-07 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0d4ea7c5f2a9"
down_revision: Union[str, Sequence[str], None] = "74d9bc0a9e1c"
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
        "qa_sessions",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("handout_version_id", ID_TYPE, nullable=False),
        sa.Column("handout_block_id", ID_TYPE, nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("context_snapshot_json", JSON_TYPE, nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("last_message_at", TS_TYPE, nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["handout_block_id"], ["handout_blocks.id"]),
        sa.ForeignKeyConstraint(["handout_version_id"], ["handout_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_qa_sessions_course_block_updated",
        "qa_sessions",
        ["course_id", "handout_block_id", "updated_at"],
    )
    op.create_index("ix_qa_sessions_user_course", "qa_sessions", ["user_id", "course_id"])

    op.create_table(
        "qa_messages",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("session_id", ID_TYPE, nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("answer_type", sa.String(length=50), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage_prompt", sa.Integer(), nullable=True),
        sa.Column("token_usage_completion", sa.Integer(), nullable=True),
        sa.Column("safety_flag", sa.String(length=100), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["session_id"], ["qa_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_messages_session_created", "qa_messages", ["session_id", "created_at"])
    op.create_index("ix_qa_messages_session_role", "qa_messages", ["session_id", "role"])

    op.create_table(
        "qa_message_refs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("qa_message_id", ID_TYPE, nullable=False),
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
        sa.Column("rank", sa.Integer(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["qa_message_id"], ["qa_messages.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["course_segments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_message_refs_message_sort", "qa_message_refs", ["qa_message_id", "sort_no"])
    op.create_index("ix_qa_message_refs_resource", "qa_message_refs", ["resource_id"])
    op.create_index("ix_qa_message_refs_segment", "qa_message_refs", ["segment_id"])


def downgrade() -> None:
    op.drop_index("ix_qa_message_refs_segment", table_name="qa_message_refs")
    op.drop_index("ix_qa_message_refs_resource", table_name="qa_message_refs")
    op.drop_index("ix_qa_message_refs_message_sort", table_name="qa_message_refs")
    op.drop_table("qa_message_refs")
    op.drop_index("ix_qa_messages_session_role", table_name="qa_messages")
    op.drop_index("ix_qa_messages_session_created", table_name="qa_messages")
    op.drop_table("qa_messages")
    op.drop_index("ix_qa_sessions_user_course", table_name="qa_sessions")
    op.drop_index("ix_qa_sessions_course_block_updated", table_name="qa_sessions")
    op.drop_table("qa_sessions")
