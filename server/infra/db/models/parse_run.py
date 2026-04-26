from sqlalchemy import String, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func
class ParseRun(Base):
    __tablename__ = "parse_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    course_id: Mapped[int] = mapped_column(BigInteger)

    status: Mapped[str] = mapped_column(String(50), default="queued")
    trigger_type: Mapped[str] = mapped_column(String(50), default="user_action")

    progress_pct: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())