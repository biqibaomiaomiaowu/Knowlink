from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

from server.api.deps import (
    _get_memory_repository,
    get_async_task_repository,
    get_handout_service,
    get_quiz_service,
    get_review_service,
    get_task_dispatcher,
)
from server.domain.services.idempotency import build_request_hash
from server.domain.services.errors import ServiceError
from server.domain.services.handouts import HandoutService
from server.domain.services.pipelines import PipelineService
from server.domain.services.quizzes import QuizService
from server.domain.services.recommendations import RecommendationFlowService
from server.domain.services.resources import ResourceService
from server.domain.services.reviews import ReviewService
from server.infra.repositories.memory_runtime import RuntimeStore, utcnow as memory_utcnow
from server.infra.storage import ObjectStat
from server.schemas.requests import ConfirmRecommendationRequest, UploadCompleteRequest
from server.tasks import InMemoryTaskDispatcher, NoopTaskDispatcher


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, dict[str, Any]]] = []

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("parse_pipeline", task_id, payload))

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("handout_generate", task_id, payload))

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("handout_block_generate", task_id, payload))

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("quiz_generate", task_id, payload))

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("review_refresh", task_id, payload))

    def enqueue_bilibili_import(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.calls.append(("bilibili_import", task_id, payload))


def test_memory_runtime_async_tasks_use_in_memory_dispatcher():
    repo = _get_memory_repository()

    async_tasks = asyncio.run(get_async_task_repository(repo))
    dispatcher = asyncio.run(get_task_dispatcher(repo, async_tasks))

    assert async_tasks is repo
    assert isinstance(dispatcher, InMemoryTaskDispatcher)
    assert not isinstance(dispatcher, NoopTaskDispatcher)
    assert dispatcher.parse_runs is repo
    assert dispatcher.async_tasks is repo


class _FailingDispatcher(_RecordingDispatcher):
    def __init__(self, failing_method: str) -> None:
        super().__init__()
        self.failing_method = failing_method

    def _maybe_fail(self, method_name: str) -> None:
        if method_name == self.failing_method:
            raise RuntimeError("broker offline")

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self._maybe_fail("parse_pipeline")
        super().enqueue_parse_pipeline(task_id=task_id, payload=payload)

    def enqueue_handout_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self._maybe_fail("handout_generate")
        super().enqueue_handout_generate(task_id=task_id, payload=payload)

    def enqueue_handout_block_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self._maybe_fail("handout_block_generate")
        super().enqueue_handout_block_generate(task_id=task_id, payload=payload)

    def enqueue_quiz_generate(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self._maybe_fail("quiz_generate")
        super().enqueue_quiz_generate(task_id=task_id, payload=payload)

    def enqueue_review_refresh(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self._maybe_fail("review_refresh")
        super().enqueue_review_refresh(task_id=task_id, payload=payload)


class _SynchronousSuccessDispatcher(_RecordingDispatcher):
    def __init__(self, async_tasks: Any) -> None:
        super().__init__()
        self.async_tasks = async_tasks

    def _mark_succeeded(self, task_id: int) -> None:
        self.async_tasks.update_async_task(task_id, status="succeeded", progress_pct=100)

    def enqueue_parse_pipeline(self, *, task_id: int, payload: dict[str, Any]) -> None:
        super().enqueue_parse_pipeline(task_id=task_id, payload=payload)
        self._mark_succeeded(task_id)


class _PipelineRepo:
    def __init__(self) -> None:
        self.course = {
            "courseId": 201,
            "lifecycleStatus": "resource_ready",
            "pipelineStage": "idle",
            "pipelineStatus": "idle",
        }
        self.resources = [{"resourceId": 501, "resourceType": "pdf"}]
        self.parse_runs: dict[int, dict[str, Any]] = {}
        self.tasks: dict[int, dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.next_parse_run_id = 9000
        self.next_task_id = 7000

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.resources

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        self.next_parse_run_id += 1
        parse_run = {
            "parseRunId": self.next_parse_run_id,
            "courseId": course_id,
            "status": "queued",
            "progressPct": 0,
        }
        self.parse_runs[self.next_parse_run_id] = parse_run
        return parse_run, {}

    def get_parse_run(self, parse_run_id: int) -> dict[str, Any] | None:
        return self.parse_runs.get(parse_run_id)

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        if not self.parse_runs:
            return None
        return self.parse_runs[max(self.parse_runs)]

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

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
        self.next_task_id += 1
        task = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": parse_run_id,
            "taskType": task_type,
            "status": status,
            "progressPct": progress_pct,
            "payloadJson": payload_json or {},
            "parentTaskId": parent_task_id,
            "targetType": target_type,
            "targetId": target_id,
            "stepCode": step_code,
        }
        self.tasks[self.next_task_id] = task
        return task

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            task
            for task in self.tasks.values()
            if task["courseId"] == course_id
            and (parse_run_id is None or task["parseRunId"] == parse_run_id)
        ]

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
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if clear_error:
            task["errorCode"] = None
            task["errorMessage"] = None
        if status is not None:
            task["status"] = status
        if progress_pct is not None:
            task["progressPct"] = progress_pct
        if payload_json is not None:
            task["payloadJson"] = payload_json
        if error_code is not None:
            task["errorCode"] = error_code
        if error_message is not None:
            task["errorMessage"] = error_message
        return task


class _QuizRepo:
    def __init__(self) -> None:
        self.course = {"courseId": 301}
        self.tasks: dict[int, dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.next_quiz_id = 8100
        self.next_task_id = 9100

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.next_quiz_id += 1
        self.next_task_id += 1
        payload = {
            "courseId": course_id,
            "quizId": self.next_quiz_id,
            "questionCountLevel": question_count_level,
        }
        self.tasks[self.next_task_id] = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "taskType": "quiz_generate",
            "status": "queued",
            "progressPct": 0,
            "payloadJson": payload,
            "targetType": "quiz",
            "targetId": self.next_quiz_id,
        }
        return {}, {
            "taskId": self.next_task_id,
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "quiz", "id": self.next_quiz_id},
        }

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None:
        return None

    def submit_quiz(self, quiz_id: int, answers) -> dict[str, Any]:
        raise AssertionError("not used")

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        clear_error: bool = False,
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if clear_error:
            task["errorCode"] = None
            task["errorMessage"] = None
        if status is not None:
            task["status"] = status
        if progress_pct is not None:
            task["progressPct"] = progress_pct
        if error_code is not None:
            task["errorCode"] = error_code
        if error_message is not None:
            task["errorMessage"] = error_message
        return task


class _RunningQuizRepo(_QuizRepo):
    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.next_quiz_id += 1
        self.next_task_id += 1
        payload = {
            "courseId": course_id,
            "quizId": self.next_quiz_id,
            "questionCountLevel": question_count_level,
        }
        self.tasks[self.next_task_id] = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "taskType": "quiz_generate",
            "status": "running",
            "progressPct": 50,
            "payloadJson": payload,
            "targetType": "quiz",
            "targetId": self.next_quiz_id,
        }
        return {}, {
            "taskId": self.next_task_id,
            "status": "running",
            "nextAction": "poll",
            "entity": {"type": "quiz", "id": self.next_quiz_id},
        }


