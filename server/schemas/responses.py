from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

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
    reason_materials: list[str] = Field(default_factory=list)
    next_action: dict[str, object] | None = None
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


class CourseLibraryItem(CamelModel):
    course_id: int
    title: str
    is_current: bool = False
    entry_type: str
    learning_status: str
    last_activity_at: datetime | None = None
    lesson_count: int = 0
    course_resource_count: int = 0
    current_lesson_id: int | None = None
    current_lesson_title: str | None = None
    overall_mastery_score: float | None = None
    pending_review_count: int = 0
    pipeline_stage: str
    pipeline_status: str
    lifecycle_status: str
    archived_at: datetime | None = None


class CourseQuickEntry(CamelModel):
    key: str
    title: str
    status: str
    enabled: bool = True
    target: str | None = None


class CourseProgressSummary(CamelModel):
    lesson_count: int = 0
    completed_lesson_count: int = 0
    resource_count: int = 0
    course_resource_count: int = 0
    lesson_resource_count: int = 0
    overall_mastery_score: float | None = None
    pending_review_count: int = 0
    completion_percent: int = 0
    last_activity_at: datetime | None = None


class CourseDeleteImpactData(CamelModel):
    course_id: int
    can_delete: bool
    blocker_count: int
    blockers: dict[str, int]


class CourseWorkbenchData(CamelModel):
    course: dict[str, object]
    progress: CourseProgressSummary
    current_lesson: dict[str, object] | None = None
    lessons: list[dict[str, object]]
    course_resources: list[dict[str, object]]
    quick_entries: list[CourseQuickEntry]
    next_actions: list[dict[str, object]] = Field(default_factory=list)
    placeholder_states: dict[str, dict[str, object]] = Field(default_factory=dict)


class LessonSummary(CamelModel):
    lesson_id: int
    course_id: int
    title: str
    order_index: int
    lesson_status: str
    primary_video_resource_id: int | None = None
    primary_video_start_sec: int | None = None
    primary_video_end_sec: int | None = None
    handout_status: str
    quiz_status: str
    review_status: str
    mastery_score: float | None = None
    last_position_sec: int | None = None
    last_activity_at: datetime | None = None
    next_action: dict[str, object] | None = None


class LessonArtifactSummary(CamelModel):
    artifact_id: int
    artifact_type: str
    scope_type: str
    lesson_id: int | None = None
    status: str


class LessonProgressSummary(CamelModel):
    last_position_sec: int | None = None
    last_handout_block_id: int | None = None
    handout_read_percent: int = 0
    quiz_status: str = "not_generated"
    review_status: str = "not_due"
    last_activity_at: datetime | None = None


class LessonSourceOverview(CamelModel):
    scope_type: str = "lesson"
    lesson_id: int | None = None
    resource_count: int
    primary_video_resource_id: int | None = None
    has_primary_video: bool = False
    lesson_resource_count: int = 0
    course_resource_count: int = 0


class LessonDetailData(CamelModel):
    lesson: LessonSummary
    primary_video: dict[str, object] | None = None
    lesson_resources: list[dict[str, object]]
    artifact_summaries: list[LessonArtifactSummary]
    progress: LessonProgressSummary
    citations: list[dict[str, object]]
    source_overview: LessonSourceOverview
    knowledge_point_placeholders: list[dict[str, object]]
    weakness_placeholders: list[dict[str, object]]
    next_action: dict[str, object] | None = None


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
    handout_version_id: int | None = None
    outline_key: str | None = None
    title: str
    summary: str
    status: str | None = None
    content_md: str | None = None
    start_sec: int | None = None
    end_sec: int | None = None
    source_segment_keys: list[str] = []
    knowledge_points: list[dict[str, object]] = []
    page_from: int | None = None
    page_to: int | None = None
    slide_no: int | None = None
    anchor_key: str | None = None
    citations: list[Citation]
    generation_metadata: dict[str, object] | None = None


class HandoutOutlineChild(CamelModel):
    outline_key: str
    block_id: int | None = None
    title: str
    summary: str
    start_sec: int
    end_sec: int
    sort_no: int
    generation_status: str
    source_segment_keys: list[str]
    topic_tags: list[str] = []


class HandoutOutlineSection(CamelModel):
    outline_key: str
    title: str
    summary: str
    start_sec: int
    end_sec: int
    sort_no: int
    children: list[HandoutOutlineChild]


class HandoutOutlineData(CamelModel):
    handout_version_id: int
    title: str
    summary: str
    items: list[HandoutOutlineSection]


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
    answer_type: str | None = None
    citations: list[Citation]
    generation_metadata: dict[str, object] | None = None


