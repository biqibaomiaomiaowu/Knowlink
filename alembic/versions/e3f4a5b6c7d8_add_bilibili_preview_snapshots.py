"""add bilibili preview snapshots

Revision ID: e3f4a5b6c7d8
Revises: a6c3d2f1e9b4
Create Date: 2026-05-19 00:00:02.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "a6c3d2f1e9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "bilibili_preview_snapshots",
        sa.Column("id", ID_TYPE, autoincrement=True, nullable=False),
        sa.Column("preview_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", ID_TYPE, nullable=False),
        sa.Column("course_id", ID_TYPE, nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("preview_json", JSON_TYPE, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bilibili_preview_snapshots_user_preview",
        "bilibili_preview_snapshots",
        ["user_id", "preview_id"],
        unique=True,
    )
    op.create_index(
        "ix_bilibili_preview_snapshots_course_user",
        "bilibili_preview_snapshots",
        ["course_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bilibili_preview_snapshots_course_user", table_name="bilibili_preview_snapshots")
    op.drop_index("ix_bilibili_preview_snapshots_user_preview", table_name="bilibili_preview_snapshots")
    op.drop_table("bilibili_preview_snapshots")
