from sqlalchemy import String, Text, Integer, BigInteger, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
from server.infra.db.base import Base
from sqlalchemy import func

class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(255))
    entry_type: Mapped[str] = mapped_column(String(50))  # recommendation / manual_import
    goal_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lifecycle_status: Mapped[str] = mapped_column(String(50), default="draft")
    pipeline_stage: Mapped[str] = mapped_column(String(50), default="idle")
    pipeline_status: Mapped[str] = mapped_column(String(50), default="idle")

    active_parse_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    active_handout_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # 关系映射
    segments: Mapped[List["CourseSegment"]] = relationship("CourseSegment", back_populates="course")


class CourseSegment(Base):
    """
    课程内容片段模型
    严格对应 schemas/parse/normalized_document.schema.json
    """
    __tablename__ = "course_segments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"), nullable=False)
    
    # 通用必填字段
    segment_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    segment_type: Mapped[str] = mapped_column(String(50), nullable=False) 
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)

    # 资源特定定位字段
    page_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)        # PDF
    slide_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)       # PPTX
    start_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)      # Video
    end_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)        # Video
    section_path: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)     # DOCX
    anchor_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) # DOCX

    course: Mapped["Course"] = relationship("Course", back_populates="segments")


class LearningPreference(Base):
    """
    用户学习偏好
    """
    __tablename__ = "learning_preferences"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"), primary_key=True)
    
    goal_type: Mapped[Optional[str]] = mapped_column(String(50))
    self_level: Mapped[Optional[str]] = mapped_column(String(50))
    preferred_style: Mapped[Optional[str]] = mapped_column(String(50))
    time_budget_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    
    confirmed_at: Mapped[datetime] = mapped_column(server_default=func.now())