from __future__ import annotations

<<<<<<< HEAD
from sqlalchemy import BigInteger, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from server.infra.db.base import Base
from typing import Optional


class VectorDocument(Base):
    __tablename__ = "vector_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"), index=True)

    # 存储原始文本或讲义块内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 向量字段：m3e-base 向量维度 768
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(768), nullable=True)

    # 元数据
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False)
=======
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
>>>>>>> main
