from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class VectorDocument(Base, TimestampMixin):
    __tablename__ = "vector_documents"
    __table_args__ = (
        Index("ix_vector_documents_course_parse", "course_id", "parse_run_id"),
        Index("ix_vector_documents_owner", "owner_type", "owner_id"),
        Index("ix_vector_documents_resource", "resource_id"),
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