class _MissingQuizTaskIdRepo(_QuizRepo):
    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self.next_quiz_id += 1
        return {}, {
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "quiz", "id": self.next_quiz_id},
        }


class _QuizSubmitRepo:
    def __init__(self) -> None:
        self.quiz = {
            "quizId": 8201,
            "courseId": 302,
            "status": "ready",
            "questionCount": 1,
        }
        self.next_review_run_id = 8300
        self.next_task_id = 9300

    def get_course(self, course_id: int) -> dict[str, Any]:
        return {"courseId": course_id}

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None:
        if quiz_id == self.quiz["quizId"]:
            return self.quiz
        return None

    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raise AssertionError("not used")

    def submit_quiz(self, quiz_id: int, answers) -> dict[str, Any]:
        raise AssertionError("use QuizService grading path")

    def get_quiz_submission_context(self, quiz_id: int) -> dict[str, Any] | None:
        if quiz_id != self.quiz["quizId"]:
            return None
        return {
            "quizPayload": {
                "quizType": "chapter_review",
                "questions": [
                    {
                        "questionId": 1,
                        "questionKey": "q1",
                        "questionType": "single_choice",
                        "stemMd": "1 + 1 = ?",
                        "options": ["A. 2", "B. 3", "C. 4", "D. 5"],
                        "correctAnswer": "A",
                        "explanationMd": "基础加法。",
                        "difficultyLevel": "easy",
                        "knowledgePointKey": "kp-add",
                        "knowledgePointName": "加法",
                        "sourceBlockKey": "block-1",
                        "sourceSegmentKeys": ["seg-1"],
                    }
                ],
            },
            "masteryRecords": [],
        }

    def save_quiz_attempt_result(
        self,
        quiz_id: int,
        *,
        quiz_attempt_result: dict[str, Any],
        mastery_updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _ = mastery_updates
        self.next_review_run_id += 1
        self.next_task_id += 1
        payload = {
            "courseId": self.quiz["courseId"],
            "reviewTaskRunId": self.next_review_run_id,
        }
        return {
            "attemptId": 8401,
            "score": quiz_attempt_result["score"],
            "totalScore": quiz_attempt_result["totalScore"],
            "accuracy": quiz_attempt_result["accuracy"],
            "reviewTaskRunId": self.next_review_run_id,
            "_reviewRefreshTask": {
                "taskId": self.next_task_id,
                "payload": payload,
            },
        }


class _QuizSubmitPayload:
    def model_dump(self, **kwargs) -> dict[str, Any]:
        return {"answers": [{"questionId": 1, "selectedOption": "A"}]}


class _ReviewRepo:
    def __init__(self) -> None:
        self.course = {"courseId": 401}
        self.tasks: dict[int, dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.next_run_id = 1000
        self.next_task_id_value = 1100

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def next_task_id(self) -> int:
        return self.next_task_id_value + 1

    def create_review_run(self, course_id: int) -> dict[str, Any]:
        self.next_run_id += 1
        self.next_task_id_value += 1
        payload = {"courseId": course_id, "reviewTaskRunId": self.next_run_id}
        self.tasks[self.next_task_id_value] = {
            "taskId": self.next_task_id_value,
            "courseId": course_id,
            "taskType": "review_refresh",
            "status": "queued",
            "progressPct": 0,
            "payloadJson": payload,
            "targetType": "review_task_run",
            "targetId": self.next_run_id,
        }
        return {
            "reviewTaskRunId": self.next_run_id,
            "courseId": course_id,
            "status": "queued",
            "_reviewRefreshTask": {
                "taskId": self.next_task_id_value,
                "payload": payload,
            },
        }

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        return []

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None:
        return None

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]:
        raise AssertionError("not used")

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        clear_error: bool = False,
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if clear_error:
            task["errorCode"] = None
            task["errorMessage"] = None
        if status is not None:
            task["status"] = status
        if progress_pct is not None:
            task["progressPct"] = progress_pct
        if error_code is not None:
            task["errorCode"] = error_code
        if error_message is not None:
            task["errorMessage"] = error_message
        return task


class _ReviewMissingRefreshTaskIdRepo(_ReviewRepo):
    def create_review_run(self, course_id: int) -> dict[str, Any]:
        self.next_run_id += 1
        payload = {"courseId": course_id, "reviewTaskRunId": self.next_run_id}
        return {
            "reviewTaskRunId": self.next_run_id,
            "courseId": course_id,
            "status": "queued",
            "_reviewRefreshTask": {
                "payload": payload,
            },
        }


class _ReviewInvalidRefreshPayloadRepo(_ReviewRepo):
    def create_review_run(self, course_id: int) -> dict[str, Any]:
        self.next_run_id += 1
        self.next_task_id_value += 1
        self.tasks[self.next_task_id_value] = {
            "taskId": self.next_task_id_value,
            "courseId": course_id,
            "taskType": "review_refresh",
            "status": "queued",
            "progressPct": 0,
            "payloadJson": {},
            "targetType": "review_task_run",
            "targetId": self.next_run_id,
        }
        return {
            "reviewTaskRunId": self.next_run_id,
            "courseId": course_id,
            "status": "queued",
            "_reviewRefreshTask": {
                "taskId": self.next_task_id_value,
                "payload": "not-a-payload",
            },
        }


class _ReviewReadyRepo:
    def __init__(self) -> None:
        self.course = {"courseId": 402}
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.next_task_id_value = 2100

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def next_task_id(self) -> int:
        return self.next_task_id_value

    def create_review_run(self, course_id: int) -> dict[str, Any]:
        return {
            "reviewTaskRunId": 2001,
            "courseId": course_id,
            "status": "ready",
            "generatedCount": 3,
        }

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        return []

    def get_review_run(self, review_task_run_id: int) -> dict[str, Any] | None:
        return None

    def complete_review_task(self, review_task_id: int) -> dict[str, Any]:
        raise AssertionError("not used")


class _HandoutRepo:
    def __init__(self) -> None:
        self.course = {"courseId": 501, "activeParseRunId": 9501}
        self.tasks: dict[int, dict[str, Any]] = {}
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.next_handout_version_id = 1200
        self.next_task_id = 1300
        self.block_id = 1401

    def get_course(self, course_id: int) -> dict[str, Any]:
        return self.course

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def get_handout_outline_context(self, course_id: int) -> dict[str, Any] | None:
        return {
            "title": "导数基础",
            "summary": "导数概念与几何意义。",
            "captionSegments": [
                {
                    "segmentKey": "caption-1",
                    "segmentType": "video_caption",
                    "orderNo": 1,
                    "textContent": "导数表示函数在一点附近的变化率。",
                    "startSec": 0,
                    "endSec": 30,
                }
            ],
        }

    def create_handout(
        self,
        course_id: int,
        *,
        outline: dict[str, Any] | None = None,
        outline_meta: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        self.next_handout_version_id += 1
        self.next_task_id += 1
        payload = {
            "courseId": course_id,
            "handoutVersionId": self.next_handout_version_id,
            "sourceParseRunId": self.course["activeParseRunId"],
        }
        self.tasks[self.next_task_id] = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": self.course["activeParseRunId"],
            "taskType": "handout_generate",
            "status": "queued",
            "progressPct": 0,
            "payloadJson": payload,
            "targetType": "handout_version",
            "targetId": self.next_handout_version_id,
        }
        return (
            {"handoutVersionId": self.next_handout_version_id},
            {
                "taskId": self.next_task_id,
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "handout_version", "id": self.next_handout_version_id},
            },
            [],
        )

    def prepare_handout_block_generation(
        self,
        block_id: int,
    ) -> tuple[dict[str, Any], tuple[int, dict[str, Any]] | None] | None:
        if block_id != self.block_id:
            return None
        self.next_task_id += 1
        payload = {
            "courseId": self.course["courseId"],
            "handoutVersionId": self.next_handout_version_id,
            "handoutBlockId": block_id,
            "sourceParseRunId": self.course["activeParseRunId"],
        }
        self.tasks[self.next_task_id] = {
            "taskId": self.next_task_id,
            "courseId": self.course["courseId"],
            "parseRunId": self.course["activeParseRunId"],
            "taskType": "handout_block_generate",
            "status": "queued",
            "progressPct": 0,
            "payloadJson": payload,
            "targetType": "handout_block",
            "targetId": block_id,
        }
        return (
            {
                "taskId": self.next_task_id,
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "handout_block", "id": block_id},
            },
            (self.next_task_id, payload),
        )

    def get_handout(self, handout_version_id: int) -> dict[str, Any] | None:
        return None

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None:
        return None

    def get_latest_outline(self, course_id: int) -> dict[str, Any] | None:
        return None

    def get_block_jump_target(self, block_id: int) -> dict[str, Any] | None:
        return None

    def save_handout_block_result(self, block_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        raise AssertionError("not used")

    def get_handout_block_status(self, block_id: int) -> dict[str, Any] | None:
        if block_id != self.block_id:
            return None
        return {"blockId": block_id, "status": "pending"}

    def get_current_handout_block(self, course_id: int, current_sec: int) -> dict[str, Any] | None:
        return None

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

    def update_async_task(
        self,
        task_id: int,
        *,
        status: str | None = None,
        progress_pct: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        clear_error: bool = False,
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if clear_error:
            task["errorCode"] = None
            task["errorMessage"] = None
        if status is not None:
            task["status"] = status
        if progress_pct is not None:
            task["progressPct"] = progress_pct
        if error_code is not None:
            task["errorCode"] = error_code
        if error_message is not None:
            task["errorMessage"] = error_message
        return task


class _HandoutMissingEntityRepo(_HandoutRepo):
    def create_handout(
        self,
        course_id: int,
        *,
        outline: dict[str, Any] | None = None,
        outline_meta: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        self.next_handout_version_id += 1
        self.next_task_id += 1
        payload = {
            "courseId": course_id,
            "handoutVersionId": self.next_handout_version_id,
            "sourceParseRunId": self.course["activeParseRunId"],
        }
        self.tasks[self.next_task_id] = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": self.course["activeParseRunId"],
            "taskType": "handout_generate",
            "status": "queued",
            "progressPct": 0,
            "payloadJson": payload,
            "targetType": "handout_version",
            "targetId": self.next_handout_version_id,
        }
        return (
            {"handoutVersionId": self.next_handout_version_id},
            {
                "taskId": self.next_task_id,
                "status": "queued",
                "nextAction": "poll",
            },
            [],
        )


class _HandoutGeneratingRepo(_HandoutRepo):
    def __init__(self) -> None:
        super().__init__()
        self.existing_task_id = 1601

    def prepare_handout_block_generation(
        self,
        block_id: int,
    ) -> tuple[dict[str, Any], tuple[int, dict[str, Any]] | None] | None:
        if block_id != self.block_id:
            return None
        return (
            {
                "taskId": self.existing_task_id,
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "handout_block", "id": block_id},
            },
            None,
        )

    def get_handout_block_status(self, block_id: int) -> dict[str, Any] | None:
        if block_id != self.block_id:
            return None
        return {"blockId": block_id, "status": "generating"}


class _RepoWithoutAsyncTasks:
    def get_course(self, course_id: int) -> dict[str, Any]:
        return {"courseId": course_id, "activeParseRunId": 9501}

    def run_idempotent(self, action: str, key: str | None, factory):
        return factory()


class _SeparateAsyncTaskRepo:
    def __init__(self) -> None:
        self.tasks: dict[int, dict[str, Any]] = {}
        self.next_task_id = 50000

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
        self.next_task_id += 1
        task = {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": parse_run_id,
            "taskType": task_type,
            "status": status,
            "progressPct": progress_pct,
            "payloadJson": payload_json or {},
            "parentTaskId": parent_task_id,
            "targetType": target_type,
            "targetId": target_id,
            "stepCode": step_code,
            "errorCode": None,
            "errorMessage": None,
        }
        self.tasks[self.next_task_id] = task
        return task

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get(task_id)

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
    ) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        if clear_error:
            task["errorCode"] = None
            task["errorMessage"] = None
        if status is not None:
            task["status"] = status
        if progress_pct is not None:
            task["progressPct"] = progress_pct
        if payload_json is not None:
            task["payloadJson"] = payload_json
        if error_code is not None:
            task["errorCode"] = error_code
        if error_message is not None:
            task["errorMessage"] = error_message
        return task


