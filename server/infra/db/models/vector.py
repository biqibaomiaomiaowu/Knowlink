from __future__ import annotations

from typing import ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


EMBEDDING_DIM = 1536
VECTOR_TYPE = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class VectorDocument(Base, TimestampMixin):
    __tablename__ = "vector_documents"
    EMBEDDING_DIM: ClassVar[int] = EMBEDDING_DIM
    __table_args__ = (
        Index("ix_vector_documents_course_parse", "course_id", "parse_run_id"),
        Index(
            "ix_vector_documents_course_parse_owner",
            "course_id",
            "parse_run_id",
            "owner_type",
            "owner_id",
        ),
        Index(
            "ix_vector_documents_course_parse_handout_owner",
            "course_id",
            "parse_run_id",
            "handout_version_id",
            "owner_type",
            "owner_id",
        ),
        Index("ix_vector_documents_owner", "owner_type", "owner_id"),
        Index("ix_vector_documents_resource", "resource_id"),
        Index("ix_vector_documents_embedding_status", "embedding_status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    parse_run_id: Mapped[int | None] = mapped_column(ForeignKey("parse_runs.id"), nullable=True)
    handout_version_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    embedding_vector: Mapped[list[float] | None] = mapped_column(VECTOR_TYPE, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
