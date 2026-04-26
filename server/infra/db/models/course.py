from sqlalchemy import String, Text, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func
class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(BigInteger)

    title: Mapped[str] = mapped_column(String(255))
    entry_type: Mapped[str] = mapped_column(String(50))  # recommendation / manual_import

    goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    lifecycle_status: Mapped[str] = mapped_column(String(50), default="draft")
    pipeline_stage: Mapped[str] = mapped_column(String(50), default="idle")
    pipeline_status: Mapped[str] = mapped_column(String(50), default="idle")

    active_parse_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())