from __future__ import annotations

from typing import Literal

from server.schemas.base import CamelModel


class ParsePipelinePayload(CamelModel):
    course_id: int
    parse_run_id: int
    resource_types: list[Literal["mp4", "pdf", "pptx", "docx", "srt"]]


class HandoutGeneratePayload(CamelModel):
    course_id: int
    parse_run_id: int
    preferred_style: str


class QuizGeneratePayload(CamelModel):
    course_id: int
    handout_version_id: int


class ReviewRefreshPayload(CamelModel):
    course_id: int
    review_task_run_id: int | None = None


TASK_PAYLOAD_MODELS = {
    "parse_pipeline": ParsePipelinePayload,
    "handout_generate": HandoutGeneratePayload,
    "quiz_generate": QuizGeneratePayload,
    "review_refresh": ReviewRefreshPayload,
}