class _UnverifiedAsyncTaskRepo(_SeparateAsyncTaskRepo):
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
        self.next_task_id += 1
        return {
            "taskId": self.next_task_id,
            "courseId": course_id,
            "parseRunId": parse_run_id,
            "taskType": task_type,
            "status": status,
            "progressPct": progress_pct,
            "payloadJson": payload_json or {},
            "parentTaskId": parent_task_id,
            "targetType": target_type,
            "targetId": target_id,
            "stepCode": step_code,
        }


class _LegacyIdempotencyMixin:
    def get_idempotency_result(self, action: str, key: str | None):
        if key is None:
            return None
        idempotency_records = getattr(self, "idempotency_records", {})
        if (action, key) in idempotency_records:
            return idempotency_records[(action, key)]
        return self.idempotency.get((action, key))


class _LegacyPipelineRepo(_LegacyIdempotencyMixin, _PipelineRepo):
    pass


class _LegacyQuizRepo(_LegacyIdempotencyMixin, _QuizRepo):
    pass


class _LegacyReviewRepo(_LegacyIdempotencyMixin, _ReviewRepo):
    pass


class _LegacyHandoutRepo(_LegacyIdempotencyMixin, _HandoutRepo):
    pass


class _LegacyResourceRepo(_LegacyIdempotencyMixin):
    def __init__(self) -> None:
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.idempotency_records: dict[tuple[str, str], dict[str, Any]] = {}
        self.resources: list[dict[str, Any]] = []
        self.next_resource_id = 600

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def get_course(self, course_id: int) -> dict[str, Any]:
        return {"courseId": course_id}

    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.next_resource_id += 1
        resource = {
            "resourceId": self.next_resource_id,
            "courseId": course_id,
            "resourceType": payload["resourceType"],
            "objectKey": payload["objectKey"],
            "originalName": payload["originalName"],
            "mimeType": payload["mimeType"],
        }
        self.resources.append(resource)
        return resource

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return [item for item in self.resources if item["courseId"] == course_id]

    def get_resource(self, resource_id: int) -> dict[str, Any] | None:
        for resource in self.resources:
            if resource["resourceId"] == resource_id:
                return resource
        return None

    def delete_resource(self, course_id: int, resource_id: int) -> bool:
        raise AssertionError("not used")


