from sqlalchemy import String, BigInteger, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func


class AsyncTask(Base):
    __tablename__ = "async_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # 归属
    course_id: Mapped[int] = mapped_column(BigInteger)
    parse_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 任务层级（关键！）
    parent_task_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("async_tasks.id"), nullable=True
    )

    # 类型 & 状态
    task_type: Mapped[str] = mapped_column(String(100))  # parse_pipeline / doc_parse ...
    status: Mapped[str] = mapped_column(String(50), default="queued")

    # 进度 & 阶段
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    step_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 输入输出
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 错误
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 时间
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)