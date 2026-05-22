"""extend idempotency records

Revision ID: 9c2f4a1d7b30
Revises: 4a6c1d9e8b20
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9c2f4a1d7b30"
down_revision: Union[str, Sequence[str], None] = "4a6c1d9e8b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("idempotency_records") as batch:
        batch.add_column(sa.Column("scope", sa.String(length=160), nullable=True))
        batch.add_column(sa.Column("request_hash", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="succeeded")
        )
        batch.add_column(sa.Column("http_status", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("response_json", JSON_TYPE, nullable=True))
        batch.add_column(sa.Column("error_code", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint("uq_idempotency_records_scope_key", ["scope", "key"])
        batch.create_index("ix_idempotency_records_expires_at", ["expires_at"])


def downgrade() -> None:
    with op.batch_alter_table("idempotency_records") as batch:
        batch.drop_index("ix_idempotency_records_expires_at")
        batch.drop_constraint("uq_idempotency_records_scope_key", type_="unique")
        batch.drop_column("expires_at")
        batch.drop_column("error_code")
        batch.drop_column("response_json")
        batch.drop_column("http_status")
        batch.drop_column("status")
        batch.drop_column("request_hash")
        batch.drop_column("scope")