class _LegacyResourceStorage:
    def stat_object(self, object_key: str) -> ObjectStat:
        return ObjectStat(size_bytes=1024, checksum="sha256:new", checksum_required=True)


class _LegacyCourseRepo(_LegacyIdempotencyMixin):
    def __init__(self) -> None:
        self.idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        self.courses: list[dict[str, Any]] = []
        self.next_course_id = 900

    def run_idempotent(self, action: str, key: str | None, factory):
        if key is not None and (action, key) in self.idempotency:
            return self.idempotency[(action, key)]
        value = factory()
        if key is not None:
            self.idempotency[(action, key)] = value
        return value

    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
        exam_at=None,
    ) -> dict[str, Any]:
        self.next_course_id += 1
        course = {
            "courseId": self.next_course_id,
            "title": title,
            "entryType": entry_type,
            "goalText": goal_text,
            "preferredStyle": preferred_style,
            "catalogId": catalog_id,
            "examAt": exam_at,
        }
        self.courses.append(course)
        return course

    def list_recent_courses(self) -> list[dict[str, Any]]:
        return list(self.courses)

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        for course in self.courses:
            if course["courseId"] == course_id:
                return course
        return None


class _LegacyCatalog:
    def get_catalog_entry(self, catalog_id: str) -> dict[str, Any] | None:
        entries = {
            "math-final-01": {"catalogId": "math-final-01", "title": "高数期末课"},
            "linear-final-01": {"catalogId": "linear-final-01", "title": "线代期末课"},
        }
        return entries.get(catalog_id)


def _upload_payload(course_id: int, suffix: str) -> UploadCompleteRequest:
    return UploadCompleteRequest(
        resource_type="pdf",
        object_key=f"raw/1/{course_id}/{suffix}.pdf",
        original_name=f"{suffix}.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        checksum="sha256:new",
    )


def test_legacy_unscoped_upload_complete_replays_only_for_matching_course():
    repo = _LegacyResourceRepo()
    service = ResourceService(
        courses=repo,
        resources=repo,
        idempotency=repo,
        storage=_LegacyResourceStorage(),
    )
    matching = {
        "resourceId": 777,
        "courseId": 11,
        "resourceType": "pdf",
        "objectKey": "raw/1/11/legacy.pdf",
        "originalName": "legacy.pdf",
        "mimeType": "application/pdf",
    }
    mismatched = matching | {"resourceId": 778, "courseId": 22}
    repo.idempotency[("resources.upload_complete", "legacy-match")] = matching
    repo.idempotency[("resources.upload_complete", "legacy-mismatch")] = mismatched

    replayed = service.upload_complete(
        course_id=11,
        payload=_upload_payload(11, "new-match"),
        idempotency_key="legacy-match",
    )
    created = service.upload_complete(
        course_id=11,
        payload=_upload_payload(11, "new-mismatch"),
        idempotency_key="legacy-mismatch",
    )

    assert replayed == matching
    assert repo.idempotency[("resources.upload_complete:11", "legacy-match")] == matching
    assert created["courseId"] == 11
    assert created["resourceId"] != mismatched["resourceId"]


def test_scoped_idempotency_rejects_in_progress_replay():
    repo = _LegacyResourceRepo()
    service = ResourceService(
        courses=repo,
        resources=repo,
        idempotency=repo,
        storage=_LegacyResourceStorage(),
    )
    payload = _upload_payload(11, "in-progress")
    request_hash = build_request_hash(payload.model_dump(by_alias=True))
    repo.idempotency_records[("resources.upload_complete:11", "in-progress-key")] = {
        "scope": "resources.upload_complete:11",
        "key": "in-progress-key",
        "requestHash": request_hash,
        "status": "in_progress",
        "responseJson": None,
    }

    with pytest.raises(ServiceError) as exc_info:
        service.upload_complete(
            course_id=11,
            payload=payload,
            idempotency_key="in-progress-key",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "common.idempotency_replay"


def test_memory_scoped_idempotency_ignores_expired_records():
    store = RuntimeStore()
    expired_at = memory_utcnow() - timedelta(seconds=1)

    in_progress_scope = "resources.upload_complete:11"
    in_progress_key = "expired-in-progress"
    in_progress_hash = build_request_hash({"objectKey": "old.pdf"})
    replacement_hash = build_request_hash({"objectKey": "new.pdf"})
    store.idempotency_records[(in_progress_scope, in_progress_key)] = {
        "scope": in_progress_scope,
        "key": in_progress_key,
        "requestHash": in_progress_hash,
        "status": "in_progress",
        "responseJson": None,
        "expiresAt": expired_at,
    }

    replacement = store.run_scoped_idempotent(
        scope=in_progress_scope,
        key=in_progress_key,
        request_hash=replacement_hash,
        factory=lambda: {"resourceId": 701, "objectKey": "new.pdf"},
    )

    succeeded_scope = "pipelines.parse_start:11"
    succeeded_key = "expired-succeeded"
    succeeded_hash = build_request_hash({"courseId": 11})
    new_succeeded_hash = build_request_hash({"courseId": 12})
    store.idempotency_records[(succeeded_scope, succeeded_key)] = {
        "scope": succeeded_scope,
        "key": succeeded_key,
        "requestHash": succeeded_hash,
        "status": "succeeded",
        "responseJson": {"taskId": 1},
        "expiresAt": expired_at,
    }

    new_value = store.run_scoped_idempotent(
        scope=succeeded_scope,
        key=succeeded_key,
        request_hash=new_succeeded_hash,
        factory=lambda: {"taskId": 2},
    )

    assert replacement == {"resourceId": 701, "objectKey": "new.pdf"}
    assert store.idempotency_records[(in_progress_scope, in_progress_key)]["requestHash"] == replacement_hash
    assert store.idempotency_records[(in_progress_scope, in_progress_key)]["status"] == "succeeded"
    assert new_value == {"taskId": 2}
    assert store.idempotency_records[(succeeded_scope, succeeded_key)]["requestHash"] == new_succeeded_hash


def test_legacy_unscoped_recommendation_confirm_replays_only_for_matching_catalog():
    repo = _LegacyCourseRepo()
    service = RecommendationFlowService(
        catalog=_LegacyCatalog(),
        courses=repo,
        idempotency=repo,
    )
    matching = {
        "course": {"courseId": 901, "catalogId": "math-final-01"},
        "createdFromCatalogId": "math-final-01",
    }
    mismatched = {
        "course": {"courseId": 902, "catalogId": "linear-final-01"},
        "createdFromCatalogId": "linear-final-01",
    }
    repo.idempotency[("recommendation.confirm", "legacy-match")] = matching
    repo.idempotency[("recommendation.confirm", "legacy-mismatch")] = mismatched
    payload = ConfirmRecommendationRequest(goal_text="期末复习", preferred_style="exam")

    replayed = service.confirm(
        catalog_id="math-final-01",
        payload=payload,
        idempotency_key="legacy-match",
    )
    created = service.confirm(
        catalog_id="math-final-01",
        payload=payload,
        idempotency_key="legacy-mismatch",
    )

    assert replayed == matching
    assert repo.idempotency[("recommendation.confirm:math-final-01", "legacy-match")] == matching
    assert created["createdFromCatalogId"] == "math-final-01"
    assert created["course"]["courseId"] != mismatched["course"]["courseId"]


def test_legacy_unscoped_parse_start_replays_matching_task_trigger():
    repo = _LegacyPipelineRepo()
    dispatcher = _RecordingDispatcher()
    service = PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=dispatcher,
        idempotency=repo,
    )
    stored = {
        "taskId": 7701,
        "status": "queued",
        "nextAction": "poll",
        "entity": {"type": "parse_run", "id": 9901},
    }
    repo.tasks[7701] = {
        "taskId": 7701,
        "courseId": 201,
        "parseRunId": 9901,
        "taskType": "parse_pipeline",
        "status": "queued",
        "progressPct": 0,
        "payloadJson": {"courseId": 201, "parseRunId": 9901},
        "targetType": "parse_run",
        "targetId": 9901,
    }
    repo.idempotency[("pipelines.parse_start", "legacy-parse")] = stored

    result = service.start_parse(course_id=201, idempotency_key="legacy-parse")

    assert result == stored
    assert repo.idempotency[("pipelines.parse_start:201", "legacy-parse")] == stored
    assert dispatcher.calls == []


