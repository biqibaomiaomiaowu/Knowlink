from __future__ import annotations

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