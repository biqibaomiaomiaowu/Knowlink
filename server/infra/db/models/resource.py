from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func
class CourseResource(Base):
    __tablename__ = "course_resources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    course_id: Mapped[int] = mapped_column(BigInteger)

    resource_type: Mapped[str] = mapped_column(String(20))  # mp4/pdf/pptx/docx
    object_key: Mapped[str] = mapped_column(String(255))

    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))

    ingest_status: Mapped[str] = mapped_column(String(50), default="pending")
    validation_status: Mapped[str] = mapped_column(String(50), default="pending")
    processing_status: Mapped[str] = mapped_column(String(50), default="pending")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())