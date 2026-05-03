from sqlalchemy import String, BigInteger, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from server.infra.db.base import Base
from sqlalchemy import func
class ParseRun(Base):
    __tablename__ = "parse_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

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