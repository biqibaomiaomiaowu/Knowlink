from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from server.schemas.base import CamelModel


def _require_timezone_aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("examAt must include a timezone offset.")
    return value


class RecommendationRequest(CamelModel):
    goal_text: str
    self_level: Literal["beginner", "intermediate", "advanced"]
    time_budget_minutes: int = Field(ge=30)
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] = "balanced"

    @field_validator("exam_at")
    @classmethod
    def _exam_at_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone_aware(value)


class ConfirmRecommendationRequest(CamelModel):
    goal_text: str
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] = "balanced"
    title_override: str | None = None

    @field_validator("exam_at")
    @classmethod
    def _exam_at_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone_aware(value)


class CreateCourseRequest(CamelModel):
    title: str
    entry_type: Literal["manual_import", "recommendation"]
    goal_text: str
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] = "balanced"

    @field_validator("exam_at")
    @classmethod
    def _exam_at_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        return _require_timezone_aware(value)


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
    value: Any


class InquiryAnswersRequest(CamelModel):
    answers: list[InquiryAnswerItem]


class QaMessageRequest(CamelModel):
    course_id: int
    handout_block_id: int
    question: str


class QuizGenerateRequest(CamelModel):
    question_count_level: Literal["small", "medium", "large"] = "medium"


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