def test_legacy_unscoped_handout_generate_replays_matching_task_trigger():
    repo = _LegacyHandoutRepo()
    dispatcher = _RecordingDispatcher()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )
    stored = {
        "taskId": 8801,
        "status": "queued",
        "nextAction": "poll",
        "entity": {"type": "handout_version", "id": 1801},
    }
    repo.tasks[8801] = {
        "taskId": 8801,
        "courseId": 501,
        "parseRunId": 9501,
        "taskType": "handout_generate",
        "status": "queued",
        "progressPct": 0,
        "payloadJson": {"courseId": 501, "handoutVersionId": 1801, "sourceParseRunId": 9501},
        "targetType": "handout_version",
        "targetId": 1801,
    }
    repo.idempotency[("handouts.generate", "legacy-handout")] = stored

    result = service.generate_handout(course_id=501, idempotency_key="legacy-handout")

    assert result == stored
    assert repo.idempotency[("handouts.generate:501", "legacy-handout")] == stored
    assert dispatcher.calls == []


def test_legacy_unscoped_quiz_generate_replays_only_for_matching_task_trigger():
    repo = _LegacyQuizRepo()
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )
    matching = {
        "taskId": 9901,
        "status": "queued",
        "nextAction": "poll",
        "entity": {"type": "quiz", "id": 8801},
    }
    mismatched = {
        "taskId": 9902,
        "status": "queued",
        "nextAction": "poll",
        "entity": {"type": "quiz", "id": 8802},
    }
    repo.tasks[9901] = {
        "taskId": 9901,
        "courseId": 301,
        "taskType": "quiz_generate",
        "status": "queued",
        "progressPct": 0,
        "payloadJson": {"courseId": 301, "quizId": 8801},
        "targetType": "quiz",
        "targetId": 8801,
    }
    repo.tasks[9902] = repo.tasks[9901] | {
        "taskId": 9902,
        "courseId": 999,
        "payloadJson": {"courseId": 999, "quizId": 8802},
        "targetId": 8802,
    }
    repo.idempotency[("quizzes.generate", "legacy-match")] = matching
    repo.idempotency[("quizzes.generate", "legacy-mismatch")] = mismatched

    replayed = service.generate_quiz(
        course_id=301,
        question_count_level="medium",
        idempotency_key="legacy-match",
    )
    created = service.generate_quiz(
        course_id=301,
        question_count_level="medium",
        idempotency_key="legacy-mismatch",
    )

    assert replayed == matching
    assert repo.idempotency[("quizzes.generate:301", "legacy-match")] == matching
    assert created["entity"]["id"] != mismatched["entity"]["id"]
    assert dispatcher.calls == [("quiz_generate", created["taskId"], repo.tasks[created["taskId"]]["payloadJson"])]


def test_legacy_unscoped_review_regenerate_replays_matching_task_trigger():
    repo = _LegacyReviewRepo()
    dispatcher = _RecordingDispatcher()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )
    stored = {
        "taskId": 9903,
        "status": "queued",
        "nextAction": "poll",
        "entity": {"type": "review_task_run", "id": 1803},
    }
    repo.tasks[9903] = {
        "taskId": 9903,
        "courseId": 401,
        "taskType": "review_refresh",
        "status": "queued",
        "progressPct": 0,
        "payloadJson": {"courseId": 401, "reviewTaskRunId": 1803},
        "targetType": "review_task_run",
        "targetId": 1803,
    }
    repo.idempotency[("reviews.regenerate", "legacy-review")] = stored

    result = service.regenerate_review_tasks(course_id=401, idempotency_key="legacy-review")

    assert result == stored
    assert repo.idempotency[("reviews.regenerate:401", "legacy-review")] == stored
    assert dispatcher.calls == []


class _StaleUpdatePipelineRepo(_PipelineRepo):
    def update_async_task(self, task_id: int, **kwargs) -> dict[str, Any] | None:
        if kwargs.get("status") == "queued":
            return None
        return super().update_async_task(task_id, **kwargs)


def _pipeline_service(repo: _PipelineRepo, dispatcher: _RecordingDispatcher) -> PipelineService:
    return PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=repo,
        task_dispatcher=dispatcher,
        idempotency=repo,
    )


