"""add current course flag

Revision ID: b7c8d9e0f1a2
Revises: e3f4a5b6c7d8
Create Date: 2026-05-19 00:00:03.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(
        "ix_courses_user_current",
        "courses",
        ["user_id", "is_current"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_courses_user_current", table_name="courses")
    op.drop_column("courses", "is_current")
