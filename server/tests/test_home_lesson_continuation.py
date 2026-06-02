from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any
from urllib.parse import urlsplit

import pytest

from server.app import app
from server.infra.repositories.memory_runtime import RuntimeStore, runtime_store
from server.tests.test_api import AUTH_HEADERS


_STORE_FIELDS = (
    "counters",
    "idempotency",
    "idempotency_records",
    "courses",
    "lessons",
    "resources",
    "parse_runs",
    "inquiry_answers",
    "handouts",
    "handout_by_course",
    "quizzes",
    "qa_sessions",
    "review_runs",
    "review_tasks",
    "async_tasks",
    "progress",
    "user_lesson_progress",
    "scoped_artifacts",
    "bilibili_qr_sessions",
    "bilibili_auth_session",
    "bilibili_preview_snapshots",
    "bilibili_import_runs",
    "current_course_id",
)


@pytest.fixture(autouse=True)
def isolated_runtime_store():
    snapshot = {field: deepcopy(getattr(runtime_store, field)) for field in _STORE_FIELDS}
    fresh = RuntimeStore()
    for field in _STORE_FIELDS:
        setattr(runtime_store, field, deepcopy(getattr(fresh, field)))
    yield
    for field, value in snapshot.items():
        setattr(runtime_store, field, value)


async def _request(method: str, target: str, *, json_body: dict[str, Any] | None = None):
    parsed = urlsplit(target)
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in AUTH_HEADERS.items()]
    body = b""
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        raw_headers.append((b"content-type", b"application/json"))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode(),
        "query_string": parsed.query.encode(),
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    incoming = [{"type": "http.request", "body": body, "more_body": False}]
    outgoing = []
    response_complete = asyncio.Event()

    async def receive():
        if incoming:
            return incoming.pop(0)
        await response_complete.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        outgoing.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            response_complete.set()

    await app(scope, receive, send)
    status = next(message["status"] for message in outgoing if message["type"] == "http.response.start")
    payload = b"".join(
        message.get("body", b"")
        for message in outgoing
        if message["type"] == "http.response.body"
    )
    return status, json.loads(payload.decode())


def _api(method: str, target: str, *, json_body: dict[str, Any] | None = None):
    return asyncio.run(_request(method, target, json_body=json_body))


def _create_course(title: str, *, exam_at: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "entryType": "manual_import",
        "goalText": "数据库系统期末复习",
        "preferredStyle": "exam",
    }
    if exam_at is not None:
        payload["examAt"] = exam_at
    status, body = _api("POST", "/api/v1/courses", json_body=payload)
    assert status == 201
    return body["data"]["course"]


def _resource_payload(
    *,
    name: str,
    resource_type: str = "pdf",
    scope_type: str = "course",
    lesson_id: int | None = None,
    usage_role: str = "course_material",
) -> dict[str, Any]:
    suffix = "mp4" if resource_type == "mp4" else "pdf"
    mime_type = "video/mp4" if resource_type == "mp4" else "application/pdf"
    payload: dict[str, Any] = {
        "resourceType": resource_type,
        "sourceType": "upload",
        "objectKey": f"raw/{name}.{suffix}",
        "originalName": f"{name}.{suffix}",
        "mimeType": mime_type,
        "sizeBytes": 1024,
        "checksum": f"sha256:{name}",
        "scopeType": scope_type,
        "usageRole": usage_role,
    }
    if resource_type == "mp4":
        payload["durationSec"] = 1800
    if lesson_id is not None:
        payload["lessonId"] = lesson_id
    return payload


def _bind_primary_video(course_id: int, lesson: dict[str, Any], *, name: str) -> dict[str, Any]:
    resource = runtime_store.create_resource(
        course_id,
        _resource_payload(
            name=name,
            resource_type="mp4",
            scope_type="lesson",
            lesson_id=lesson["lessonId"],
            usage_role="primary_video",
        ),
    )
    runtime_store.update_lesson(
        course_id=course_id,
        lesson_id=lesson["lessonId"],
        changes={"primaryVideoResourceId": resource["resourceId"], "lessonStatus": "learning_ready"},
    )
    return resource


