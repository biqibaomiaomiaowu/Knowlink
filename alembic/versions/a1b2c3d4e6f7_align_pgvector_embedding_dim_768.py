"""align pgvector embedding dimension 768

Revision ID: a1b2c3d4e6f7
Revises: 0a1b2c3d4e5f
Create Date: 2026-07-06 00:00:00.000000
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e6f7"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TARGET_EMBEDDING_DIM = 768
PREVIOUS_EMBEDDING_DIM = 1536


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    if _dialect_name() != "postgresql":
        _reset_failed_dimension_rows(PREVIOUS_EMBEDDING_DIM)
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _drop_hnsw_indexes()
    op.execute("ALTER TABLE vector_documents DROP COLUMN IF EXISTS embedding_vector")
    op.execute(f"ALTER TABLE vector_documents ADD COLUMN embedding_vector vector({TARGET_EMBEDDING_DIM})")
    _restore_json_embeddings(TARGET_EMBEDDING_DIM)
    _reset_unrestored_embeddings()
    _create_hnsw_indexes()


def downgrade() -> None:
    if _dialect_name() != "postgresql":
        _reset_failed_dimension_rows(TARGET_EMBEDDING_DIM)
        return

    _drop_hnsw_indexes()
    op.execute("ALTER TABLE vector_documents DROP COLUMN IF EXISTS embedding_vector")
    op.execute(f"ALTER TABLE vector_documents ADD COLUMN embedding_vector vector({PREVIOUS_EMBEDDING_DIM})")
    _restore_json_embeddings(PREVIOUS_EMBEDDING_DIM)
    _reset_unrestored_embeddings()
    _create_hnsw_indexes()


def _drop_hnsw_indexes() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vector_documents_embedding_vector_handout_block_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_vector_documents_embedding_vector_segment_hnsw")


def _create_hnsw_indexes() -> None:
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


def _restore_json_embeddings(dimension: int) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, embedding "
            "FROM vector_documents "
            "WHERE embedding IS NOT NULL AND embedding_dim = :dimension"
        ),
        {"dimension": dimension},
    ).mappings()
    for row in rows:
        embedding = _vector_literal(row["embedding"])
        if embedding is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE vector_documents "
                "SET embedding_vector = CAST(:embedding AS vector), "
                "embedding_status = 'ready', "
                "embedding_error = NULL "
                "WHERE id = :id"
            ),
            {"id": row["id"], "embedding": embedding},
        )


def _reset_unrestored_embeddings() -> None:
    op.execute(
        "UPDATE vector_documents "
        "SET embedding = NULL, "
        "embedding_model = NULL, "
        "embedding_dim = NULL, "
        "embedding_status = 'pending', "
        "embedding_error = NULL "
        "WHERE embedding_vector IS NULL "
        "AND embedding_status <> 'pending'"
    )


def _reset_failed_dimension_rows(previous_dimension: int) -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE vector_documents "
            "SET embedding_status = 'pending', "
            "embedding_error = NULL "
            "WHERE embedding_status = 'failed' "
            "AND embedding_error LIKE :expected_dimension"
        ),
        {"expected_dimension": f"%expected {previous_dimension}%"},
    )


def _vector_literal(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))
