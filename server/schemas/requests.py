from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from server.schemas.base import CamelModel


class RecommendationRequest(CamelModel):
    goal_text: str
    self_level: Literal["beginner", "intermediate", "advanced"]
    time_budget_minutes: int = Field(ge=30)
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] = "balanced"


class ConfirmRecommendationRequest(CamelModel):
    goal_text: str
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] = "balanced"
    title_override: str | None = None


class CreateCourseRequest(CamelModel):
    title: str
    entry_type: Literal["manual_import", "recommendation"]
    goal_text: str
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] = "balanced"


class UploadInitRequest(CamelModel):
    resource_type: Literal["mp4", "pdf", "srt", "pptx", "docx"]
    filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    checksum: str


class UploadCompleteRequest(CamelModel):
    resource_type: Literal["mp4", "pdf", "srt", "pptx", "docx"]
    object_key: str
    original_name: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    checksum: str


class BilibiliImportRequest(CamelModel):
    video_url: str | None = Field(
        default=None,
        description="预留的 B 站单视频链接。stub 阶段允许为空，正式接通后收紧为必填。",
    )


class InquiryAnswerItem(CamelModel):
    key: str
    value: str | int


class InquiryAnswersRequest(CamelModel):
    answers: list[InquiryAnswerItem]


class QaMessageRequest(CamelModel):
    course_id: int
    handout_block_id: int
    question: str


class QuizAnswerItem(CamelModel):
    question_id: int
    selected_option: str


class SubmitQuizRequest(CamelModel):
    answers: list[QuizAnswerItem]


class ProgressData(CamelModel):
    handout_version_id: int | None = None
    last_handout_block_id: int | None = None
    last_video_resource_id: int | None = None
    last_position_sec: int | None = None
    last_doc_resource_id: int | None = None
    last_page_no: int | None = None
    last_slide_no: int | None = None
    last_anchor_key: str | None = None
    last_activity_at: datetime | None = None
