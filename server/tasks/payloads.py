from __future__ import annotations

from typing import Literal

from server.schemas.base import CamelModel


class ParsePipelinePayload(CamelModel):
    course_id: int
    parse_run_id: int
    resource_types: list[Literal["mp4", "pdf", "pptx", "docx", "srt"]]


class HandoutGeneratePayload(CamelModel):
    course_id: int
    handout_version_id: int
    source_parse_run_id: int


class HandoutBlockGeneratePayload(CamelModel):
    course_id: int
    handout_version_id: int
    handout_block_id: int
    source_parse_run_id: int


class QuizGeneratePayload(CamelModel):
    course_id: int
    quiz_id: int
    handout_version_id: int | None = None
    source_parse_run_id: int | None = None


class ReviewRefreshPayload(CamelModel):
    course_id: int
    review_task_run_id: int | None = None


TASK_PAYLOAD_MODELS = {
    "parse_pipeline": ParsePipelinePayload,
    "handout_generate": HandoutGeneratePayload,
    "handout_block_generate": HandoutBlockGeneratePayload,
    "quiz_generate": QuizGeneratePayload,
    "review_refresh": ReviewRefreshPayload,
}
