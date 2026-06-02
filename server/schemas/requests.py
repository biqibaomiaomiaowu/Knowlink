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


class CreateLessonRequest(CamelModel):
    title: str = Field(min_length=1)
    source_type: Literal[
        "manual",
        "local_video",
        "bilibili_part",
        "bilibili_collection_item",
        "bilibili_bangumi_item",
    ] = "manual"
    source_ref_json: dict[str, Any] | None = None
    primary_video_resource_id: int | None = None
    primary_video_start_sec: int | None = Field(default=None, ge=0)
    primary_video_end_sec: int | None = Field(default=None, ge=0)


class UpdateLessonRequest(CamelModel):
    title: str | None = Field(default=None, min_length=1)
    lesson_status: Literal[
        "draft",
        "resource_ready",
        "learning_ready",
        "completed",
        "stale",
    ] | None = None
    meta_json: dict[str, Any] | None = None


class ReorderLessonsRequest(CamelModel):
    lesson_ids: list[int]


class SetPrimaryVideoRequest(CamelModel):
    resource_id: int
    start_sec: int | None = Field(default=None, ge=0)
    end_sec: int | None = Field(default=None, ge=0)


class MergeLessonsRequest(CamelModel):
    lesson_ids: list[int]
    target_title: str | None = Field(default=None, min_length=1)


class SplitLessonRequest(CamelModel):
    split_at_sec: int = Field(ge=0)
    first_title: str | None = Field(default=None, min_length=1)
    second_title: str | None = Field(default=None, min_length=1)


class UploadInitRequest(CamelModel):
    resource_type: Literal["mp4", "pdf", "srt", "pptx", "docx"]
    filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    checksum: str
    scope_type: Literal["course", "lesson"] | None = None
    lesson_id: int | None = None
    usage_role: Literal[
        "course_material",
        "primary_video",
        "lesson_material",
        "transcript",
        "supplement",
    ] | None = None
    lesson_placement: Literal["auto_create", "bind_existing", "course_material"] | None = None
    lesson_title: str | None = Field(default=None, min_length=1)
    visible_to_course_qa: bool | None = None
    source_part_id: str | None = None
    duration_sec: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)


class UploadCompleteRequest(CamelModel):
    resource_type: Literal["mp4", "pdf", "srt", "pptx", "docx"]
    object_key: str
    original_name: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    checksum: str
    scope_type: Literal["course", "lesson"] | None = None
    lesson_id: int | None = None
    usage_role: Literal[
        "course_material",
        "primary_video",
        "lesson_material",
        "transcript",
        "supplement",
    ] | None = None
    lesson_placement: Literal["auto_create", "bind_existing", "course_material"] | None = None
    lesson_title: str | None = Field(default=None, min_length=1)
    visible_to_course_qa: bool | None = None
    source_part_id: str | None = None
    duration_sec: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)


class BilibiliPreviewRequest(CamelModel):
    source_url: str = Field(min_length=1)


class BilibiliImportRequest(CamelModel):
    preview_id: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    selection_mode: Literal["current_part", "all_parts", "selected_parts"] = "current_part"
    selected_part_ids: list[str] = Field(default_factory=list)
    quality_preference: Literal["android_safe"] = "android_safe"
    lesson_mode: Literal["auto_per_video", "bind_existing", "course_material"] = "auto_per_video"
    target_lesson_id: int | None = None
    part_lesson_titles: dict[str, str] = Field(default_factory=dict)
    part_lesson_map: dict[str, dict[str, int | str | None]] = Field(default_factory=dict)
    create_lesson_if_missing: bool = True

    @field_validator("selected_part_ids")
    @classmethod
    def _clean_selected_part_ids(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @field_validator("part_lesson_titles")
    @classmethod
    def _clean_part_lesson_titles(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            str(part_id).strip(): str(title).strip()
            for part_id, title in value.items()
            if str(part_id).strip() and str(title).strip()
        }

    @field_validator("part_lesson_map")
    @classmethod
    def _clean_part_lesson_map(cls, value: dict[str, dict[str, int | str | None]]) -> dict[str, dict[str, int | str | None]]:
        clean: dict[str, dict[str, int | str | None]] = {}
        for part_id, mapping in value.items():
            key = str(part_id).strip()
            if not key or not isinstance(mapping, dict):
                continue
            clean_mapping = {
                str(field).strip(): field_value
                for field, field_value in mapping.items()
                if str(field).strip() and field_value not in ("", [])
            }
            if clean_mapping:
                clean[key] = clean_mapping
        return clean

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
