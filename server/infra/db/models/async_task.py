<<<<<<< HEAD
from sqlalchemy import String, BigInteger, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func


class AsyncTask(Base):
=======
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class AsyncTask(Base, TimestampMixin):
>>>>>>> main
    __tablename__ = "async_tasks"
    __table_args__ = (
        Index("ix_async_tasks_parse_status", "parse_run_id", "status"),
        Index("ix_async_tasks_parent_status", "parent_task_id", "status"),
        Index("ix_async_tasks_course_type_status", "course_id", "task_type", "status"),
        Index("ix_async_tasks_course_target", "course_id", "target_type", "target_id"),
        Index("ix_async_tasks_resource_status", "resource_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)

<<<<<<< HEAD
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
=======
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    parse_run_id: Mapped[int | None] = mapped_column(ForeignKey("parse_runs.id"), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)

    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("async_tasks.id"), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    step_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    payload_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
>>>>>>> main
