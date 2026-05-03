from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RuntimeStore:
    lock: Lock = field(default_factory=Lock)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "course": 100,
            "resource": 500,
            "task": 7000,
            "parse_run": 9000,
            "handout_version": 3000,
            "handout_block": 4000,
            "qa_session": 6000,
            "qa_message": 6100,
            "quiz": 8000,
            "question": 8100,
            "attempt": 8200,
            "review_run": 8300,
            "review_task": 8400,
        }
    )
    idempotency: dict[tuple[str, str], Any] = field(default_factory=dict)
    courses: dict[int, dict[str, Any]] = field(default_factory=dict)
    resources: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    parse_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    inquiry_answers: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    handouts: dict[int, dict[str, Any]] = field(default_factory=dict)
    handout_by_course: dict[int, int] = field(default_factory=dict)
    quizzes: dict[int, dict[str, Any]] = field(default_factory=dict)
    qa_sessions: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    review_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    review_tasks: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    progress: dict[int, dict[str, Any]] = field(default_factory=dict)

    def next_id(self, key: str) -> int:
        with self.lock:
            self.counters[key] += 1
            return self.counters[key]

    def run_idempotent(self, action: str, key: str | None, factory):
        if not key:
            return factory()
        slot = (action, key)
        with self.lock:
            if slot in self.idempotency:
                return self.idempotency[slot]
        value = factory()
        with self.lock:
            self.idempotency[slot] = value
        return value

    def create_course(
        self,
        *,
        title: str,
        entry_type: str,
        goal_text: str,
        preferred_style: str,
        catalog_id: str | None = None,
    ) -> dict[str, Any]:
        course_id = self.next_id("course")
        course = {
            "courseId": course_id,
            "title": title,
            "entryType": entry_type,
            "catalogId": catalog_id,
            "goalText": goal_text,
            "preferredStyle": preferred_style,
            "lifecycleStatus": "draft",
            "pipelineStage": "idle",
            "pipelineStatus": "idle",
            "updatedAt": utcnow(),
        }
        self.courses[course_id] = course
        self.resources.setdefault(course_id, [])
        self.progress.setdefault(course_id, {"courseId": course_id, "lastActivityAt": utcnow()})
        return course

    def list_recent_courses(self) -> list[dict[str, Any]]:
        return sorted(
            self.courses.values(),
            key=lambda course: course["updatedAt"],
            reverse=True,
        )

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        return self.courses.get(course_id)

    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        resource_id = self.next_id("resource")
        resource = {
            "resourceId": resource_id,
            "resourceType": payload["resourceType"],
            "originalName": payload["originalName"],
            "objectKey": payload["objectKey"],
            "ingestStatus": "ready",
            "validationStatus": "passed",
            "processingStatus": "pending",
        }
        self.resources.setdefault(course_id, []).append(resource)
        return resource

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.resources.get(course_id, [])

    def create_parse_run(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        parse_run_id = self.next_id("parse_run")
        task_id = self.next_id("task")
        run = {
            "parseRunId": parse_run_id,
            "courseId": course_id,
            "status": "succeeded",
            "progressPct": 100,
            "startedAt": utcnow(),
            "finishedAt": utcnow(),
        }
        self.parse_runs[parse_run_id] = run
        course = self.courses[course_id]
        course["lifecycleStatus"] = "inquiry_ready"
        course["pipelineStage"] = "parse"
        course["pipelineStatus"] = "succeeded"
        course["activeParseRunId"] = parse_run_id
        course["updatedAt"] = utcnow()
        return run, {
            "taskId": task_id,
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "parse_run", "id": parse_run_id},
        }

    def get_latest_parse_run(self, course_id: int) -> dict[str, Any] | None:
        parse_run_id = self.courses.get(course_id, {}).get("activeParseRunId")
        if parse_run_id is None:
            return None
        return self.parse_runs.get(parse_run_id)

    def mark_parse_run_succeeded(self, parse_run_id: int) -> dict[str, Any] | None:
        run = self.parse_runs.get(parse_run_id)
        if run is None:
            return None
        finished_at = utcnow()
        run["status"] = "succeeded"
        run["progressPct"] = 100
        run["finishedAt"] = finished_at
        course = self.courses.get(run["courseId"])
        if course is not None:
            course["lifecycleStatus"] = "inquiry_ready"
            course["pipelineStage"] = "parse"
            course["pipelineStatus"] = "succeeded"
            course["activeParseRunId"] = parse_run_id
            course["updatedAt"] = finished_at
        return run

    def save_inquiry_answers(self, course_id: int, answers: list[dict[str, Any]]) -> dict[str, Any]:
        self.inquiry_answers[course_id] = answers
        return {"saved": True, "answerCount": len(answers)}

    def create_handout(
        self,
        course_id: int,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        handout_version_id = self.next_id("handout_version")
        task_id = self.next_id("task")
        parse_run = self.get_latest_parse_run(course_id)
        blocks = []
        materials = [
            ("极限与连续", {"pageNo": 2}),
            ("导数与微分", {"slideNo": 6}),
            ("积分与应用", {"anchorKey": "section-integral"}),
        ]
        for index, (block_title, location) in enumerate(materials):
            block_id = self.next_id("handout_block")
            outline_key = f"outline-{index + 1}"
            start_sec = 120 + index * 300
            end_sec = 300 + index * 300
            citation = {
                "resourceId": 501 + index,
                "refLabel": "结构化来源锚点",
                **location,
            }
            blocks.append(
                {
                    "blockId": block_id,
                    "outlineKey": outline_key,
                    "title": block_title,
                    "summary": "按考试优先级整理的知识块",
                    "status": "ready",
                    "contentMd": f"### {block_title}\n- 重点：定义、题型、常见陷阱",
                    "startSec": start_sec,
                    "endSec": end_sec,
                    "sourceSegmentKeys": [f"memory-{outline_key}-source"],
                    "pageFrom": location.get("pageNo"),
                    "pageTo": (location.get("pageNo") or 0) + 1 if "pageNo" in location else None,
                    "slideNo": location.get("slideNo"),
                    "anchorKey": location.get("anchorKey"),
                    "citations": [citation],
                }
            )

        outline = {
            "handoutVersionId": handout_version_id,
            "title": "高数期末冲刺讲义",
            "summary": "按演示讲义块组织的目录",
            "items": [
                {
                    "outlineKey": block["outlineKey"],
                    "blockId": block["blockId"],
                    "title": block["title"],
                    "summary": block["summary"],
                    "startSec": block["startSec"],
                    "endSec": block["endSec"],
                    "sortNo": index + 1,
                    "generationStatus": "ready",
                    "sourceSegmentKeys": block["sourceSegmentKeys"],
                }
                for index, block in enumerate(blocks)
            ],
        }
        handout = {
            "handoutVersionId": handout_version_id,
            "title": "高数期末冲刺讲义",
            "summary": "按考试优先级整理的知识块",
            "totalBlocks": len(blocks),
            "status": "ready",
            "outlineStatus": "ready",
            "readyBlocks": len(blocks),
            "pendingBlocks": 0,
            "sourceParseRunId": parse_run["parseRunId"] if parse_run else None,
            "outline": outline,
            "blocks": blocks,
        }
        self.handouts[handout_version_id] = handout
        self.handout_by_course[course_id] = handout_version_id
        course = self.courses[course_id]
        course["activeHandoutVersionId"] = handout_version_id
        course["lifecycleStatus"] = "learning_ready"
        course["pipelineStage"] = "handout"
        course["pipelineStatus"] = "succeeded"
        course["updatedAt"] = utcnow()
        return handout, {
            "taskId": task_id,
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "handout_version", "id": handout_version_id},
        }, blocks

    def get_latest_handout(self, course_id: int) -> dict[str, Any] | None:
        handout_version_id = self.handout_by_course.get(course_id)
        if handout_version_id is None:
            return None
        return self.handouts.get(handout_version_id)

    def get_latest_outline(self, course_id: int) -> dict[str, Any] | None:
        handout = self.get_latest_handout(course_id)
        if handout is None:
            return None
        outline = handout.get("outline")
        if isinstance(outline, dict):
            return outline
        return None

    def create_qa_message(self, course_id: int, handout_block_id: int) -> dict[str, Any]:
        session_id = self.next_id("qa_session")
        message_id = self.next_id("qa_message")
        handout = self.get_latest_handout(course_id)
        block = next(
            (item for item in handout["blocks"] if item["blockId"] == handout_block_id),
            None,
        )
        citation = (
            block["citations"][0]
            if block
            else {"resourceId": 501, "refLabel": "PDF 第 2 页", "pageNo": 2}
        )
        payload = {
            "sessionId": session_id,
            "messageId": message_id,
            "answerMd": "定义决定了题型判断的边界，先记判定条件，再看典型题型转换。",
            "citations": [citation],
        }
        self.qa_sessions[session_id] = [payload]
        return payload

    def get_qa_session_messages(self, session_id: int) -> list[dict[str, Any]] | None:
        return self.qa_sessions.get(session_id)

    def create_quiz(self, course_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
        quiz_id = self.next_id("quiz")
        task_id = self.next_id("task")
        questions = []
        for stem in [
            "下列关于极限的说法哪项正确？",
            "导数的几何意义是？",
            "定积分最常见的考试用途是？",
        ]:
            question_id = self.next_id("question")
            questions.append(
                {
                    "questionId": question_id,
                    "stemMd": stem,
                    "options": ["A", "B", "C", "D"],
                }
            )
        quiz = {
            "quizId": quiz_id,
            "courseId": course_id,
            "status": "ready",
            "questionCount": len(questions),
            "questions": questions,
        }
        self.quizzes[quiz_id] = quiz
        return quiz, {
            "taskId": task_id,
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "quiz", "id": quiz_id},
        }

    def submit_quiz(self, quiz_id: int) -> dict[str, Any]:
        attempt_id = self.next_id("attempt")
        review_run = self.create_review_run(self.quizzes[quiz_id]["courseId"])
        return {
            "attemptId": attempt_id,
            "score": 100,
            "totalScore": 100,
            "accuracy": 1.0,
            "reviewTaskRunId": review_run["reviewTaskRunId"],
            "masteryDelta": [
                {"knowledgePoint": "极限定义", "delta": 0.2, "status": "improved"},
                {"knowledgePoint": "导数几何意义", "delta": 0.1, "status": "stable"},
            ],
            "recommendedReviewAction": {
                "type": "revisit_block",
                "targetBlockId": 4001,
                "reason": "建议先回看易错知识块，再进入下一轮练习。",
            },
        }

    def create_review_run(self, course_id: int) -> dict[str, Any]:
        review_run_id = self.next_id("review_run")
        tasks = []
        for task_type, priority, minutes in [
            ("revisit_block", 95, 20),
            ("redo_quiz", 80, 15),
            ("formula_drill", 70, 10),
        ]:
            task_id = self.next_id("review_task")
            tasks.append(
                {
                    "reviewTaskId": task_id,
                    "taskType": task_type,
                    "priorityScore": priority,
                    "reasonText": "该知识块仍是当前最值得复习的高频内容",
                    "recommendedMinutes": minutes,
                    "recommendedSegment": {
                        "blockId": 4000 + len(tasks) + 1,
                        "startSec": 120 + len(tasks) * 180,
                        "endSec": 240 + len(tasks) * 180,
                        "label": "建议优先回看片段",
                    },
                    "practiceEntry": {
                        "type": "quiz",
                        "targetId": 8001,
                        "label": "再练 1 题",
                    },
                    "reviewOrder": len(tasks) + 1,
                    "intensity": "high" if priority >= 90 else "medium",
                }
            )
        run = {
            "reviewTaskRunId": review_run_id,
            "courseId": course_id,
            "status": "ready",
            "generatedCount": len(tasks),
        }
        self.review_runs[review_run_id] = run
        self.review_tasks[course_id] = tasks
        return run

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        if course_id not in self.review_tasks:
            self.create_review_run(course_id)
        return self.review_tasks.get(course_id, [])

    def get_review_run(self, review_run_id: int) -> dict[str, Any] | None:
        return self.review_runs.get(review_run_id)

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.progress.get(course_id, {"courseId": course_id})
        current.update(payload)
        current["lastActivityAt"] = utcnow()
        self.progress[course_id] = current
        return current

    def get_progress(self, course_id: int) -> dict[str, Any]:
        return self.progress.get(course_id, {"courseId": course_id, "lastActivityAt": utcnow()})


runtime_store = RuntimeStore()