class ScopedHandoutPlaceholderData(CamelModel):
    scope_type: Literal["course", "lesson"]
    lesson_id: int | None = None
    artifact_kind: Literal["lesson_handout", "course_summary_handout"]
    status: Literal["not_generated", "generating", "ready", "partial_success", "failed", "stale", "placeholder"]
    can_generate: bool
    required_sources: list[str]
    message: str
    available_actions: list[str]
    citations: list[Citation] = Field(default_factory=list)


class QaSessionSummary(CamelModel):
    session_id: int
    course_id: int
    scope_type: Literal["course", "lesson"]
    lesson_id: int | None = None
    title: str | None = None
    last_message_at: datetime | None = None


class QaSessionListData(CamelModel):
    items: list[QaSessionSummary]


class ScopedQaMessageData(QaMessageData):
    course_id: int
    scope_type: Literal["course", "lesson"]
    lesson_id: int | None = None


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


class ScopedQuizData(CamelModel):
    quiz_id: int
    course_id: int
    scope_type: Literal["course", "lesson", "lesson_range"]
    lesson_id: int | None = None
    start_lesson_id: int | None = None
    end_lesson_id: int | None = None
    quiz_mode: str = "objective"
    status: str
    question_count: int = 0
    questions: list[QuizQuestion] = Field(default_factory=list)


class SubjectiveGradingPlaceholderData(CamelModel):
    answer_text: str | None = None
    grading_status: Literal["placeholder", "not_submitted", "grading", "graded", "failed"] = "placeholder"
    total_score: int | None = None
    dimension_scores: list[dict[str, object]] = Field(default_factory=list)
    deductions: list[dict[str, object]] = Field(default_factory=list)
    feedback_md: str
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: float | None = None
    needs_human_review: bool = False


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
    scope_type: Literal["course", "lesson"] | None = None
    lesson_id: int | None = None
    knowledge_point_key: str | None = None
    source_question_keys: list[str] = Field(default_factory=list)
    recommended_handout_block: dict[str, object] | None = None
    evidence_chain: list[dict[str, object]] = Field(default_factory=list)
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


class ScopedReviewTasksData(CamelModel):
    scope_type: Literal["course", "lesson"]
    lesson_id: int | None = None
    status: str
    items: list[ReviewTask]
    weak_lessons: list[dict[str, object]] = Field(default_factory=list)
    cross_lesson_weak_points: list[dict[str, object]] = Field(default_factory=list)


class PlaceholderData(CamelModel):
    status: Literal["not_generated", "generating", "ready", "placeholder"] = "placeholder"
    scope_type: Literal["course", "lesson"]
    lesson_id: int | None = None
    message: str
    available_actions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class GraphNode(CamelModel):
    node_id: str
    label: str
    node_type: str


class GraphEdge(CamelModel):
    source_node_id: str
    target_node_id: str
    relation_type: str


class GraphPlaceholderData(PlaceholderData):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class ReportSummaryPlaceholderData(CamelModel):
    summary_status: Literal["placeholder"] = "placeholder"
    scope_type: Literal["course", "lesson"]
    course_id: int
    lesson_id: int | None = None
    metrics: list[dict[str, object]] = Field(default_factory=list)
    message: str


class ExportPlaceholderData(CamelModel):
    available_export_types: list[
        Literal["course_summary", "lesson_summary", "qa_transcript", "quiz_report", "review_plan"]
    ]
    status: Literal["placeholder"] = "placeholder"
    scope_type: Literal["course", "lesson"] = "course"
    course_id: int
    lesson_id: int | None = None
    export_type: str | None = None
    export_id: int | None = None
    download_url: str | None = None
    message: str


class ContinueLearningData(CamelModel):
    course_id: int
    lesson_id: int
    last_position_sec: int
    last_handout_block_id: int | None = None
    next_route: str
    next_action: dict[str, object]


class CourseRecommendationAction(CamelModel):
    type: str
    scope_type: str
    course_id: int
    lesson_id: int | None = None
    title: str
    reason: str
    reason_placeholders: dict[str, str] = Field(default_factory=dict)
    next_route: str


class CourseRecommendationListData(CamelModel):
    course_id: int
    scope_type: Literal["course", "lesson"]
    lesson_id: int | None = None
    items: list[CourseRecommendationAction]


