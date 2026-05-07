"""add handout block refs

Revision ID: 74d9bc0a9e1c
Revises: 8b7d4f2a91c0
Create Date: 2026-05-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "74d9bc0a9e1c"
down_revision: Union[str, Sequence[str], None] = "8b7d4f2a91c0"
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
        "handout_block_refs",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("handout_block_id", ID_TYPE, nullable=False),
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
        sa.ForeignKeyConstraint(["handout_block_id"], ["handout_blocks.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["course_resources.id"]),
        sa.ForeignKeyConstraint(["segment_id"], ["course_segments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("handout_block_id", "sort_no", name="uq_handout_block_refs_block_sort"),
    )
    op.create_index(
        "ix_handout_block_refs_block_sort",
        "handout_block_refs",
        ["handout_block_id", "sort_no"],
    )
    op.create_index("ix_handout_block_refs_resource", "handout_block_refs", ["resource_id"])
    op.create_index("ix_handout_block_refs_segment", "handout_block_refs", ["segment_id"])


def downgrade() -> None:
    op.drop_index("ix_handout_block_refs_segment", table_name="handout_block_refs")
    op.drop_index("ix_handout_block_refs_resource", table_name="handout_block_refs")
    op.drop_index("ix_handout_block_refs_block_sort", table_name="handout_block_refs")
    op.drop_table("handout_block_refs")
