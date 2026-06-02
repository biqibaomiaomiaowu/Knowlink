from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

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


class UpdateCourseRequest(CamelModel):
    title: str | None = None
    goal_text: str | None = None
    exam_at: datetime | None = None
    preferred_style: Literal["balanced", "exam", "detailed", "quick"] | None = None

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


class BilibiliPreviewRequest(CamelModel):
    source_url: str = Field(min_length=1)


class BilibiliImportRequest(CamelModel):
    preview_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    selection_mode: Literal["current_part", "all_parts", "selected_parts"] = "current_part"
    selected_part_ids: list[str] = Field(default_factory=list)
    quality_preference: Literal["android_safe"] = "android_safe"

    @field_validator("selected_part_ids")
    @classmethod
    def _clean_selected_part_ids(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def _selected_parts_must_include_ids(self) -> BilibiliImportRequest:
        if self.selection_mode == "selected_parts" and not self.selected_part_ids:
            raise ValueError("selectedPartIds is required when selectionMode is selected_parts.")
        return self


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
