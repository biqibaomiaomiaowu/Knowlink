"""add bilibili import recovery fields

Revision ID: a6c3d2f1e9b4
Revises: 9f42a7d8c6b1
Create Date: 2026-05-19 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c3d2f1e9b4"
down_revision: Union[str, Sequence[str], None] = "9f42a7d8c6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bilibili_import_runs",
        sa.Column("recoverable", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "bilibili_import_runs",
        sa.Column("temp_dir", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bilibili_import_runs", "temp_dir")
    op.drop_column("bilibili_import_runs", "recoverable")
