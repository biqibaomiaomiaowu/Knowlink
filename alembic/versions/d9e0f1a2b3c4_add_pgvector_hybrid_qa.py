"""add pgvector hybrid qa

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-05-30 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = 1536
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    dialect_name = _dialect_name()
    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    with op.batch_alter_table("vector_documents") as batch_op:
        batch_op.add_column(sa.Column("embedding_model", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("embedding_dim", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "embedding_status",
                sa.String(length=50),
                server_default="pending",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("embedding_error", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("search_text", sa.Text(), server_default="", nullable=False)
        )

    if dialect_name == "postgresql":
        op.execute(
            "ALTER TABLE vector_documents ADD COLUMN "
            f"embedding_vector vector({EMBEDDING_DIM})"
        )
        op.execute(
            "ALTER TABLE vector_documents ADD COLUMN search_tsv tsvector "
            "GENERATED ALWAYS AS "
            "(to_tsvector('simple', coalesce(search_text, ''))) STORED"
        )
        op.execute(
            "CREATE INDEX ix_vector_documents_search_tsv_gin "
            "ON vector_documents USING gin (search_tsv)"
        )
        op.execute(
            "CREATE INDEX ix_vector_documents_embedding_vector_segment_hnsw "
            "ON vector_documents USING hnsw (embedding_vector vector_cosine_ops) "
            "WHERE owner_type = 'segment' AND embedding_vector IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX ix_vector_documents_embedding_vector_handout_block_hnsw "
            "ON vector_documents USING hnsw (embedding_vector vector_cosine_ops) "
            "WHERE owner_type = 'handout_block' AND embedding_vector IS NOT NULL"
        )
    else:
        with op.batch_alter_table("vector_documents") as batch_op:
            batch_op.add_column(sa.Column("embedding_vector", JSON_TYPE, nullable=True))
            batch_op.add_column(sa.Column("search_tsv", sa.Text(), nullable=True))

    op.create_index(
        "ix_vector_documents_course_parse_owner",
        "vector_documents",
        ["course_id", "parse_run_id", "owner_type", "owner_id"],
    )
    op.create_index(
        "ix_vector_documents_course_parse_handout_owner",
        "vector_documents",
        ["course_id", "parse_run_id", "handout_version_id", "owner_type", "owner_id"],
    )
    op.create_index(
        "ix_vector_documents_embedding_status",
        "vector_documents",
        ["embedding_status"],
    )


def downgrade() -> None:
    dialect_name = _dialect_name()
    op.drop_index("ix_vector_documents_embedding_status", table_name="vector_documents")
    op.drop_index(
        "ix_vector_documents_course_parse_handout_owner",
        table_name="vector_documents",
    )
    op.drop_index("ix_vector_documents_course_parse_owner", table_name="vector_documents")

    if dialect_name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_vector_documents_embedding_vector_handout_block_hnsw")
        op.execute("DROP INDEX IF EXISTS ix_vector_documents_embedding_vector_segment_hnsw")
        op.execute("DROP INDEX IF EXISTS ix_vector_documents_search_tsv_gin")

    with op.batch_alter_table("vector_documents") as batch_op:
        batch_op.drop_column("search_tsv")
        batch_op.drop_column("search_text")
        batch_op.drop_column("embedding_error")
        batch_op.drop_column("embedding_status")
        batch_op.drop_column("embedding_dim")
        batch_op.drop_column("embedding_model")
        batch_op.drop_column("embedding_vector")
