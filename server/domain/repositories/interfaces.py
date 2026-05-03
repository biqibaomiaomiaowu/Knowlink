from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar


T = TypeVar("T")


class IdempotencyRepository(Protocol):
    def run_idempotent(self, action: str, key: str | None, factory: Callable[[], T]) -> T: ...


class CourseRepository(Protocol):
    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
    ) -> dict[str, Any]: ...

    def list_recent_courses(self) -> list[dict[str, Any]]: ...

    def get_course(self, course_id: int) -> dict[str, Any] | None: ...


class ResourceRepository(Protocol):
    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...

    def list_resources(self, course_id: int) -> list[dict[str, Any]]: ...

    def delete_resource(self, course_id: int, resource_id: int) -> bool: ...


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
        error_message: str | None = None,
    ) -> dict[str, Any] | None: ...


class TaskDispatcher(Protocol):
    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None: ...


class InquiryRepository(Protocol):
    def save_inquiry_answers(
        self,
        course_id: int,
        answers: Sequence[dict[str, Any]],
    ) -> dict[str, Any]: ...


class HandoutRepository(Protocol):
    def create_handout(
        self,
        course_id: int,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]: ...

    def get_handout(self, handout_version_id: int) -> dict[str, Any] | None: ...

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None: ...

    def get_block_jump_target(self, block_id: int) -> dict[str, Any] | None: ...


class QaRepository(Protocol):
    def create_qa_message(self, course_id: int, handout_block_id: int) -> dict[str, Any]: ...

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]] | None: ...


class QuizRepository(Protocol):
    def create_quiz(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]: ...

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None: ...

    def submit_quiz(self, quiz_id: int) -> dict[str, Any]: ...


class ReviewRepository(Protocol):
    def next_task_id(self) -> int: ...

    def create_review_run(self, course_id: int) -> dict[str, Any]: ...

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]: ...

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None: ...

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]: ...


class ProgressRepository(Protocol):
    def get_progress(self, course_id: int) -> dict[str, Any]: ...

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]: ...
