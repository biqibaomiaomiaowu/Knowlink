"""merge pgvector and lesson heads

Revision ID: 0a1b2c3d4e5f
Revises: d9e0f1a2b3c4, f6a7b8c9d0e1
Create Date: 2026-06-03 00:00:00.000000
"""

from collections.abc import Sequence


revision: str = "0a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = ("d9e0f1a2b3c4", "f6a7b8c9d0e1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    return None


def downgrade() -> None:
    return None
