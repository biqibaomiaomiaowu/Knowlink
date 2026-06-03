from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, TypeVar


T = TypeVar("T")


class IdempotencyRepository(Protocol):
    def get_idempotency_result(self, action: str, key: str | None) -> Any | None: ...

    def run_idempotent(self, action: str, key: str | None, factory: Callable[[], T]) -> T: ...

    def run_scoped_idempotent(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        factory: Callable[[], T],
    ) -> T: ...


class CourseRepository(Protocol):
    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
        exam_at: datetime | None = None,
    ) -> dict[str, Any]: ...

    def list_recent_courses(self) -> list[dict[str, Any]]: ...

    def list_courses(self, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]: ...

    def get_course(self, course_id: int) -> dict[str, Any] | None: ...

    def update_course(self, course_id: int, changes: Mapping[str, Any]) -> dict[str, Any] | None: ...

    def archive_course(self, course_id: int) -> dict[str, Any] | None: ...

    def restore_course(self, course_id: int) -> dict[str, Any] | None: ...

    def get_course_delete_impact(self, course_id: int) -> dict[str, Any] | None: ...

    def delete_course(self, course_id: int) -> dict[str, Any] | None: ...

    def set_current_course(self, course_id: int) -> dict[str, Any] | None: ...

    def get_current_course(self) -> dict[str, Any] | None: ...


class ResourceRepository(Protocol):
    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...

    def list_resources(self, course_id: int) -> list[dict[str, Any]]: ...

    def get_resource(self, resource_id: int) -> dict[str, Any] | None: ...

    def get_resource_delete_blockers(self, course_id: int, resource_id: int) -> dict[str, int]: ...

    def delete_resource(self, course_id: int, resource_id: int) -> bool: ...

    def update_resource_scope(
        self,
        *,
        course_id: int,
        resource_id: int,
        scope_type: str,
        lesson_id: int | None = None,
        usage_role: str | None = None,
    ) -> dict[str, Any] | None: ...


class LessonRepository(Protocol):
    def create_lesson(
        self,
        *,
        course_id: int,
        title: str,
        source_type: str = "manual",
        source_ref_json: dict[str, Any] | None = None,
        primary_video_resource_id: int | None = None,
        primary_video_start_sec: int | None = None,
        primary_video_end_sec: int | None = None,
        meta_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def list_lessons(self, course_id: int, *, include_deleted: bool = False) -> list[dict[str, Any]]: ...

    def get_lesson(
        self,
        *,
        course_id: int,
        lesson_id: int,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None: ...

    def reorder_lessons(self, *, course_id: int, lesson_ids: Sequence[int]) -> list[dict[str, Any]]: ...

    def soft_delete_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, Any]: ...

    def update_lesson(
        self,
        *,
        course_id: int,
        lesson_id: int,
        changes: Mapping[str, Any],
    ) -> dict[str, Any] | None: ...


class ScopedArtifactRepository(Protocol):
    def create_scoped_artifact(
        self,
        *,
        artifact_type: str,
        course_id: int,
        scope_type: str,
        lesson_id: int | None = None,
        start_lesson_id: int | None = None,
        end_lesson_id: int | None = None,
        status: str = "placeholder",
        **extra: Any,
    ) -> dict[str, Any]: ...

    def list_lesson_artifacts(self, *, course_id: int, lesson_id: int) -> list[dict[str, Any]]: ...

    def mark_lesson_artifacts_stale(
        self,
        *,
        course_id: int,
        lesson_ids: Sequence[int],
    ) -> list[dict[str, Any]]: ...


class ParseRunRepository(Protocol):
    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None: ...

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None: ...


class AsyncTaskRepository(Protocol):
    def create_async_task(
        self,
        *,
        course_id: int,
        task_type: str,
        status: str = "queued",
        progress_pct: int = 0,
        payload_json: dict[str, Any] | None = None,
        parse_run_id: int | None = None,
        parent_task_id: int | None = None,
        target_type: str | None = None,
        target_id: int | None = None,
        step_code: str | None = None,
    ) -> dict[str, Any]: ...

    def get_async_task(self, task_id: int) -> dict[str, Any] | None: ...

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]: ...

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        payload_json: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        clear_error: bool = False,
    ) -> dict[str, Any] | None: ...