def test_parse_start_marks_root_task_failed_when_enqueue_fails():
    repo = _PipelineRepo()
    service = _pipeline_service(repo, _FailingDispatcher("parse_pipeline"))

    with pytest.raises(ServiceError) as exc_info:
        service.start_parse(course_id=201, idempotency_key="parse-enqueue-fails")

    root_task = next(task for task in repo.tasks.values() if task["taskType"] == "parse_pipeline")
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert root_task["status"] == "failed"
    assert root_task["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in root_task["errorMessage"]


def test_parse_start_marks_non_skipped_child_tasks_failed_when_root_enqueue_fails():
    repo = _PipelineRepo()
    service = _pipeline_service(repo, _FailingDispatcher("parse_pipeline"))

    with pytest.raises(ServiceError) as exc_info:
        service.start_parse(course_id=201, idempotency_key="parse-tree-enqueue-fails")

    assert exc_info.value.error_code == "async_task.enqueue_failed"
    child_tasks = [task for task in repo.tasks.values() if task["parentTaskId"] is not None]
    assert child_tasks
    assert [
        task["stepCode"]
        for task in child_tasks
        if task["status"] == "skipped"
    ] == ["caption_extract"]
    non_skipped_children = [task for task in child_tasks if task["stepCode"] != "caption_extract"]
    assert non_skipped_children
    assert {task["status"] for task in non_skipped_children} == {"failed"}
    assert all(task["errorCode"] == "async_task.enqueue_failed" for task in non_skipped_children)


def test_parse_start_replay_returns_failed_task_after_enqueue_failure():
    repo = _PipelineRepo()
    service = _pipeline_service(repo, _FailingDispatcher("parse_pipeline"))

    with pytest.raises(ServiceError):
        service.start_parse(course_id=201, idempotency_key="parse-enqueue-fails")

    result = service.start_parse(course_id=201, idempotency_key="parse-enqueue-fails")

    assert result["status"] == "failed"
    assert result["nextAction"] == "retry"
    assert result["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in result["errorMessage"]


def test_parse_start_keeps_created_queued_trigger_when_enqueue_succeeds_synchronously():
    repo = _PipelineRepo()
    service = _pipeline_service(repo, _SynchronousSuccessDispatcher(repo))

    result = service.start_parse(course_id=201, idempotency_key="parse-sync-success")

    task = repo.get_async_task(result["taskId"])
    assert task is not None
    assert task["status"] == "succeeded"
    assert result["status"] == "queued"
    assert result["nextAction"] == "poll"
    assert result["entity"]["type"] == "parse_run"


@pytest.mark.parametrize(
    ("task_type", "expected_dispatcher_key", "payload"),
    [
        ("parse_pipeline", "parse_pipeline", {"courseId": 201, "parseRunId": 9001}),
        ("handout_generate", "handout_generate", {"courseId": 201, "handoutVersionId": 11}),
        ("handout_block_generate", "handout_block_generate", {"courseId": 201, "handoutBlockId": 12}),
        ("quiz_generate", "quiz_generate", {"courseId": 201, "quizId": 13}),
        ("review_refresh", "review_refresh", {"courseId": 201, "reviewTaskRunId": 14}),
        ("bilibili_import", "bilibili_import", {"courseId": 201, "importRunId": 15}),
    ],
)
def test_retry_async_task_reenqueues_supported_task_types(
    task_type: str,
    expected_dispatcher_key: str,
    payload: dict[str, Any],
):
    repo = _PipelineRepo()
    repo.tasks[42] = {
        "taskId": 42,
        "courseId": 201,
        "taskType": task_type,
        "status": "failed",
        "progressPct": 100,
        "payloadJson": payload,
    }
    dispatcher = _RecordingDispatcher()
    service = _pipeline_service(repo, dispatcher)

    result = service.retry_async_task(task_id=42)

    assert result == {"taskId": 42, "status": "queued", "nextAction": "poll"}
    assert repo.tasks[42]["status"] == "queued"
    assert repo.tasks[42]["progressPct"] == 0
    assert dispatcher.calls == [(expected_dispatcher_key, 42, payload)]


def test_retry_async_task_clears_previous_error_fields():
    repo = _PipelineRepo()
    repo.tasks[42] = {
        "taskId": 42,
        "courseId": 201,
        "taskType": "quiz_generate",
        "status": "failed",
        "progressPct": 100,
        "payloadJson": {"courseId": 201, "quizId": 13},
        "errorCode": "async_task.enqueue_failed",
        "errorMessage": "broker offline",
    }
    dispatcher = _RecordingDispatcher()
    service = _pipeline_service(repo, dispatcher)

    service.retry_async_task(task_id=42)

    assert repo.tasks[42]["errorCode"] is None
    assert repo.tasks[42]["errorMessage"] is None


def test_retry_async_task_rejects_succeeded_task():
    repo = _PipelineRepo()
    repo.tasks[42] = {
        "taskId": 42,
        "courseId": 201,
        "taskType": "quiz_generate",
        "status": "succeeded",
        "progressPct": 100,
        "payloadJson": {"courseId": 201, "quizId": 13},
    }
    dispatcher = _RecordingDispatcher()
    service = _pipeline_service(repo, dispatcher)

    with pytest.raises(ServiceError) as exc_info:
        service.retry_async_task(task_id=42)

    assert exc_info.value.error_code == "pipeline.task_not_retryable"
    assert exc_info.value.status_code == 409
    assert dispatcher.calls == []


def test_retry_async_task_rejects_canceled_task():
    repo = _PipelineRepo()
    repo.tasks[42] = {
        "taskId": 42,
        "courseId": 201,
        "taskType": "quiz_generate",
        "status": "canceled",
        "progressPct": 0,
        "payloadJson": {"courseId": 201, "quizId": 13},
    }
    dispatcher = _RecordingDispatcher()
    service = _pipeline_service(repo, dispatcher)

    with pytest.raises(ServiceError) as exc_info:
        service.retry_async_task(task_id=42)

    assert exc_info.value.error_code == "pipeline.task_not_retryable"
    assert exc_info.value.status_code == 409
    assert dispatcher.calls == []


def test_retry_async_task_rejects_unknown_status_without_requeueing():
    repo = _PipelineRepo()
    repo.tasks[42] = {
        "taskId": 42,
        "courseId": 201,
        "taskType": "quiz_generate",
        "status": "paused",
        "progressPct": 25,
        "payloadJson": {"courseId": 201, "quizId": 13},
    }
    dispatcher = _RecordingDispatcher()
    service = _pipeline_service(repo, dispatcher)

    with pytest.raises(ServiceError) as exc_info:
        service.retry_async_task(task_id=42)

    assert exc_info.value.error_code == "pipeline.task_not_retryable"
    assert exc_info.value.status_code == 409
    assert repo.tasks[42]["status"] == "paused"
    assert dispatcher.calls == []


def test_retry_async_task_does_not_enqueue_when_status_update_is_stale():
    repo = _StaleUpdatePipelineRepo()
    repo.tasks[42] = {
        "taskId": 42,
        "courseId": 201,
        "taskType": "quiz_generate",
        "status": "failed",
        "progressPct": 100,
        "payloadJson": {"courseId": 201, "quizId": 13},
    }
    dispatcher = _RecordingDispatcher()
    service = _pipeline_service(repo, dispatcher)

    with pytest.raises(ServiceError) as exc_info:
        service.retry_async_task(task_id=42)

    assert exc_info.value.status_code in {404, 409}
    assert dispatcher.calls == []


def test_quiz_generate_marks_task_failed_when_enqueue_fails():
    repo = _QuizRepo()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=_FailingDispatcher("quiz_generate"),
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_quiz(course_id=301, question_count_level="short", idempotency_key="quiz-enqueue-fails")

    task = next(iter(repo.tasks.values()))
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in task["errorMessage"]


def test_quiz_generate_rejects_queued_poll_trigger_missing_task_id():
    repo = _MissingQuizTaskIdRepo()
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_quiz(
            course_id=301,
            question_count_level="short",
            idempotency_key="quiz-missing-task-id",
        )

    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert dispatcher.calls == []


def test_quiz_generate_rejects_unverified_created_async_task_without_enqueueing():
    repo = _QuizRepo()
    async_tasks = _UnverifiedAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_quiz(
            course_id=301,
            question_count_level="short",
            idempotency_key="quiz-unverified-created-task",
        )

    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert async_tasks.tasks == {}
    assert dispatcher.calls == []


def test_quiz_generate_running_trigger_returns_poll_without_reenqueue_or_new_async_task():
    repo = _RunningQuizRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    result = service.generate_quiz(
        course_id=301,
        question_count_level="short",
        idempotency_key="quiz-running-trigger",
    )

    assert result["status"] == "running"
    assert result["nextAction"] == "poll"
    assert result["taskId"] in repo.tasks
    assert repo.tasks[result["taskId"]]["status"] == "running"
    assert async_tasks.tasks == {}
    assert dispatcher.calls == []


def test_generate_flows_mark_task_failed_when_dispatcher_is_missing():
    quiz_repo = _QuizRepo()
    quiz_service = QuizService(
        courses=quiz_repo,
        quizzes=quiz_repo,
        idempotency=quiz_repo,
    )

    with pytest.raises(ServiceError) as quiz_exc:
        quiz_service.generate_quiz(
            course_id=301,
            question_count_level="short",
            idempotency_key="quiz-missing-dispatcher",
        )

    quiz_task = next(iter(quiz_repo.tasks.values()))
    assert quiz_exc.value.error_code == "async_task.enqueue_failed"
    assert quiz_task["status"] == "failed"
    assert quiz_task["errorCode"] == "async_task.enqueue_failed"
    assert "dispatcher" in quiz_task["errorMessage"].lower()

    review_repo = _ReviewRepo()
    review_service = ReviewService(
        courses=review_repo,
        reviews=review_repo,
        idempotency=review_repo,
    )

    with pytest.raises(ServiceError) as review_exc:
        review_service.regenerate_review_tasks(course_id=401, idempotency_key="review-missing-dispatcher")

    review_task = next(iter(review_repo.tasks.values()))
    assert review_exc.value.error_code == "async_task.enqueue_failed"
    assert review_task["status"] == "failed"
    assert review_task["errorCode"] == "async_task.enqueue_failed"
    assert "dispatcher" in review_task["errorMessage"].lower()

    handout_repo = _HandoutRepo()
    handout_service = HandoutService(
        courses=handout_repo,
        handouts=handout_repo,
        idempotency=handout_repo,
    )

    with pytest.raises(ServiceError) as handout_exc:
        handout_service.generate_handout(course_id=501, idempotency_key="handout-missing-dispatcher")

    handout_task = next(task for task in handout_repo.tasks.values() if task["taskType"] == "handout_generate")
    assert handout_exc.value.error_code == "async_task.enqueue_failed"
    assert handout_task["status"] == "failed"
    assert handout_task["errorCode"] == "async_task.enqueue_failed"
    assert "dispatcher" in handout_task["errorMessage"].lower()

    block_repo = _HandoutRepo()
    block_service = HandoutService(
        courses=block_repo,
        handouts=block_repo,
        idempotency=block_repo,
    )

    with pytest.raises(ServiceError) as block_exc:
        block_service.generate_block(block_id=block_repo.block_id, idempotency_key="block-missing-dispatcher")

    block_task = next(task for task in block_repo.tasks.values() if task["taskType"] == "handout_block_generate")
    assert block_exc.value.error_code == "async_task.enqueue_failed"
    assert block_task["status"] == "failed"
    assert block_task["errorCode"] == "async_task.enqueue_failed"
    assert "dispatcher" in block_task["errorMessage"].lower()


def test_review_regenerate_marks_task_failed_when_enqueue_fails():
    repo = _ReviewRepo()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=_FailingDispatcher("review_refresh"),
    )

    with pytest.raises(ServiceError) as exc_info:
        service.regenerate_review_tasks(course_id=401, idempotency_key="review-enqueue-fails")

    task = next(iter(repo.tasks.values()))
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in task["errorMessage"]


def test_review_regenerate_rejects_refresh_task_missing_task_id():
    repo = _ReviewMissingRefreshTaskIdRepo()
    dispatcher = _RecordingDispatcher()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.regenerate_review_tasks(course_id=401, idempotency_key="review-missing-task-id")

    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert dispatcher.calls == []


def test_review_regenerate_rejects_refresh_task_invalid_payload_and_marks_task_failed():
    repo = _ReviewInvalidRefreshPayloadRepo()
    dispatcher = _RecordingDispatcher()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.regenerate_review_tasks(course_id=401, idempotency_key="review-invalid-payload")

    task = next(iter(repo.tasks.values()))
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert dispatcher.calls == []


def test_review_regenerate_returns_ready_run_when_repo_has_no_refresh_task():
    repo = _ReviewReadyRepo()
    dispatcher = _RecordingDispatcher()
    service = ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
    )

    result = service.regenerate_review_tasks(course_id=402, idempotency_key="review-ready")

    assert result == {
        "reviewTaskRunId": 2001,
        "courseId": 402,
        "status": "ready",
        "generatedCount": 3,
    }
    assert "taskId" not in result
    assert result.get("nextAction") != "poll"
    assert dispatcher.calls == []


