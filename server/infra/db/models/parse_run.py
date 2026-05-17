<<<<<<< HEAD
from sqlalchemy import String, BigInteger, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
=======
from __future__ import annotations

>>>>>>> main
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class ParseRun(Base, TimestampMixin):
    __tablename__ = "parse_runs"
    __table_args__ = (
        Index("ix_parse_runs_course_created", "course_id", "created_at"),
        Index("ix_parse_runs_course_status", "course_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)

<<<<<<< HEAD
    #  增加外键关联，确保数据一致性
    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"), index=True)

    # 状态机字段：queued -> running -> succeeded/failed
    status: Mapped[str] = mapped_column(String(50), default="queued")
    
    # 增加 pipeline_stage 以支持“视频优先”逻辑[cite: 8]
    pipeline_stage: Mapped[str] = mapped_column(String(50), nullable=True)

    # 增加错误信息记录，方便 worker 报错时反馈给前端
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    trigger_type: Mapped[str] = mapped_column(String(50), default="user_action")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
=======
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="user_action", nullable=False)
    source_parse_run_id: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)

    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
>>>>>>> main
