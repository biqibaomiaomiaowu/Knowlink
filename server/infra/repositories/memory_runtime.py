from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from threading import Lock
from typing import Any, Mapping, Sequence

from server.ai.qa_types import LexicalSearchHit, QaScope, VectorSearchHit
from server.domain.services.idempotency import (
    IDEMPOTENCY_EXPIRES_IN,
    raise_idempotency_body_mismatch,
    raise_idempotency_in_progress,
)
from server.parsers.base import clean_text


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _scoped_idempotency_record_expired(expires_at: object) -> bool:
    if not isinstance(expires_at, datetime):
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= utcnow()


def _qa_scope_block_label(block: Mapping[str, Any]) -> str:
    parts = [
        str(value).strip()
        for value in (block.get("title"), block.get("summary"))
        if isinstance(value, str) and value.strip()
    ]
    return " ".join(parts)


def _qa_scope_knowledge_point_names(blocks: Sequence[Mapping[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        points = block.get("knowledgePoints")
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, Mapping):
                continue
            name = point.get("displayName") or point.get("name") or point.get("knowledgePointKey")
            if not isinstance(name, str):
                continue
            normalized = name.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                names.append(normalized)
    return names


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
            "bilibili_import_run": 9100,
            "bilibili_qr_session": 9200,
            "bilibili_preview": 9300,
        }
    )
    idempotency: dict[tuple[str, str], Any] = field(default_factory=dict)
    idempotency_records: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    courses: dict[int, dict[str, Any]] = field(default_factory=dict)
    resources: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    parse_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    inquiry_answers: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    handouts: dict[int, dict[str, Any]] = field(default_factory=dict)
    handout_by_course: dict[int, int] = field(default_factory=dict)
    quizzes: dict[int, dict[str, Any]] = field(default_factory=dict)
    qa_sessions: dict[int, dict[str, Any]] = field(default_factory=dict)
    review_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    review_tasks: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    async_tasks: dict[int, dict[str, Any]] = field(default_factory=dict)
    progress: dict[int, dict[str, Any]] = field(default_factory=dict)
    bilibili_qr_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    bilibili_auth_session: dict[str, Any] | None = None
    bilibili_preview_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    bilibili_import_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    current_course_id: int | None = None

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

    def get_idempotency_result(self, action: str, key: str | None):
        if not key:
            return None
        with self.lock:
            return self.idempotency.get((action, key))

    def run_scoped_idempotent(self, *, scope: str, key: str, request_hash: str, factory):
        slot = (scope, key)
        with self.lock:
            existing = self.idempotency_records.get(slot)
            if existing is not None:
                if _scoped_idempotency_record_expired(existing.get("expiresAt")):
                    self.idempotency_records.pop(slot, None)
                    existing = None
            if existing is not None:
                if existing.get("requestHash") != request_hash:
                    raise_idempotency_body_mismatch()
                if existing.get("status") == "in_progress":
                    raise_idempotency_in_progress()
                return existing.get("responseJson")
            self.idempotency_records[slot] = {
                "scope": scope,
                "key": key,
                "requestHash": request_hash,
                "status": "in_progress",
                "responseJson": None,
                "expiresAt": utcnow() + IDEMPOTENCY_EXPIRES_IN,
            }
        try:
            value = factory()
        except Exception:
            with self.lock:
                current = self.idempotency_records.get(slot)
                if current is not None and current.get("status") == "in_progress":
                    self.idempotency_records.pop(slot, None)
            raise
        with self.lock:
            self.idempotency_records[slot] = {
                "scope": scope,
                "key": key,
                "requestHash": request_hash,
                "status": "succeeded",
                "responseJson": value,
                "expiresAt": utcnow() + IDEMPOTENCY_EXPIRES_IN,
            }
        return value

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
        course_id = self.next_id("course")
        course = {
            "courseId": course_id,
            "title": title,
            "entryType": entry_type,
            "catalogId": catalog_id,
            "goalText": goal_text,
            "examAt": exam_at,
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

    def set_current_course(self, course_id: int) -> dict[str, Any] | None:
        course = self.get_course(course_id)
        if course is None:
            return None
        course["updatedAt"] = utcnow()
        self.current_course_id = course_id
        return course

    def get_current_course(self) -> dict[str, Any] | None:
        if self.current_course_id is not None:
            course = self.get_course(self.current_course_id)
            if course is not None:
                return course
        recent = self.list_recent_courses()
        return recent[0] if recent else None

    def create_bilibili_qr_session(
        self,
        *,
        qr_key: str,
        qr_url: str,
        status: str = "pending_scan",
        poll_payload_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        session = {
            "qrSessionId": self.next_id("bilibili_qr_session"),
            "qrKey": qr_key,
            "qrUrl": qr_url,
            "status": status,
            "pollPayloadJson": poll_payload_json,
            "errorCode": None,
            "failureReason": None,
            "scannedAt": None,
            "confirmedAt": None,
            "expiresAt": expires_at,
            "createdAt": utcnow(),
            "updatedAt": utcnow(),
        }
        self.bilibili_qr_sessions[qr_key] = session
        return session

    def get_bilibili_qr_session(self, qr_key: str) -> dict[str, Any] | None:
        return self.bilibili_qr_sessions.get(qr_key)

    def update_bilibili_qr_session(self, qr_key: str, **changes: Any) -> dict[str, Any] | None:
        session = self.bilibili_qr_sessions.get(qr_key)
        if session is None:
            return None
        field_map = {
            "status": "status",
            "poll_payload_json": "pollPayloadJson",
            "pollPayloadJson": "pollPayloadJson",
            "error_code": "errorCode",
            "errorCode": "errorCode",
            "failure_reason": "failureReason",
            "failureReason": "failureReason",
            "scanned_at": "scannedAt",
            "scannedAt": "scannedAt",
            "confirmed_at": "confirmedAt",
            "confirmedAt": "confirmedAt",
            "expires_at": "expiresAt",
            "expiresAt": "expiresAt",
        }
        for key, value in changes.items():
            target = field_map.get(key)
            if target is not None:
                session[target] = value
        session["updatedAt"] = utcnow()
        return session

    def save_bilibili_auth_session(
        self,
        *,
        cookies_json: dict[str, Any],
        csrf: str | None = None,
        expires_at: datetime | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        now = utcnow()
        auth_session = {
            "authSessionId": (self.bilibili_auth_session or {}).get("authSessionId", 1),
            "status": status,
            "cookiesJson": dict(cookies_json),
            "csrf": csrf,
            "expiresAt": expires_at,
            "lastVerifiedAt": now,
            "errorCode": None,
            "failureReason": None,
            "createdAt": (self.bilibili_auth_session or {}).get("createdAt", now),
            "updatedAt": now,
        }
        self.bilibili_auth_session = auth_session
        return auth_session

    def get_bilibili_auth_session(self) -> dict[str, Any] | None:
        return self.bilibili_auth_session

    def delete_bilibili_auth_session(self) -> bool:
        existed = self.bilibili_auth_session is not None
        self.bilibili_auth_session = None
        return existed

    def save_bilibili_preview_snapshot(
        self,
        *,
        preview_id: str,
        course_id: int,
        source_url: str,
        source_type: str,
        preview: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        existing = self.bilibili_preview_snapshots.get(preview_id)
        preview_snapshot_id = (
            existing["previewSnapshotId"]
            if existing is not None
            else self.next_id("bilibili_preview")
        )
        snapshot = {
            "previewSnapshotId": preview_snapshot_id,
            "previewId": preview_id,
            "courseId": course_id,
            "sourceUrl": source_url,
            "sourceType": source_type,
            "preview": dict(preview),
            "expiresAt": expires_at,
            "createdAt": (existing or {}).get("createdAt", now),
            "updatedAt": now,
        }
        self.bilibili_preview_snapshots[preview_id] = snapshot
        return snapshot

    def get_bilibili_preview_snapshot(self, preview_id: str) -> dict[str, Any] | None:
        return self.bilibili_preview_snapshots.get(preview_id)

    def create_bilibili_import_run(
        self,
        *,
        course_id: int,
        source_url: str,
        source_type: str,
        preview: dict[str, Any] | None = None,
        selection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        import_run_id = self.next_id("bilibili_import_run")
        run = {
            "importRunId": import_run_id,
            "courseId": course_id,
            "taskId": None,
            "sourceUrl": source_url,
            "sourceType": source_type,
            "status": "pending",
            "stage": "queued",
            "progressPct": 0,
            "preview": preview,
            "selection": selection,
            "resourceIds": [],
            "recoverable": False,
            "tempDir": None,
            "errorCode": None,
            "failureReason": None,
            "startedAt": now,
            "finishedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
        self.bilibili_import_runs[import_run_id] = run
        return run

    def get_bilibili_import_run(self, import_run_id: int) -> dict[str, Any] | None:
        return self.bilibili_import_runs.get(import_run_id)

    def list_bilibili_import_runs(self, course_id: int) -> list[dict[str, Any]]:
        return sorted(
            [
                run
                for run in self.bilibili_import_runs.values()
                if run["courseId"] == course_id
            ],
            key=lambda run: (run["createdAt"], run["importRunId"]),
            reverse=True,
        )

    def update_bilibili_import_run(self, import_run_id: int, **changes: Any) -> dict[str, Any] | None:
        run = self.bilibili_import_runs.get(import_run_id)
        if run is None:
            return None
        field_map = {
            "status": "status",
            "stage": "stage",
            "progress_pct": "progressPct",
            "progressPct": "progressPct",
            "task_id": "taskId",
            "taskId": "taskId",
            "preview": "preview",
            "preview_json": "preview",
            "selection": "selection",
            "selection_json": "selection",
            "resource_ids": "resourceIds",
            "resourceIds": "resourceIds",
            "recoverable": "recoverable",
            "temp_dir": "tempDir",
            "tempDir": "tempDir",
            "error_code": "errorCode",
            "errorCode": "errorCode",
            "failure_reason": "failureReason",
            "failureReason": "failureReason",
            "started_at": "startedAt",
            "startedAt": "startedAt",
            "finished_at": "finishedAt",
            "finishedAt": "finishedAt",
        }
        for key, value in changes.items():
            target = field_map.get(key)
            if target is not None:
                run[target] = value
        if (
            run.get("status") in {"imported", "failed", "recoverable", "canceled"}
            and "finished_at" not in changes
            and "finishedAt" not in changes
            and run.get("finishedAt") is None
        ):
            run["finishedAt"] = utcnow()
        run["updatedAt"] = utcnow()
        return run

    def create_resource(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        resource_id = self.next_id("resource")
        resource = {
            "resourceId": resource_id,
            "courseId": course_id,
            "resourceType": payload["resourceType"],
            "sourceType": payload.get("sourceType", "upload"),
            "originUrl": payload.get("originUrl"),
            "originalName": payload["originalName"],
            "objectKey": payload["objectKey"],
            "previewKey": payload.get("previewKey"),
            "mimeType": payload.get("mimeType"),
            "sizeBytes": payload.get("sizeBytes"),
            "checksum": payload.get("checksum"),
            "ingestStatus": "ready",
            "validationStatus": "passed",
            "processingStatus": "pending",
            "parsePolicyJson": payload.get("parsePolicyJson"),
        }
        self.resources.setdefault(course_id, []).append(resource)
        return resource

    def list_resources(self, course_id: int) -> list[dict[str, Any]]:
        return self.resources.get(course_id, [])

    def get_resource(self, resource_id: int) -> dict[str, Any] | None:
        for resources in self.resources.values():
            for resource in resources:
                if resource["resourceId"] == resource_id:
                    return resource
        return None

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
        self.register_async_task(
            task_id=task_id,
            course_id=course_id,
            task_type="parse_pipeline",
            status="queued",
            progress_pct=0,
            payload_json={"courseId": course_id, "parseRunId": parse_run_id},
            parse_run_id=parse_run_id,
            target_type="parse_run",
            target_id=parse_run_id,
        )
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
                    "summary": "按定义、题型和考试应用整理的知识块",
                    "status": "pending",
                    "generationStatus": "pending",
                    "contentMd": None,
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
                    "outlineKey": f"section-{index + 1}",
                    "title": block["title"],
                    "summary": block["summary"],
                    "startSec": block["startSec"],
                    "endSec": block["endSec"],
                    "sortNo": index + 1,
                    "children": [
                        {
                            "outlineKey": block["outlineKey"],
                            "blockId": block["blockId"],
                            "title": block["title"],
                            "summary": block["summary"],
                            "startSec": block["startSec"],
                            "endSec": block["endSec"],
                            "sortNo": index + 1,
                            "generationStatus": block["status"],
                            "sourceSegmentKeys": block["sourceSegmentKeys"],
                            "topicTags": [],
                        }
                    ],
                }
                for index, block in enumerate(blocks)
            ],
        }
        handout = {
            "handoutVersionId": handout_version_id,
            "title": "高数期末冲刺讲义",
            "summary": "按定义、题型和考试应用整理的知识块",
            "totalBlocks": len(blocks),
            "status": "outline_ready",
            "outlineStatus": "ready",
            "readyBlocks": 0,
            "pendingBlocks": len(blocks),
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
        payload = {
            "courseId": course_id,
            "handoutVersionId": handout_version_id,
            "sourceParseRunId": handout["sourceParseRunId"],
        }
        self.register_async_task(
            task_id=task_id,
            course_id=course_id,
            task_type="handout_generate",
            status="queued",
            progress_pct=0,
            payload_json=payload,
            parse_run_id=handout["sourceParseRunId"],
            target_type="handout_version",
            target_id=handout_version_id,
        )
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

    def get_qa_context(self, course_id: int, handout_block_id: int) -> dict[str, Any] | None:
        course = self.courses.get(course_id)
        handout = self.get_latest_handout(course_id)
        if course is None or handout is None:
            return None
        if handout.get("sourceParseRunId") != course.get("activeParseRunId"):
            return None
        block = next(
            (item for item in handout["blocks"] if item["blockId"] == handout_block_id),
            None,
        )
        if block is None:
            return None

        parse_run_id = course.get("activeParseRunId")
        handout_version_id = handout["handoutVersionId"]
        segments = self._qa_segments_from_memory_handout(
            course_id=course_id,
            parse_run_id=parse_run_id,
            handout=handout,
        )
        adjacent_blocks = [
            self._qa_block_payload_from_memory(
                adjacent,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
            )
            for adjacent in handout["blocks"]
            if adjacent["blockId"] != handout_block_id
            and abs(int(adjacent.get("startSec") or 0) - int(block.get("startSec") or 0)) <= 300
        ]
        ready_blocks = [
            self._qa_block_payload_from_memory(
                ready_block,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
            )
            for ready_block in handout["blocks"]
            if ready_block.get("status") == "ready" or ready_block.get("generationStatus") == "ready"
        ]
        return {
            "courseId": course_id,
            "activeCourseId": course_id,
            "activeParseRunId": parse_run_id,
            "activeHandoutVersionId": handout_version_id,
            "handoutBlockId": handout_block_id,
            "currentBlock": self._qa_block_payload_from_memory(
                block,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
            ),
            "segments": segments,
            "knowledgePointEvidences": [],
            "adjacentBlocks": adjacent_blocks,
            "readyBlocks": ready_blocks,
            "courseScope": self._qa_course_scope_from_memory(
                course=course,
                course_id=course_id,
                current_block=block,
                adjacent_blocks=adjacent_blocks,
            ),
        }

    def search_course_wide_original_segments(
        self,
        *,
        question: str,
        course_id: int | None,
        parse_run_id: int | None,
        handout_version_id: int | None = None,
        handout_block_id: int | str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        active_course_id = _as_positive_int(course_id)
        if active_course_id is None:
            return []
        course = self.courses.get(active_course_id)
        handout = self.get_latest_handout(active_course_id)
        if course is None or handout is None:
            return []
        active_parse_run_id = _as_positive_int(parse_run_id) or _as_positive_int(course.get("activeParseRunId"))
        if active_parse_run_id is None or handout.get("sourceParseRunId") != active_parse_run_id:
            return []
        normalized_limit = _normalized_search_limit(limit)
        if normalized_limit <= 0:
            return []
        scored: list[tuple[float, int, str, dict[str, Any]]] = []
        for segment in self._qa_segments_from_memory_handout(
            course_id=active_course_id,
            parse_run_id=active_parse_run_id,
            handout=handout,
        ):
            score = _qa_lexical_overlap_score(question, str(segment.get("textContent") or ""))
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    int(segment.get("orderNo") or 0),
                    str(segment.get("segmentKey") or ""),
                    segment,
                )
            )
        return [
            segment
            for _score, _order_no, _key, segment in sorted(
                scored,
                key=lambda item: (-item[0], item[1], item[2]),
            )[:normalized_limit]
        ]

    def search_vector_segments(
        self,
        scope: QaScope,
        embedding: Sequence[float],
        limit: int,
    ) -> list[VectorSearchHit]:
        return []

    def search_lexical_segments(
        self,
        scope: QaScope,
        query: str,
        limit: int,
    ) -> list[LexicalSearchHit]:
        active_course_id = _as_positive_int(scope.course_id)
        active_parse_run_id = _as_positive_int(scope.active_parse_run_id)
        normalized_limit = _normalized_search_limit(limit)
        if active_course_id is None or active_parse_run_id is None or normalized_limit <= 0:
            return []
        course = self.courses.get(active_course_id)
        handout = self.get_latest_handout(active_course_id)
        if course is None or handout is None or handout.get("sourceParseRunId") != active_parse_run_id:
            return []

        scored: list[tuple[float, int, LexicalSearchHit]] = []
        for segment in self._qa_segments_from_memory_handout(
            course_id=active_course_id,
            parse_run_id=active_parse_run_id,
            handout=handout,
        ):
            text = str(segment.get("textContent") or "")
            score = _qa_lexical_overlap_score(query, text)
            if score <= 0:
                continue
            segment_key = str(segment.get("segmentKey") or "").strip() or None
            scored.append(
                (
                    score,
                    int(segment.get("orderNo") or 0),
                    LexicalSearchHit(
                        identity_key=f"segment:{segment_key}",
                        score=score,
                        text=text,
                        segment_key=segment_key,
                        resource_id=_as_positive_int(segment.get("resourceId")),
                        owner_type="segment",
                        course_id=active_course_id,
                        parse_run_id=active_parse_run_id,
                        metadata_json={"segmentType": segment.get("segmentType")},
                        locator=_segment_locator_from_payload(segment),
                    ),
                )
            )
        return [
            _ranked_lexical_hit(hit, rank=index)
            for index, (_score, _order_no, hit) in enumerate(
                sorted(scored, key=lambda item: (-item[0], item[1], item[2].identity_key))[:normalized_limit],
                start=1,
            )
        ]

    def search_vector_handout_blocks(
        self,
        scope: QaScope,
        embedding: Sequence[float],
        limit: int,
    ) -> list[VectorSearchHit]:
        return []

    def search_lexical_handout_blocks(
        self,
        scope: QaScope,
        query: str,
        limit: int,
    ) -> list[LexicalSearchHit]:
        active_course_id = _as_positive_int(scope.course_id)
        active_parse_run_id = _as_positive_int(scope.active_parse_run_id)
        active_handout_version_id = _as_positive_int(scope.active_handout_version_id)
        normalized_limit = _normalized_search_limit(limit)
        if (
            active_course_id is None
            or active_parse_run_id is None
            or active_handout_version_id is None
            or normalized_limit <= 0
        ):
            return []
        handout = self.get_latest_handout(active_course_id)
        if (
            handout is None
            or handout.get("sourceParseRunId") != active_parse_run_id
            or handout.get("handoutVersionId") != active_handout_version_id
        ):
            return []

        scored: list[tuple[float, int, LexicalSearchHit]] = []
        for block in handout.get("blocks") or []:
            if block.get("status") != "ready" and block.get("generationStatus") != "ready":
                continue
            search_text = " ".join(
                item
                for item in (block.get("title"), block.get("summary"), block.get("contentMd"))
                if isinstance(item, str) and item
            )
            score = _qa_lexical_overlap_score(query, search_text)
            if score <= 0:
                continue
            block_id = block.get("blockId")
            scored.append(
                (
                    score,
                    int(block.get("sortNo") or 0),
                    LexicalSearchHit(
                        identity_key=f"handout:{block_id}",
                        score=score,
                        text=str(block.get("contentMd") or block.get("summary") or block.get("title") or ""),
                        owner_type="handout_block",
                        handout_block_id=block_id,
                        course_id=active_course_id,
                        parse_run_id=active_parse_run_id,
                        handout_version_id=active_handout_version_id,
                        metadata_json={"outlineKey": block.get("outlineKey"), "title": block.get("title")},
                    ),
                )
            )
        return [
            _ranked_lexical_hit(hit, rank=index)
            for index, (_score, _sort_no, hit) in enumerate(
                sorted(scored, key=lambda item: (-item[0], item[1], item[2].identity_key))[:normalized_limit],
                start=1,
            )
        ]

    def save_qa_exchange(
        self,
        context: dict[str, Any],
        question: str,
        response: dict[str, Any],
        refs: list[dict[str, Any]],
        candidate_count: int,
    ) -> dict[str, Any]:
        live_context = self.get_qa_context(int(context.get("courseId") or 0), int(context.get("handoutBlockId") or 0))
        if (
            live_context is None
            or live_context.get("activeParseRunId") != context.get("activeParseRunId")
            or live_context.get("activeHandoutVersionId") != context.get("activeHandoutVersionId")
        ):
            raise RuntimeError("Cannot save QA exchange for stale or invalid context.")

        session_id = self.next_id("qa_session")
        user_message_id = self.next_id("qa_message")
        assistant_message_id = self.next_id("qa_message")
        citations = [] if response.get("answerType") == "insufficient_evidence" else list(response.get("citations") or [])
        generation_metadata = response.get("generationMetadata")
        if not isinstance(generation_metadata, dict):
            generation_metadata = None
        payload = {
            "sessionId": session_id,
            "messageId": assistant_message_id,
            "answerMd": response["answerMd"],
            "answerType": response.get("answerType"),
            "citations": citations,
        }
        if generation_metadata:
            payload["generationMetadata"] = generation_metadata
        self.qa_sessions[session_id] = {
            "context": {
                "courseId": context.get("courseId"),
                "activeParseRunId": context.get("activeParseRunId"),
                "activeHandoutVersionId": context.get("activeHandoutVersionId"),
                "handoutBlockId": context.get("handoutBlockId"),
                "candidateCount": candidate_count,
                "generationMetadata": generation_metadata,
            },
            "messages": [
                {
                    "sessionId": session_id,
                    "messageId": user_message_id,
                    "role": "user",
                    "contentMd": question,
                    "answerMd": None,
                    "answerType": None,
                    "citations": [],
                },
                {"role": "assistant", **payload},
            ],
        }
        return payload

    def _qa_block_payload_from_memory(
        self,
        block: dict[str, Any],
        *,
        course_id: int,
        parse_run_id: int | None,
        handout_version_id: int,
    ) -> dict[str, Any]:
        return {
            "courseId": course_id,
            "parseRunId": parse_run_id,
            "handoutVersionId": handout_version_id,
            "handoutBlockId": block["blockId"],
            "outlineKey": block["outlineKey"],
            "sortNo": block.get("sortNo") or 0,
            "title": block["title"],
            "summary": block["summary"],
            "contentMd": block.get("contentMd") or block["summary"],
            "sourceSegmentKeys": list(block.get("sourceSegmentKeys") or []),
            "knowledgePoints": block.get("knowledgePoints") or [],
            "citations": block.get("citations") or [],
        }

    def _qa_course_scope_from_memory(
        self,
        *,
        course: dict[str, Any],
        course_id: int,
        current_block: dict[str, Any],
        adjacent_blocks: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        scoped_blocks = [
            self._qa_block_payload_from_memory(
                current_block,
                course_id=course_id,
                parse_run_id=course.get("activeParseRunId"),
                handout_version_id=int(course.get("activeHandoutVersionId") or 0),
            ),
            *adjacent_blocks,
        ]
        handout_titles = [_qa_scope_block_label(block) for block in scoped_blocks]
        return {
            "title": course.get("title"),
            "summary": course.get("summary"),
            "goalText": course.get("goalText"),
            "resourceTitles": [
                str(resource.get("originalName")).strip()
                for resource in self.resources.get(course_id, [])
                if str(resource.get("originalName") or "").strip()
            ],
            "handoutTitles": [item for item in handout_titles if item],
            "knowledgePointNames": _qa_scope_knowledge_point_names(scoped_blocks),
        }

    def _qa_segments_from_memory_handout(
        self,
        *,
        course_id: int,
        parse_run_id: int | None,
        handout: dict[str, Any],
    ) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        for block_index, block in enumerate(handout["blocks"], start=1):
            text_content = " ".join(
                item
                for item in [block.get("title"), block.get("summary"), block.get("contentMd")]
                if isinstance(item, str) and item
            )
            for citation_index, citation in enumerate(block.get("citations") or [], start=1):
                if not isinstance(citation, dict):
                    continue
                locator = {
                    key: citation[key]
                    for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec")
                    if citation.get(key) not in (None, "")
                }
                if not locator:
                    continue
                segment_key = str(citation.get("segmentKey") or f"memory-{block['blockId']}-{citation_index}")
                segments.append(
                    {
                        "courseId": course_id,
                        "parseRunId": parse_run_id,
                        "resourceId": citation["resourceId"],
                        "segmentId": None,
                        "segmentKey": segment_key,
                        "segmentType": self._memory_segment_type(locator),
                        "resourceType": self._memory_resource_type(locator),
                        "textContent": text_content or block["summary"],
                        "orderNo": block_index * 100 + citation_index,
                        **locator,
                    }
                )
            if block.get("citations"):
                continue
            source_resource = self._memory_source_resource(course_id, block)
            source_locator = {
                key: block[key]
                for key in ("startSec", "endSec")
                if block.get(key) not in (None, "")
            }
            if source_resource is None or set(source_locator) != {"startSec", "endSec"}:
                continue
            emitted_segment_keys: set[str] = set()
            for source_index, source_segment_key in enumerate(block.get("sourceSegmentKeys") or [], start=1):
                segment_key = str(source_segment_key or "").strip()
                if not segment_key or segment_key in emitted_segment_keys:
                    continue
                emitted_segment_keys.add(segment_key)
                segments.append(
                    {
                        "courseId": course_id,
                        "parseRunId": parse_run_id,
                        "resourceId": source_resource["resourceId"],
                        "segmentId": None,
                        "segmentKey": segment_key,
                        "segmentType": "video_caption",
                        "resourceType": source_resource.get("resourceType") or "mp4",
                        "textContent": text_content or block["summary"],
                        "orderNo": block_index * 100 + 50 + source_index,
                        **source_locator,
                    }
                )
        return segments

    def _memory_source_resource(self, course_id: int, block: Mapping[str, Any]) -> dict[str, Any] | None:
        resources = self.resources.get(course_id, [])
        if not resources or block.get("startSec") in (None, "") or block.get("endSec") in (None, ""):
            return None
        for resource in resources:
            if resource.get("resourceType") == "mp4":
                return resource
        return None

    def _memory_segment_type(self, locator: dict[str, Any]) -> str:
        if "startSec" in locator and "endSec" in locator:
            return "video_caption"
        if "pageNo" in locator:
            return "pdf_page_text"
        if "slideNo" in locator:
            return "ppt_slide_text"
        if "anchorKey" in locator:
            return "docx_block_text"
        return "text"

    def _memory_resource_type(self, locator: dict[str, Any]) -> str:
        if "startSec" in locator and "endSec" in locator:
            return "mp4"
        if "pageNo" in locator:
            return "pdf"
        if "slideNo" in locator:
            return "pptx"
        if "anchorKey" in locator:
            return "docx"
        return "document"

    def get_qa_session_messages(self, session_id: int) -> list[dict[str, Any]] | None:
        session = self.qa_sessions.get(session_id)
        if session is None:
            return None
        context = session.get("context") or {}
        live_context = self.get_qa_context(int(context.get("courseId") or 0), int(context.get("handoutBlockId") or 0))
        if (
            live_context is None
            or live_context.get("activeParseRunId") != context.get("activeParseRunId")
            or live_context.get("activeHandoutVersionId") != context.get("activeHandoutVersionId")
        ):
            return None
        return list(session.get("messages") or [])

    def create_quiz(
        self,
        course_id: int,
        *,
        question_count_level: str = "medium",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        quiz_id = self.next_id("quiz")
        task_id = self.next_id("task")
        quiz = {
            "quizId": quiz_id,
            "courseId": course_id,
            "status": "queued",
            "questionCount": 0,
            "questions": [],
        }
        self.quizzes[quiz_id] = quiz
        self.register_async_task(
            task_id=task_id,
            course_id=course_id,
            task_type="quiz_generate",
            status="queued",
            progress_pct=0,
            payload_json={
                "courseId": course_id,
                "quizId": quiz_id,
                "questionCountLevel": question_count_level,
            },
            target_type="quiz",
            target_id=quiz_id,
        )
        return quiz, {
            "taskId": task_id,
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "quiz", "id": quiz_id},
            "payload": {"questionCountLevel": question_count_level},
        }

    def get_quiz_submission_context(self, quiz_id: int) -> dict[str, Any] | None:
        quiz = self.quizzes.get(quiz_id)
        if quiz is None:
            return None
        return {
            "quizPayload": {
                "quizType": quiz.get("quizType", "chapter_review"),
                "questions": list(quiz.get("questions", [])),
            },
            "masteryRecords": [],
        }

    def save_quiz_attempt_result(
        self,
        quiz_id: int,
        *,
        quiz_attempt_result: dict[str, Any],
        mastery_updates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _ = mastery_updates
        attempt_id = self.next_id("attempt")
        review_run = self.create_review_run(self.quizzes[quiz_id]["courseId"])
        return {
            "attemptId": attempt_id,
            "score": int(quiz_attempt_result.get("score", 0)),
            "totalScore": int(quiz_attempt_result.get("totalScore", 0)),
            "accuracy": float(quiz_attempt_result.get("accuracy", 0.0)),
            "reviewTaskRunId": review_run["reviewTaskRunId"],
            "masteryDelta": list(quiz_attempt_result.get("masteryDelta", [])),
            "recommendedReviewAction": quiz_attempt_result.get("recommendedReviewAction"),
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
        task_id = self.next_id("task")
        return self.register_async_task(
            task_id=task_id,
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

    def register_async_task(
        self,
        *,
        task_id: int,
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
        task = {
            "taskId": task_id,
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
        self.async_tasks[task_id] = task
        return task

    def get_async_task(self, task_id: int) -> dict[str, Any] | None:
        return self.async_tasks.get(task_id)

    def list_async_tasks(
        self,
        *,
        course_id: int,
        parse_run_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            task
            for task in self.async_tasks.values()
            if task["courseId"] == course_id
            and (parse_run_id is None or task["parseRunId"] == parse_run_id)
        ]

    def update_async_task(self, task_id: int, **changes: Any) -> dict[str, Any] | None:
        task = self.async_tasks.get(task_id)
        if task is None:
            return None
        if changes.get("clear_error"):
            task["errorCode"] = None
            task["errorMessage"] = None
        if "status" in changes and changes["status"] is not None:
            task["status"] = changes["status"]
        if "progress_pct" in changes and changes["progress_pct"] is not None:
            task["progressPct"] = changes["progress_pct"]
        if "payload_json" in changes and changes["payload_json"] is not None:
            task["payloadJson"] = changes["payload_json"]
        if "error_code" in changes and changes["error_code"] is not None:
            task["errorCode"] = changes["error_code"]
        if "error_message" in changes and changes["error_message"] is not None:
            task["errorMessage"] = changes["error_message"]
        return task

    def list_review_tasks(self, course_id: int) -> list[dict[str, Any]]:
        if course_id not in self.review_tasks:
            self.create_review_run(course_id)
        return self.review_tasks.get(course_id, [])

    def get_review_run(self, review_run_id: int) -> dict[str, Any] | None:
        return self.review_runs.get(review_run_id)

    def list_daily_recommended_knowledge_points(self, *, limit: int = 3) -> list[dict[str, Any]]:
        recent_courses = self.list_recent_courses()
        target_course_id = recent_courses[0]["courseId"] if recent_courses else None
        recommendations = [
            {
                "knowledgePoint": "极限定义",
                "reason": "高频考点，且最近一次学习停留在该模块。",
                "targetCourseId": target_course_id,
            },
            {
                "knowledgePoint": "导数几何意义",
                "reason": "讲义块完成后适合立即回看并练习。",
                "targetCourseId": target_course_id,
            },
        ]
        return recommendations[:limit]

    def get_learning_stats(self) -> dict[str, Any]:
        completed_tasks = sum(
            1
            for tasks in self.review_tasks.values()
            for task in tasks
            if task.get("status") == "completed"
        )
        return {
            "streakDays": 3 if self.progress else 0,
            "completedCourses": len(self.courses),
            "reviewTasksCompleted": completed_tasks,
            "totalLearningMinutes": 95 if self.courses else 0,
        }

    def update_progress(self, course_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.progress.get(course_id, {"courseId": course_id})
        current.update(payload)
        current["lastActivityAt"] = utcnow()
        self.progress[course_id] = current
        return current

    def get_progress(self, course_id: int) -> dict[str, Any]:
        return self.progress.get(course_id, {"courseId": course_id, "lastActivityAt": utcnow()})


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalized_search_limit(limit: int) -> int:
    if isinstance(limit, bool):
        return 0
    try:
        return max(0, min(int(limit), 50))
    except (TypeError, ValueError):
        return 0


def _qa_lexical_overlap_score(query: str, text: str) -> float:
    query_tokens = _qa_search_tokens(query)
    if not query_tokens:
        return 0.0
    text_tokens = _qa_search_tokens(text)
    compact_text = clean_text(text).lower()
    if not text_tokens and not compact_text:
        return 0.0
    overlap = (query_tokens & text_tokens) | {token for token in query_tokens if token in compact_text}
    if not overlap:
        return 0.0
    return float(len(overlap)) + (len(overlap) / len(query_tokens))


def _qa_search_tokens(value: str) -> set[str]:
    normalized = clean_text(value).lower()
    tokens = {token for token in re.findall(r"[a-z0-9_]{2,}", normalized) if token.strip()}
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def _segment_locator_from_payload(segment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: segment[key]
        for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec")
        if segment.get(key) not in (None, "")
    }


def _ranked_lexical_hit(hit: LexicalSearchHit, *, rank: int) -> LexicalSearchHit:
    return LexicalSearchHit(
        identity_key=hit.identity_key,
        score=hit.score,
        text=hit.text,
        segment_key=hit.segment_key,
        resource_id=hit.resource_id,
        owner_type=hit.owner_type,
        handout_block_id=hit.handout_block_id,
        segment_id=hit.segment_id,
        course_id=hit.course_id,
        parse_run_id=hit.parse_run_id,
        handout_version_id=hit.handout_version_id,
        metadata_json=hit.metadata_json,
        locator=hit.locator,
        distance=hit.distance,
        rank=rank,
    )


runtime_store = RuntimeStore()
