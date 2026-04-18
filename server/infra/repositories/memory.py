from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from server.infra.repositories.memory_runtime import RuntimeStore


T = TypeVar("T")


class MemoryScaffoldRepository:
    def __init__(self, store: RuntimeStore) -> None:
        self.store = store

    def run_idempotent(self, action: str, key: str | None, factory: Callable[[], T]) -> T:
        return self.store.run_idempotent(action, key, factory)

    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
    ) -> dict[str, Any]:
        return self.store.create_course(
            title=title,
            entry_type=entry_type,
            goal_text=goal_text,
            preferred_style=preferred_style,
            catalog_id=catalog_id,
        )

    def list_recent_courses(self) -> list[dict[str, Any]]:
        return self.store.list_recent_courses()

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        return self.store.get_course(course_id)

    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.create_resource(course_id, payload)

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.store.list_resources(course_id)

    def delete_resource(self, course_id: int, resource_id: int) -> bool:
        resources = self.store.list_resources(course_id)
        self.store.resources[course_id] = [
            item for item in resources if item["resourceId"] != resource_id
        ]
        return True

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.store.create_parse_run(course_id)

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return self.store.parse_runs.get(parse_run_id)

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        return self.store.get_latest_parse_run(course_id)

    def save_inquiry_answers(
        self,
        course_id: int,
        answers: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.store.save_inquiry_answers(course_id, list(answers))

    def create_handout(
        self,
        course_id: int,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        return self.store.create_handout(course_id)

    def get_handout(self, handout_version_id: int) -> dict[str, Any] | None:
        return self.store.handouts.get(handout_version_id)

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None:
        return self.store.get_latest_handout(course_id)

    def get_block_jump_target(self, block_id: int) -> dict[str, Any] | None:
        for handout in self.store.handouts.values():
            for block in handout["blocks"]:
                if block["blockId"] == block_id:
                    citation = block["citations"][0]
                    return {
                        "blockId": block_id,
                        "videoResourceId": 501,
                        "startSec": block.get("startSec"),
                        "endSec": block.get("endSec"),
                        "docResourceId": citation["resourceId"],
                        "pageNo": citation.get("pageNo"),
                        "slideNo": citation.get("slideNo"),
                        "anchorKey": citation.get("anchorKey"),
                    }
        return None

    def create_qa_message(self, course_id: int, handout_block_id: int) -> dict[str, Any]:
        return self.store.create_qa_message(course_id, handout_block_id)

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]] | None:
        return self.store.get_qa_session_messages(session_id)

    def create_quiz(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.store.create_quiz(course_id)

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None:
        return self.store.quizzes.get(quiz_id)

    def submit_quiz(self, quiz_id: int) -> dict[str, Any]:
        return self.store.submit_quiz(quiz_id)

    def next_task_id(self) -> int:
        return self.store.next_id("task")

    def create_review_run(self, course_id: int) -> dict[str, Any]:
        return self.store.create_review_run(course_id)

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        return self.store.list_review_tasks(course_id)

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None:
        return self.store.get_review_run(review_task_run_id)

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]:
        return {"reviewTaskId": review_task_id, "completed": True}

    def get_progress(self, course_id: int) -> dict[str, Any]:
        return self.store.get_progress(course_id)

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.update_progress(course_id, payload)
