"""add handout block generation metadata

Revision ID: 4a6c1d9e8b20
Revises: 2f5c9f6a8b10
Create Date: 2026-05-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "4a6c1d9e8b20"
down_revision: Union[str, Sequence[str], None] = "2f5c9f6a8b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "handout_blocks",
        sa.Column("generation_metadata_json", JSON_TYPE, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("handout_blocks", "generation_metadata_json")
