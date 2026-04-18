from __future__ import annotations

from datetime import datetime

from server.schemas.base import CamelModel
from server.schemas.common import AsyncEntity, Citation, InquiryQuestionOption, ResourceManifestItem


class RecommendationCard(CamelModel):
    catalog_id: str
    title: str
    provider: str
    level: str
    estimated_hours: int
    fit_score: int
    reasons: list[str]
    default_resource_manifest: list[ResourceManifestItem]


class CourseSummary(CamelModel):
    course_id: int
    title: str
    entry_type: str
    catalog_id: str | None = None
    lifecycle_status: str
    pipeline_stage: str
    pipeline_status: str
    updated_at: datetime


class AsyncTriggerData(CamelModel):
    task_id: int
    status: str
    next_action: str
    entity: AsyncEntity


class PipelineCourseStatus(CamelModel):
    lifecycle_status: str
    pipeline_stage: str
    pipeline_status: str


class PipelineStatusData(CamelModel):
    course_status: PipelineCourseStatus
    progress_pct: int
    steps: list[dict[str, object]]
    active_parse_run_id: int | None = None
    active_handout_version_id: int | None = None
    next_action: str
    source_overview: dict[str, object] | None = None
    knowledge_map: dict[str, object] | None = None
    highlight_summary: dict[str, object] | None = None


class ParseRunData(CamelModel):
    parse_run_id: int
    course_id: int
    status: str
    progress_pct: int
    started_at: datetime
    finished_at: datetime | None = None


class InquiryQuestion(CamelModel):
    key: str
    label: str
    type: str
    required: bool
    options: list[InquiryQuestionOption] = []


class InquiryQuestionsData(CamelModel):
    version: int
    questions: list[InquiryQuestion]


class HandoutBlock(CamelModel):
    block_id: int
    title: str
    summary: str
    content_md: str
    start_sec: int | None = None
    end_sec: int | None = None
    page_from: int | None = None
    page_to: int | None = None
    slide_no: int | None = None
    anchor_key: str | None = None
    citations: list[Citation]


class HandoutStatusData(CamelModel):
    handout_version_id: int
    status: str
    total_blocks: int
    source_parse_run_id: int | None = None


class HandoutSummaryData(CamelModel):
    handout_version_id: int
    title: str
    summary: str
    total_blocks: int
    status: str


class HandoutBlocksData(CamelModel):
    items: list[HandoutBlock]


class JumpTargetData(CamelModel):
    block_id: int
    video_resource_id: int | None = None
    start_sec: int | None = None
    end_sec: int | None = None
    doc_resource_id: int | None = None
    page_no: int | None = None
    slide_no: int | None = None
    anchor_key: str | None = None


class QaMessageData(CamelModel):
    session_id: int
    message_id: int
    answer_md: str
    citations: list[Citation]


class QuizQuestion(CamelModel):
    question_id: int
    stem_md: str
    options: list[str]


class QuizData(CamelModel):
    quiz_id: int
    course_id: int
    status: str
    question_count: int
    questions: list[QuizQuestion]


class QuizStatusData(CamelModel):
    quiz_id: int
    status: str
    question_count: int


class SubmitQuizResult(CamelModel):
    attempt_id: int
    score: int
    total_score: int
    accuracy: float
    review_task_run_id: int
    mastery_delta: list[dict[str, object]] = []
    recommended_review_action: dict[str, object] | None = None


class ReviewTask(CamelModel):
    review_task_id: int
    task_type: str
    priority_score: int
    reason_text: str
    recommended_minutes: int
    recommended_segment: dict[str, object] | None = None
    practice_entry: dict[str, object] | None = None
    review_order: int | None = None
    intensity: str | None = None


class ReviewTasksData(CamelModel):
    items: list[ReviewTask]


class ReviewRunStatusData(CamelModel):
    review_task_run_id: int
    course_id: int
    status: str
    generated_count: int


class DashboardData(CamelModel):
    recent_courses: list[CourseSummary]
    top_review_tasks: list[ReviewTask]
    recommendation_entry_enabled: bool = True
    daily_recommended_knowledge_points: list[dict[str, object]] = []
    learning_stats: dict[str, object] | None = None


class ResourceStatusData(CamelModel):
    resource_id: int
    resource_type: str | None = None
    original_name: str | None = None
    object_key: str | None = None
    ingest_status: str
    validation_status: str
    processing_status: str


class ResourceListData(CamelModel):
    items: list[ResourceStatusData]


class UploadInitData(CamelModel):
    upload_url: str
    object_key: str
    headers: dict[str, str]
    expires_at: datetime


class SimpleSavedData(CamelModel):
    saved: bool
    answer_count: int
