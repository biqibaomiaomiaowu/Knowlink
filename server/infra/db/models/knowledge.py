from sqlalchemy import String, Text, Integer, BigInteger, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from server.infra.db.base import Base

class KnowledgePoint(Base):
    """
    知识点目录表
    """
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"), nullable=False)
    
    knowledge_point_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    difficulty_level: Mapped[Optional[str]] = mapped_column(String(50))
    importance_score: Mapped[Optional[int]] = mapped_column(Integer)

class SegmentKnowledgePoint(Base):
    """
    片段与知识点的多对多关联
    """
    __tablename__ = "segment_knowledge_points"

    segment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course_segments.id"), primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_points.id"), primary_key=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)

class KnowledgePointEvidence(Base):
    """
    知识点证据清单
    """
    __tablename__ = "knowledge_point_evidences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    knowledge_point_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_points.id"), nullable=False)
    segment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("course_segments.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50)) # definition, example, etc.
    sort_no: Mapped[int] = mapped_column(Integer, default=0)