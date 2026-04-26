from sqlalchemy import String, BigInteger, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func
class AsyncTask(Base):
    __tablename__ = "async_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    course_id: Mapped[int] = mapped_column(BigInteger)
    parse_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    task_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="queued")

    progress_pct: Mapped[int] = mapped_column(Integer, default=0)

    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at :Mapped[datetime] = mapped_column(server_default=func.now())