def test_home_dashboard_continues_current_lesson_and_returns_course_next_actions() -> None:
    course = _create_course("数据库系统", exam_at="2026-06-20T09:00:00+08:00")
    first = runtime_store.create_lesson(course_id=course["courseId"], title="关系模型")
    second = runtime_store.create_lesson(course_id=course["courseId"], title="SQL 查询")
    third = runtime_store.create_lesson(course_id=course["courseId"], title="索引优化")
    _bind_primary_video(course["courseId"], first, name="lesson-1")
    _bind_primary_video(course["courseId"], second, name="lesson-2")
    runtime_store.create_resource(
        course["courseId"],
        _resource_payload(
            name="sql-handout",
            scope_type="lesson",
            lesson_id=second["lessonId"],
            usage_role="lesson_material",
        ),
    )
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=first["lessonId"],
        changes={"lessonStatus": "completed", "masteryScore": 0.82},
    )
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=second["lessonId"],
        changes={"masteryScore": 0.42},
    )
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=third["lessonId"],
        changes={"masteryScore": 0.9},
    )
    runtime_store.create_handout(course["courseId"])
    handout_id = runtime_store.handout_by_course[course["courseId"]]
    block_id = runtime_store.handouts[handout_id]["blocks"][0]["blockId"]
    runtime_store.upsert_user_lesson_progress(
        course_id=course["courseId"],
        lesson_id=second["lessonId"],
        payload={
            "lastPositionSec": 420,
            "lastHandoutBlockId": block_id,
            "handoutReadPercent": 35,
            "reviewStatus": "due",
        },
    )
    runtime_store.set_current_course(course["courseId"])

    status, body = _api("GET", "/api/v1/home/dashboard")

    assert status == 200
    data = body["data"]
    assert data["currentCourse"]["courseId"] == course["courseId"]
    assert data["currentLesson"]["lessonId"] == second["lessonId"]
    assert data["continueLearning"] == {
        "courseId": course["courseId"],
        "lessonId": second["lessonId"],
        "lastPositionSec": 420,
        "lastHandoutBlockId": block_id,
        "nextRoute": f"/courses/{course['courseId']}/lessons/{second['lessonId']}",
        "nextAction": {
            "type": "continue_video",
            "label": "继续学习 SQL 查询",
            "positionSec": 420,
        },
    }
    assert data["nextStep"]["type"] == "continue_lesson"
    assert data["nextStep"]["lessonId"] == second["lessonId"]
    assert data["todayReviewTasks"][0]["lessonId"] == second["lessonId"]
    assert data["recommendedNextLesson"]["lessonId"] == second["lessonId"]
    assert data["recommendedStageQuiz"]["type"] == "stage_quiz"
    assert data["recommendedStageQuiz"]["completedLessonCount"] == 1
    assert {entry["key"] for entry in data["courseQuickEntries"]} == {
        "course_qa",
        "course_graph",
        "comprehensive_quiz",
        "course_review",
        "report",
        "export",
        "settings",
    }


