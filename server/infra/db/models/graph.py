from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class GraphSnapshot(Base, TimestampMixin):
    __tablename__ = "graph_snapshots"
    __table_args__ = (
        Index("ix_graph_snapshots_course_scope", "course_id", "scope_type", "lesson_id"),
        Index("ix_graph_snapshots_course_status", "course_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), default="course", nullable=False)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("course_lessons.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="placeholder", nullable=False)
    nodes_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    edges_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    citations_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    meta_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