class BilibiliImportRepository(Protocol):
    def create_bilibili_qr_session(
        self,
        *,
        qr_key: str,
        qr_url: str,
        status: str = "pending_scan",
        poll_payload_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]: ...

    def get_bilibili_qr_session(self, qr_key: str) -> dict[str, Any] | None: ...

    def update_bilibili_qr_session(
        self,
        qr_key: str,
        **changes: Any,
    ) -> dict[str, Any] | None: ...

    def save_bilibili_auth_session(
        self,
        *,
        cookies_json: dict[str, Any],
        csrf: str | None = None,
        expires_at: datetime | None = None,
        status: str = "active",
    ) -> dict[str, Any]: ...

    def get_bilibili_auth_session(self) -> dict[str, Any] | None: ...

    def delete_bilibili_auth_session(self) -> bool: ...

    def save_bilibili_preview_snapshot(
        self,
        *,
        preview_id: str,
        course_id: int,
        source_url: str,
        source_type: str,
        preview: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> dict[str, Any]: ...

    def get_bilibili_preview_snapshot(self, preview_id: str) -> dict[str, Any] | None: ...

    def create_bilibili_import_run(
        self,
        *,
        course_id: int,
        source_url: str,
        source_type: str,
        preview: dict[str, Any] | None = None,
        selection: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def get_bilibili_import_run(self, import_run_id: int) -> dict[str, Any] | None: ...

    def list_bilibili_import_runs(self, course_id: int) -> list[dict[str, Any]]: ...

    def update_bilibili_import_run(
        self,
        import_run_id: int,
        **changes: Any,
    ) -> dict[str, Any] | None: ...

    def upsert_bilibili_import_item(
        self,
        *,
        import_run_id: int,
        course_id: int,
        source_url: str,
        item_key: str | None = None,
        title: str | None = None,
        part_no: int | None = None,
        status: str = "pending",
        progress_pct: int = 0,
        lesson_id: int | None = None,
        resource_id: int | None = None,
        metadata_json: dict[str, Any] | None = None,
        error_code: str | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any]: ...

    def list_bilibili_import_items(self, import_run_id: int) -> list[dict[str, Any]]: ...


class TaskDispatcher(Protocol):
    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None: ...

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None: ...

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None: ...

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None: ...

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None: ...

    def enqueue_bilibili_import(self, *, task_id: int, payload: dict[str, Any]) -> None: ...


class InquiryRepository(Protocol):
    def save_inquiry_answers(
        self,
        course_id: int,
        answers: Sequence[dict[str, Any]],
    ) -> dict[str, Any]: ...


class HandoutRepository(Protocol):
    def get_handout_outline_context(self, course_id: int) -> dict[str, Any] | None: ...

    def create_handout(
        self,
        course_id: int,
        *,
        outline: dict[str, Any] | None = None,
        outline_meta: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]: ...

    def get_handout(self, handout_version_id: int) -> dict[str, Any] | None: ...

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None: ...

    def get_latest_outline(self, course_id: int) -> dict[str, Any] | None: ...

    def get_block_jump_target(self, block_id: int) -> dict[str, Any] | None: ...

    def save_handout_block_result(
        self,
        block_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def prepare_handout_block_generation(
        self,
        block_id: int,
    ) -> tuple[dict[str, Any], tuple[int, dict[str, Any]] | None] | None: ...

    def get_handout_block_status(self, block_id: int) -> dict[str, Any] | None: ...

    def get_current_handout_block(self, course_id: int, current_sec: int) -> dict[str, Any] | None: ...


class QaRepository(Protocol):
    def get_qa_context(self, course_id: int, handout_block_id: int) -> dict[str, Any] | None: ...

    def save_qa_exchange(
        self,
        context: dict[str, Any],
        question: str,
        response: dict[str, Any],
        refs: list[dict[str, Any]],
        candidate_count: int,
    ) -> dict[str, Any]: ...

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]] | None: ...

    def list_scoped_qa_sessions(
        self,
        *,
        course_id: int,
        scope_type: str,
        lesson_id: int | None = None,
    ) -> list[dict[str, Any]]: ...

    def create_scoped_qa_exchange(
        self,
        *,
        course_id: int,
        scope_type: str,
        lesson_id: int | None,
        question: str,
        answer_md: str,
        citations: Sequence[dict[str, Any]],
        session_id: int | None = None,
    ) -> dict[str, Any]: ...


class QuizRepository(Protocol):
    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None: ...

    def get_quiz_submission_context(self, quiz_id: int) -> dict[str, Any] | None: ...

    def save_quiz_attempt_result(
        self,
        quiz_id: int,
        *,
        quiz_attempt_result: dict[str, Any],
        mastery_updates: Sequence[dict[str, Any]],
    ) -> dict[str, Any]: ...


class ReviewRepository(Protocol):
    def next_task_id(self) -> int: ...

    def create_review_run(self, course_id: int) -> dict[str, Any]: ...

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]: ...

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None: ...

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]: ...


class DashboardRepository(Protocol):
    def list_daily_recommended_knowledge_points(self, *, limit: int = 3) -> list[dict[str, Any]]: ...

    def get_learning_stats(self) -> dict[str, Any]: ...


class ProgressRepository(Protocol):
    def get_progress(self, course_id: int) -> dict[str, Any]: ...

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...


class LessonProgressRepository(Protocol):
    def upsert_user_lesson_progress(
        self,
        *,
        course_id: int,
        lesson_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def get_user_lesson_progress(self, *, course_id: int, lesson_id: int) -> dict[str, Any] | None: ...
