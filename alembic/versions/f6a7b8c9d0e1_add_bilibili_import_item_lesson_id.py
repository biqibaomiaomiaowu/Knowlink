"""add bilibili import item lesson id

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-02 00:00:02.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


ID_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("bilibili_import_items") as batch:
        batch.add_column(sa.Column("lesson_id", ID_TYPE, nullable=True))
        batch.create_foreign_key(
            "fk_bilibili_import_items_lesson_id_course_lessons",
            "course_lessons",
            ["lesson_id"],
            ["id"],
        )
    op.create_index(
        "ix_bilibili_import_items_course_lesson",
        "bilibili_import_items",
        ["course_id", "lesson_id"],
        unique=False,
    )
    op.create_index(
        "ix_bilibili_import_items_run_item_key",
        "bilibili_import_items",
        ["import_run_id", "item_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_bilibili_import_items_run_item_key", table_name="bilibili_import_items")
    op.drop_index("ix_bilibili_import_items_course_lesson", table_name="bilibili_import_items")
    with op.batch_alter_table("bilibili_import_items") as batch:
        batch.drop_constraint("fk_bilibili_import_items_lesson_id_course_lessons", type_="foreignkey")
        batch.drop_column("lesson_id")