def test_handout_generate_marks_task_failed_when_enqueue_fails():
    repo = _HandoutRepo()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=_FailingDispatcher("handout_generate"),
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_handout(course_id=501, idempotency_key="handout-enqueue-fails")

    task = next(task for task in repo.tasks.values() if task["taskType"] == "handout_generate")
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in task["errorMessage"]


def test_handout_generate_rejects_queued_poll_trigger_missing_entity_id_and_marks_task_failed():
    repo = _HandoutMissingEntityRepo()
    dispatcher = _RecordingDispatcher()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_handout(course_id=501, idempotency_key="handout-missing-entity-id")

    task = next(task for task in repo.tasks.values() if task["taskType"] == "handout_generate")
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert dispatcher.calls == []


def test_api_service_dependencies_pass_separate_async_task_repository():
    repo = _RepoWithoutAsyncTasks()
    async_tasks = _SeparateAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()

    handout_service = asyncio.run(
        get_handout_service(repo=repo, async_tasks=async_tasks, task_dispatcher=dispatcher)
    )
    quiz_service = asyncio.run(
        get_quiz_service(repo=repo, async_tasks=async_tasks, task_dispatcher=dispatcher)
    )
    review_service = asyncio.run(
        get_review_service(repo=repo, async_tasks=async_tasks, task_dispatcher=dispatcher)
    )

    assert handout_service.async_tasks is async_tasks
    assert quiz_service.async_tasks is async_tasks
    assert review_service.async_tasks is async_tasks