def test_in_course_recommendations_use_deterministic_lesson_rules() -> None:
    course = _create_course("算法设计", exam_at="2026-06-18T09:00:00+08:00")
    completed = runtime_store.create_lesson(course_id=course["courseId"], title="分治法")
    weak = runtime_store.create_lesson(course_id=course["courseId"], title="动态规划")
    missing_video = runtime_store.create_lesson(course_id=course["courseId"], title="贪心算法")
    missing_material = runtime_store.create_lesson(course_id=course["courseId"], title="图算法")
    _bind_primary_video(course["courseId"], completed, name="divide")
    _bind_primary_video(course["courseId"], weak, name="dp")
    _bind_primary_video(course["courseId"], missing_material, name="graph")
    runtime_store.create_resource(
        course["courseId"],
        _resource_payload(
            name="divide-notes",
            scope_type="lesson",
            lesson_id=completed["lessonId"],
            usage_role="lesson_material",
        ),
    )
    runtime_store.create_resource(
        course["courseId"],
        _resource_payload(
            name="dp-notes",
            scope_type="lesson",
            lesson_id=weak["lessonId"],
            usage_role="lesson_material",
        ),
    )
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=completed["lessonId"],
        changes={"lessonStatus": "completed", "masteryScore": 0.86},
    )
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=weak["lessonId"],
        changes={"masteryScore": 0.38},
    )

    course_status, course_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/recommendations/next-actions",
    )
    lesson_status, lesson_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{weak['lessonId']}/recommendations/next-actions",
    )

    assert course_status == 200
    actions = course_body["data"]["items"]
    by_type = {action["type"]: action for action in actions}
    assert by_type["next_lesson"]["lessonId"] == weak["lessonId"]
    assert by_type["lesson_review"]["lessonId"] == weak["lessonId"]
    assert by_type["stage_quiz"]["completedLessonCount"] == 1
    material_actions = [action for action in actions if action["type"] == "add_lesson_material"]
    assert {action["lessonId"] for action in material_actions} == {
        missing_video["lessonId"],
        missing_material["lessonId"],
    }
    assert any(action["missing"] == ["primary_video"] for action in material_actions)
    assert any(action["missing"] == ["supporting_material"] for action in material_actions)
    for action in actions:
        reason = action["reason"]
        assert "当前进度" in reason
        assert "薄弱点占位" in reason
        assert "考试紧迫度占位" in reason
        assert action["reasonPlaceholders"]["graphDriven"] == "placeholder"

    assert lesson_status == 200
    lesson_actions = lesson_body["data"]["items"]
    assert [action["lessonId"] for action in lesson_actions] == [weak["lessonId"]]
    assert lesson_actions[0]["type"] == "lesson_review"


def test_report_and_export_placeholders_keep_scope_fields() -> None:
    course = _create_course("操作系统")
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="进程调度")

    course_report_status, course_report_body = _api("GET", f"/api/v1/courses/{course['courseId']}/reports/summary")
    lesson_report_status, lesson_report_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/reports/summary",
    )
    export_list_status, export_list_body = _api("GET", f"/api/v1/courses/{course['courseId']}/exports")
    export_create_status, export_create_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/exports",
        json_body={"exportType": "lesson_summary", "scopeType": "lesson", "lessonId": lesson["lessonId"]},
    )

    assert course_report_status == 200
    assert course_report_body["data"] == {
        "summaryStatus": "placeholder",
        "scopeType": "course",
        "courseId": course["courseId"],
        "lessonId": None,
        "metrics": [],
        "message": "学习报告本轮仅提供占位摘要。",
    }
    assert lesson_report_status == 200
    assert lesson_report_body["data"]["scopeType"] == "lesson"
    assert lesson_report_body["data"]["courseId"] == course["courseId"]
    assert lesson_report_body["data"]["lessonId"] == lesson["lessonId"]
    assert lesson_report_body["data"]["metrics"] == []
    assert export_list_status == 200
    assert export_list_body["data"]["availableExportTypes"] == [
        "course_summary",
        "lesson_summary",
        "qa_transcript",
        "quiz_report",
        "review_plan",
    ]
    assert export_list_body["data"]["status"] == "placeholder"
    assert export_list_body["data"]["courseId"] == course["courseId"]
    assert export_list_body["data"]["downloadUrl"] is None
    assert export_create_status == 200
    assert export_create_body["data"]["scopeType"] == "lesson"
    assert export_create_body["data"]["courseId"] == course["courseId"]
    assert export_create_body["data"]["lessonId"] == lesson["lessonId"]
    assert export_create_body["data"]["downloadUrl"] is None