class DashboardData(CamelModel):
    recent_courses: list[CourseSummary]
    top_review_tasks: list[ReviewTask]
    recommendation_entry_enabled: bool = True
    daily_recommended_knowledge_points: list[dict[str, object]] = []
    learning_stats: dict[str, object] | None = None
    current_course: dict[str, object] | None = None
    current_lesson: dict[str, object] | None = None
    continue_learning: ContinueLearningData | None = None
    next_step: dict[str, object] | None = None
    today_review_tasks: list[dict[str, object]] = Field(default_factory=list)
    recommended_next_lesson: dict[str, object] | None = None
    recommended_stage_quiz: dict[str, object] | None = None
    course_quick_entries: list[CourseQuickEntry] = Field(default_factory=list)


class ResourceStatusData(CamelModel):
    resource_id: int
    resource_type: str | None = None
    original_name: str | None = None
    object_key: str | None = None
    scope_type: Literal["course", "lesson"] | None = None
    lesson_id: int | None = None
    usage_role: str | None = None
    source_type: str | None = None
    source_part_id: str | None = None
    visible_to_course_qa: bool | None = None
    duration_sec: int | None = None
    ingest_status: str
    validation_status: str
    processing_status: str


class ResourceListData(CamelModel):
    items: list[ResourceStatusData]


class ResourcePlaybackData(CamelModel):
    resource_id: int
    resource_type: str
    playback_url: str
    mime_type: str
    expires_at: datetime
    duration_sec: int | None = None


class UploadInitData(CamelModel):
    upload_url: str
    object_key: str
    headers: dict[str, str]
    expires_at: datetime


class BilibiliPreviewPart(CamelModel):
    part_id: str
    title: str
    duration_sec: int
    cid: int
    page_no: int
    selected_by_default: bool
    lesson_id: int | None = None
    lesson_title: str | None = None


class BilibiliPreviewData(CamelModel):
    preview_id: str
    source_url: str
    source_type: Literal["single_video", "multi_p", "collection", "bangumi"]
    title: str
    cover_url: str | None = None
    total_parts: int
    parts: list[BilibiliPreviewPart]
    default_selection_mode: Literal["current_part", "all_parts", "selected_parts"]


BilibiliResponseStage = Literal[
    "queued",
    "metadata",
    "download",
    "ffmpeg",
    "object_storage",
    "resource_import",
    "done",
    "error",
    "canceling",
    "canceled",
]


BilibiliImportRunStatus = Literal[
    "pending",
    "fetching_metadata",
    "waiting_download",
    "downloading",
    "merging",
    "uploading",
    "imported",
    "failed",
    "recoverable",
    "canceled",
]


class BilibiliImportRunSummary(CamelModel):
    import_run_id: int
    course_id: int
    source_url: str
    source_type: Literal["single_video", "multi_p", "collection", "bangumi"]
    status: BilibiliImportRunStatus
    progress_pct: int
    stage: BilibiliResponseStage
    task_id: int | None = None
    resource_ids: list[int] = Field(default_factory=list)
    lesson_mode: Literal["auto_per_video", "bind_existing", "course_material"] | None = None
    target_lesson_id: int | None = None
    part_lesson_map: dict[str, dict[str, object]] = Field(default_factory=dict)
    items: list[dict[str, object]] = Field(default_factory=list)
    preview: BilibiliPreviewData | None = None
    next_action: str | None = None
    error_code: str | None = None
    failure_reason: str | None = None
    recoverable: bool = False


class BilibiliImportListData(CamelModel):
    items: list[BilibiliImportRunSummary]


class BilibiliImportRunStatusData(CamelModel):
    import_run_id: int
    course_id: int
    source_url: str
    source_type: Literal["single_video", "multi_p", "collection", "bangumi"]
    status: BilibiliImportRunStatus
    progress_pct: int
    stage: BilibiliResponseStage
    task_id: int | None = None
    resource_ids: list[int] = Field(default_factory=list)
    lesson_mode: Literal["auto_per_video", "bind_existing", "course_material"] | None = None
    target_lesson_id: int | None = None
    part_lesson_map: dict[str, dict[str, object]] = Field(default_factory=dict)
    items: list[dict[str, object]] = Field(default_factory=list)
    preview: BilibiliPreviewData | None = None
    next_action: str | None = None
    error_code: str | None = None
    failure_reason: str | None = None
    recoverable: bool = False


class BilibiliAuthQrSessionData(CamelModel):
    session_id: str
    status: str
    qr_code_url: str | None = None
    expires_at: datetime | None = None


class BilibiliAuthSessionData(CamelModel):
    login_status: str
    user_nickname: str | None = None
    expires_at: datetime | None = None


class BilibiliAuthSessionDeleteData(CamelModel):
    deleted: bool


class SimpleSavedData(CamelModel):
    saved: bool
    answer_count: int