def test_generate_flows_create_real_async_task_when_async_repo_is_separate():
    quiz_repo = _QuizRepo()
    quiz_async_tasks = _SeparateAsyncTaskRepo()
    quiz_dispatcher = _RecordingDispatcher()
    quiz_service = QuizService(
        courses=quiz_repo,
        quizzes=quiz_repo,
        idempotency=quiz_repo,
        task_dispatcher=quiz_dispatcher,
        async_tasks=quiz_async_tasks,
    )

    quiz_result = quiz_service.generate_quiz(
        course_id=301,
        question_count_level="short",
        idempotency_key="quiz-separate-async",
    )

    quiz_task = quiz_async_tasks.get_async_task(quiz_result["taskId"])
    assert quiz_task is not None
    assert quiz_result["taskId"] not in quiz_repo.tasks
    assert quiz_task["taskType"] == "quiz_generate"
    assert quiz_task["targetType"] == "quiz"
    assert quiz_dispatcher.calls == [("quiz_generate", quiz_result["taskId"], quiz_task["payloadJson"])]

    handout_repo = _HandoutRepo()
    handout_async_tasks = _SeparateAsyncTaskRepo()
    handout_dispatcher = _RecordingDispatcher()
    handout_service = HandoutService(
        courses=handout_repo,
        handouts=handout_repo,
        idempotency=handout_repo,
        task_dispatcher=handout_dispatcher,
        async_tasks=handout_async_tasks,
    )

    handout_result = handout_service.generate_handout(
        course_id=501,
        idempotency_key="handout-separate-async",
    )

    handout_task = handout_async_tasks.get_async_task(handout_result["taskId"])
    assert handout_task is not None
    assert handout_result["taskId"] not in handout_repo.tasks
    assert handout_task["taskType"] == "handout_generate"
    assert handout_task["targetType"] == "handout_version"
    assert handout_dispatcher.calls == [
        ("handout_generate", handout_result["taskId"], handout_task["payloadJson"])
    ]

    review_repo = _ReviewRepo()
    review_async_tasks = _SeparateAsyncTaskRepo()
    review_dispatcher = _RecordingDispatcher()
    review_service = ReviewService(
        courses=review_repo,
        reviews=review_repo,
        idempotency=review_repo,
        task_dispatcher=review_dispatcher,
        async_tasks=review_async_tasks,
    )

    review_result = review_service.regenerate_review_tasks(
        course_id=401,
        idempotency_key="review-separate-async",
    )

    review_task = review_async_tasks.get_async_task(review_result["taskId"])
    assert review_task is not None
    assert review_result["taskId"] not in review_repo.tasks
    assert review_task["taskType"] == "review_refresh"
    assert review_task["targetType"] == "review_task_run"
    assert review_dispatcher.calls == [
        ("review_refresh", review_result["taskId"], review_task["payloadJson"])
    ]


def test_generate_flow_does_not_reuse_mismatched_existing_async_task_id():
    repo = _QuizRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    async_tasks.tasks[9101] = {
        "taskId": 9101,
        "courseId": 999,
        "parseRunId": None,
        "taskType": "handout_generate",
        "status": "queued",
        "progressPct": 0,
        "payloadJson": {"courseId": 999, "handoutVersionId": 1},
        "targetType": "handout_version",
        "targetId": 1,
    }
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    result = service.generate_quiz(
        course_id=301,
        question_count_level="short",
        idempotency_key="quiz-mismatched-existing-task",
    )

    task = async_tasks.get_async_task(result["taskId"])
    assert result["taskId"] != 9101
    assert task is not None
    assert task["taskType"] == "quiz_generate"
    assert task["targetType"] == "quiz"
    assert task["courseId"] == 301
    assert dispatcher.calls == [("quiz_generate", result["taskId"], task["payloadJson"])]


def test_helper_created_async_task_idempotency_replay_does_not_recreate_or_reenqueue():
    repo = _QuizRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    first = service.generate_quiz(
        course_id=301,
        question_count_level="short",
        idempotency_key="quiz-helper-created-replay",
    )
    second = service.generate_quiz(
        course_id=301,
        question_count_level="short",
        idempotency_key="quiz-helper-created-replay",
    )

    assert second["taskId"] == first["taskId"]
    assert list(async_tasks.tasks) == [first["taskId"]]
    assert dispatcher.calls == [
        ("quiz_generate", first["taskId"], async_tasks.tasks[first["taskId"]]["payloadJson"])
    ]


def test_handout_block_create_real_async_task_when_async_repo_is_separate():
    repo = _HandoutRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    result = service.generate_block(block_id=repo.block_id, idempotency_key="block-separate-async")

    task = async_tasks.get_async_task(result["taskId"])
    assert task is not None
    assert result["taskId"] not in repo.tasks
    assert task["taskType"] == "handout_block_generate"
    assert task["targetType"] == "handout_block"
    assert dispatcher.calls == [("handout_block_generate", result["taskId"], task["payloadJson"])]


def test_handout_block_generate_replays_existing_old_scoped_idempotency_action():
    repo = _HandoutRepo()
    dispatcher = _RecordingDispatcher()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=repo,
    )
    stored_result = {
        "taskId": 7777,
        "status": "queued",
        "nextAction": "poll",
        "entity": {"type": "handout_block", "id": repo.block_id},
    }
    repo.idempotency[(f"handout_blocks.generate:{repo.block_id}", "legacy-block-key")] = stored_result

    result = service.generate_block(block_id=repo.block_id, idempotency_key="legacy-block-key")

    assert result == stored_result
    assert repo.tasks == {}
    assert dispatcher.calls == []


def test_handout_block_generating_without_enqueue_request_does_not_create_tracking_task():
    repo = _HandoutGeneratingRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    result = service.generate_block(block_id=repo.block_id, idempotency_key="block-generating-separate-async")

    assert result["blockId"] == repo.block_id
    assert result["status"] == "generating"
    assert "taskId" not in result
    assert "nextAction" not in result
    assert async_tasks.tasks == {}
    assert dispatcher.calls == []


def test_quiz_submit_review_refresh_uses_real_async_task_when_async_repo_is_separate():
    repo = _QuizSubmitRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    dispatcher = _RecordingDispatcher()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=dispatcher,
        async_tasks=async_tasks,
    )

    result = service.submit_quiz(quiz_id=repo.quiz["quizId"], payload=_QuizSubmitPayload())

    task = next(iter(async_tasks.tasks.values()))
    assert result["reviewTaskRunId"] == task["targetId"]
    assert task["taskType"] == "review_refresh"
    assert task["targetType"] == "review_task_run"
    assert dispatcher.calls == [("review_refresh", task["taskId"], task["payloadJson"])]


def test_enqueue_failure_marks_real_async_task_when_async_repo_is_separate():
    repo = _QuizRepo()
    async_tasks = _SeparateAsyncTaskRepo()
    service = QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=_FailingDispatcher("quiz_generate"),
        async_tasks=async_tasks,
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_quiz(
            course_id=301,
            question_count_level="short",
            idempotency_key="quiz-separate-async-fails",
        )

    task = next(iter(async_tasks.tasks.values()))
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in task["errorMessage"]


def test_handout_block_generate_marks_task_failed_when_enqueue_fails():
    repo = _HandoutRepo()
    service = HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=_FailingDispatcher("handout_block_generate"),
    )

    with pytest.raises(ServiceError) as exc_info:
        service.generate_block(block_id=repo.block_id, idempotency_key="handout-block-enqueue-fails")

    task = next(task for task in repo.tasks.values() if task["taskType"] == "handout_block_generate")
    assert exc_info.value.error_code == "async_task.enqueue_failed"
    assert exc_info.value.status_code == 503
    assert task["status"] == "failed"
    assert task["errorCode"] == "async_task.enqueue_failed"
    assert "broker offline" in task["errorMessage"]
