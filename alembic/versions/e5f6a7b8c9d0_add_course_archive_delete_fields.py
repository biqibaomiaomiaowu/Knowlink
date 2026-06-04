"""add course archive and delete fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-02 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("courses") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_courses_user_archived", "courses", ["user_id", "archived_at"], unique=False)
    op.create_index("ix_courses_user_deleted", "courses", ["user_id", "deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_courses_user_deleted", table_name="courses")
    op.drop_index("ix_courses_user_archived", table_name="courses")
    with op.batch_alter_table("courses") as batch:
        batch.drop_column("deleted_at")
        batch.drop_column("archived_at")
