from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any, TypeVar

from server.infra.repositories.memory_runtime import RuntimeStore


T = TypeVar("T")


class MemoryScaffoldRepository:
    def __init__(self, store: RuntimeStore) -> None:
        self.store = store

    def run_idempotent(self, action: str, key: str | None, factory: Callable[[], T]) -> T:
        return self.store.run_idempotent(action, key, factory)

    def get_idempotency_result(self, action: str, key: str | None) -> Any | None:
        return self.store.get_idempotency_result(action, key)

    def run_scoped_idempotent(
        self,
        *,
        scope: str,
        key: str,
        request_hash: str,
        factory: Callable[[], T],
    ) -> T:
        return self.store.run_scoped_idempotent(
            scope=scope,
            key=key,
            request_hash=request_hash,
            factory=factory,
        )

    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
        exam_at: datetime | None = None,
    ) -> dict[str, Any]:
        return self.store.create_course(
            title=title,
            entry_type=entry_type,
            goal_text=goal_text,
            preferred_style=preferred_style,
            catalog_id=catalog_id,
            exam_at=exam_at,
        )

    def list_recent_courses(self) -> list[dict[str, Any]]:
        return self.store.list_recent_courses()

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        return self.store.get_course(course_id)

    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.create_resource(course_id, payload)

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.store.list_resources(course_id)

    def get_resource(self, resource_id: int) -> dict[str, Any] | None:
        return self.store.get_resource(resource_id)

    def get_resource_delete_blockers(self, course_id: int, resource_id: int) -> dict[str, int]:
        return {}

    def delete_resource(self, course_id: int, resource_id: int) -> bool:
        resources = self.store.list_resources(course_id)
        remaining = [item for item in resources if item["resourceId"] != resource_id]
        deleted = len(remaining) != len(resources)
        self.store.resources[course_id] = remaining
        return deleted

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.store.create_parse_run(course_id)

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return self.store.parse_runs.get(parse_run_id)

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        return self.store.get_latest_parse_run(course_id)

    def mark_parse_run_succeeded(self, parse_run_id: int) -> dict[str, Any] | None:
        return self.store.mark_parse_run_succeeded(parse_run_id)

    def save_inquiry_answers(
        self,
        course_id: int,
        answers: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.store.save_inquiry_answers(course_id, list(answers))

    def create_handout(
        self,
        course_id: int,
        *,
        outline: dict[str, Any] | None = None,
        outline_meta: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        return self.store.create_handout(course_id)

    def get_handout_outline_context(self, course_id: int) -> dict[str, Any] | None:
        return None

    def get_handout(self, handout_version_id: int) -> dict[str, Any] | None:
        handout = self.store.handouts.get(handout_version_id)
        if handout is not None:
            _sync_memory_handout_statuses(handout)
            return _memory_public_handout(handout)
        return None

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None:
        handout = self.store.get_latest_handout(course_id)
        if handout is not None:
            _sync_memory_handout_statuses(handout)
            return _memory_public_handout(handout)
        return None

    def get_latest_outline(self, course_id: int) -> dict[str, Any] | None:
        handout = self.store.get_latest_handout(course_id)
        if handout is None:
            return None
        _sync_memory_handout_statuses(handout)
        outline = handout.get("outline")
        if isinstance(outline, dict):
            return outline
        return None

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

    def prepare_handout_block_generation(
        self,
        block_id: int,
    ) -> tuple[dict[str, Any], tuple[int, dict[str, Any]] | None] | None:
        for handout in self.store.handouts.values():
            for block in handout["blocks"]:
                if block["blockId"] != block_id:
                    continue
                if block["status"] == "ready":
                    return self.get_handout_block_status(block_id), None
                if block["status"] == "generating" and block.get("taskId") is not None:
                    task_id = int(block["taskId"])
                    return {
                        "taskId": task_id,
                        "status": "queued",
                        "nextAction": "poll",
                        "entity": {"type": "handout_block", "id": block_id},
                    }, None
                task_id = self.store.next_id("task")
                _set_memory_block_status(handout, block, "generating")
                block["taskId"] = task_id
                payload = {
                    "courseId": next(
                        course_id
                        for course_id, handout_version_id in self.store.handout_by_course.items()
                        if handout_version_id == handout["handoutVersionId"]
                    ),
                    "handoutVersionId": handout["handoutVersionId"],
                    "handoutBlockId": block_id,
                    "sourceParseRunId": handout.get("sourceParseRunId"),
                }
                self.store.register_async_task(
                    task_id=task_id,
                    course_id=payload["courseId"],
                    task_type="handout_block_generate",
                    status="queued",
                    progress_pct=0,
                    payload_json=payload,
                    parse_run_id=payload["sourceParseRunId"],
                    target_type="handout_block",
                    target_id=block_id,
                )
                return {
                    "taskId": task_id,
                    "status": "queued",
                    "nextAction": "poll",
                    "entity": {"type": "handout_block", "id": block_id},
                }, (task_id, payload)
        return None

    def save_handout_block_result(
        self,
        block_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        for handout in self.store.handouts.values():
            for block in handout["blocks"]:
                if block["blockId"] != block_id:
                    continue
                generation_metadata = _generation_metadata_from_payload(payload)
                block["title"] = str(payload.get("title") or block["title"])
                block["summary"] = str(payload.get("summary") or block["summary"])
                block["contentMd"] = str(payload.get("contentMd") or payload.get("content_md") or "")
                block["knowledgePoints"] = list(payload.get("knowledgePoints") or payload.get("knowledge_points") or [])
                block["citations"] = [
                    dict(citation)
                    for citation in payload.get("citations", [])
                    if isinstance(citation, Mapping)
                ]
                if generation_metadata:
                    block["generationMetadata"] = generation_metadata
                else:
                    block.pop("generationMetadata", None)
                _set_memory_block_status(handout, block, "ready")
                handout["readyBlocks"] = sum(
                    1 for item in handout["blocks"] if item.get("status") == "ready"
                )
                handout["pendingBlocks"] = sum(
                    1 for item in handout["blocks"] if item.get("status") != "ready"
                )
                return _memory_public_block(block)
        return None

    def get_handout_block_status(self, block_id: int) -> dict[str, Any] | None:
        for handout in self.store.handouts.values():
            for block in handout["blocks"]:
                if block["blockId"] == block_id:
                    payload = {
                        "blockId": block_id,
                        "outlineKey": block["outlineKey"],
                        "status": block["status"],
                        "generationStatus": block["status"],
                        "startSec": block.get("startSec"),
                        "endSec": block.get("endSec"),
                    }
                    if block.get("generationMetadata"):
                        payload["generationMetadata"] = dict(block["generationMetadata"])
                    return payload
        return None

    def get_current_handout_block(self, course_id: int, current_sec: int) -> dict[str, Any] | None:
        handout = self.store.get_latest_handout(course_id)
        if handout is None:
            return None
        blocks = sorted(handout["blocks"], key=lambda block: block.get("startSec") or 0)
        for index, block in enumerate(blocks):
            start_sec = block.get("startSec")
            end_sec = block.get("endSec")
            if start_sec is None or end_sec is None:
                continue
            is_last = index == len(blocks) - 1
            if start_sec <= current_sec < end_sec or (is_last and current_sec == end_sec):
                prefetch_block_id = None
                if end_sec - current_sec <= 30 and index + 1 < len(blocks):
                    next_block = blocks[index + 1]
                    if next_block["status"] == "pending":
                        prefetch_block_id = next_block["blockId"]
                return {
                    "blockId": block["blockId"],
                    "outlineKey": block["outlineKey"],
                    "startSec": start_sec,
                    "endSec": end_sec,
                    "status": block["status"],
                    "generationStatus": block["status"],
                    "prefetchBlockId": prefetch_block_id,
                }
        return None

    def get_qa_context(self, course_id: int, handout_block_id: int) -> dict[str, Any] | None:
        return self.store.get_qa_context(course_id, handout_block_id)

    def save_qa_exchange(
        self,
        context: dict[str, Any],
        question: str,
        response: dict[str, Any],
        refs: list[dict[str, Any]],
        candidate_count: int,
    ) -> dict[str, Any]:
        return self.store.save_qa_exchange(context, question, response, refs, candidate_count)

    def get_session_messages(self, session_id: int) -> list[dict[str, Any]] | None:
        return self.store.get_qa_session_messages(session_id)

    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.store.create_quiz(course_id, question_count_level=question_count_level)

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None:
        return self.store.quizzes.get(quiz_id)

    def get_quiz_submission_context(self, quiz_id: int) -> dict[str, Any] | None:
        return self.store.get_quiz_submission_context(quiz_id)

    def save_quiz_attempt_result(
        self,
        quiz_id: int,
        *,
        quiz_attempt_result: dict[str, Any],
        mastery_updates: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.store.save_quiz_attempt_result(
            quiz_id,
            quiz_attempt_result=quiz_attempt_result,
            mastery_updates=list(mastery_updates),
        )

    def next_task_id(self) -> int:
        return self.store.next_id("task")

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
    ) -> dict[str, Any]:
        return self.store.create_async_task(
            course_id=course_id,
            task_type=task_type,
            status=status,
            progress_pct=progress_pct,
            payload_json=payload_json,
            parse_run_id=parse_run_id,
            parent_task_id=parent_task_id,
            target_type=target_type,
            target_id=target_id,
            step_code=step_code,
        )

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.store.get_async_task(task_id)

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.store.list_async_tasks(course_id=course_id, parse_run_id=parse_run_id)

    def update_async_task(self, task_id: int, **changes: Any) -> dict[str, Any] | None:
        return self.store.update_async_task(task_id, **changes)

    def create_review_run(self, course_id: int) -> dict[str, Any]:
        return self.store.create_review_run(course_id)

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        return self.store.list_review_tasks(course_id)

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None:
        return self.store.get_review_run(review_task_run_id)

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]:
        return {"reviewTaskId": review_task_id, "completed": True}

    def list_daily_recommended_knowledge_points(self, *, limit: int = 3) -> list[dict[str, Any]]:
        return self.store.list_daily_recommended_knowledge_points(limit=limit)

    def get_learning_stats(self) -> dict[str, Any]:
        return self.store.get_learning_stats()

    def get_progress(self, course_id: int) -> dict[str, Any]:
        return self.store.get_progress(course_id)

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.store.update_progress(course_id, payload)


def _sync_memory_handout_statuses(handout: dict[str, Any]) -> None:
    blocks_by_id = {
        block.get("blockId"): block
        for block in handout.get("blocks", [])
        if isinstance(block, dict)
    }
    for block in blocks_by_id.values():
        status = str(block.get("status") or block.get("generationStatus") or "pending")
        block["status"] = status
        block["generationStatus"] = status

    outline = handout.get("outline")
    if not isinstance(outline, dict):
        return
    for section in outline.get("items", []):
        if not isinstance(section, dict):
            continue
        children = section.get("children")
        if not isinstance(children, list):
            continue
        for child in children:
            if not isinstance(child, dict):
                continue
            block = blocks_by_id.get(child.get("blockId"))
            if block is None:
                continue
            child["generationStatus"] = block["status"]
            child["sourceSegmentKeys"] = list(block.get("sourceSegmentKeys") or [])


def _set_memory_block_status(handout: dict[str, Any], block: dict[str, Any], status: str) -> None:
    block["status"] = status
    block["generationStatus"] = status
    _sync_memory_handout_statuses(handout)


def _memory_public_handout(handout: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(handout)
    payload["blocks"] = [
        _memory_public_block(block)
        for block in handout.get("blocks", [])
        if isinstance(block, dict)
    ]
    return payload


def _memory_public_block(block: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(block)
    payload["citations"] = [
        _memory_public_citation(citation)
        for citation in block.get("citations", [])
        if isinstance(citation, Mapping)
    ]
    return payload


def _memory_public_citation(ref: Mapping[str, Any]) -> dict[str, Any]:
    citation = {
        "resourceId": ref.get("resourceId"),
        "refLabel": ref.get("refLabel"),
        "pageNo": ref.get("pageNo"),
        "slideNo": ref.get("slideNo"),
        "anchorKey": ref.get("anchorKey"),
        "startSec": ref.get("startSec"),
        "endSec": ref.get("endSec"),
    }
    return {key: value for key, value in citation.items() if value not in (None, "", [])}


def _generation_metadata_from_payload(payload: Mapping[str, Any]) -> dict[str, str] | None:
    raw = payload.get("generationMetadata") or payload.get("generation_metadata")
    if not isinstance(raw, Mapping):
        return None
    source = raw.get("source")
    reason = raw.get("reason")
    if source not in {"model", "fallback"} or not isinstance(reason, str) or not reason.strip():
        return None
    return {"source": str(source), "reason": reason.strip()}
