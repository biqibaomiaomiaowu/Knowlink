"""merge idempotency and bilibili heads

Revision ID: c8d9e0f1a2b3
Revises: 9c2f4a1d7b30, b7c8d9e0f1a2
Create Date: 2026-05-22 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = ("9c2f4a1d7b30", "b7c8d9e0f1a2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
