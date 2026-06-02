from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any
from urllib.parse import urlsplit

import pytest

from server.app import app
from server.infra.repositories.memory_runtime import RuntimeStore, runtime_store, utcnow
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


def _create_course(
    title: str,
    *,
    entry_type: str = "manual_import",
    goal_text: str = "期末复习",
    preferred_style: str = "balanced",
    exam_at: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "entryType": entry_type,
        "goalText": goal_text,
        "preferredStyle": preferred_style,
    }
    if exam_at is not None:
        payload["examAt"] = exam_at
    status, body = _api(
        "POST",
        "/api/v1/courses",
        json_body=payload,
    )
    assert status == 201
    return body["data"]["course"]


def _resource_payload(
    *,
    name: str,
    scope_type: str = "course",
    lesson_id: int | None = None,
    usage_role: str = "course_material",
) -> dict[str, Any]:
    payload = {
        "resourceType": "pdf",
        "sourceType": "upload",
        "objectKey": f"raw/{name}.pdf",
        "originalName": f"{name}.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 1024,
        "checksum": f"sha256:{name}",
        "scopeType": scope_type,
        "usageRole": usage_role,
    }
    if lesson_id is not None:
        payload["lessonId"] = lesson_id
    return payload


def _items(body: dict[str, Any]) -> list[dict[str, Any]]:
    return body["data"]["items"]


def test_course_library_returns_active_courses_with_counts() -> None:
    active = _create_course("Task3 活跃课程")
    deleted = _create_course("Task3 已删除课程")
    runtime_store.courses[deleted["courseId"]]["deletedAt"] = utcnow()

    lesson = runtime_store.create_lesson(course_id=active["courseId"], title="第 1 节")
    runtime_store.create_resource(active["courseId"], _resource_payload(name="course-material"))
    runtime_store.upsert_user_lesson_progress(
        course_id=active["courseId"],
        lesson_id=lesson["lessonId"],
        payload={"handoutReadPercent": 80, "reviewStatus": "due"},
    )

    status, body = _api("GET", "/api/v1/courses")

    assert status == 200
    items = _items(body)
    assert [item["courseId"] for item in items] == [active["courseId"]]
    item = items[0]
    assert item["lessonCount"] == 1
    assert item["courseResourceCount"] == 1
    assert item["pendingReviewCount"] == 1
    assert item["lifecycleStatus"] == "draft"
    assert item["archivedAt"] is None


def test_course_library_filters_archived_source_status_query_and_sort() -> None:
    algebra = _create_course(
        "线代强化",
        entry_type="manual_import",
        exam_at="2026-06-20T09:00:00+08:00",
    )
    ai = _create_course(
        "AI 导论",
        entry_type="recommendation",
        exam_at="2026-06-10T09:00:00+08:00",
    )
    archived = _create_course("归档线代旧课", entry_type="manual_import")
    runtime_store.courses[algebra["courseId"]]["lifecycleStatus"] = "learning_ready"
    runtime_store.courses[ai["courseId"]]["lifecycleStatus"] = "completed"
    runtime_store.courses[archived["courseId"]]["archivedAt"] = utcnow()

    status, q_body = _api("GET", "/api/v1/courses?q=%E7%BA%BF%E4%BB%A3&archived=include")
    status_source, source_body = _api("GET", "/api/v1/courses?source=recommendation")
    status_status, status_body = _api("GET", "/api/v1/courses?learningStatus=learning_ready")
    status_archived, archived_body = _api("GET", "/api/v1/courses?archived=only")
    status_sort, sort_body = _api("GET", "/api/v1/courses?archived=include&sort=title_asc")

    assert status == 200
    assert {item["title"] for item in _items(q_body)} == {"线代强化", "归档线代旧课"}
    assert status_source == 200
    assert [item["courseId"] for item in _items(source_body)] == [ai["courseId"]]
    assert status_status == 200
    assert [item["courseId"] for item in _items(status_body)] == [algebra["courseId"]]
    assert status_archived == 200
    assert [item["courseId"] for item in _items(archived_body)] == [archived["courseId"]]
    assert status_sort == 200
    assert [item["title"] for item in _items(sort_body)] == ["AI 导论", "归档线代旧课", "线代强化"]


def test_update_course_patch_updates_editable_fields() -> None:
    course = _create_course("旧标题")

    status, body = _api(
        "PATCH",
        f"/api/v1/courses/{course['courseId']}",
        json_body={
            "title": "新标题",
            "goalText": "完成数据库期末冲刺",
            "examAt": "2026-06-30T14:30:00+08:00",
            "preferredStyle": "exam",
        },
    )

    assert status == 200
    updated = body["data"]["course"]
    assert updated["title"] == "新标题"
    assert updated["goalText"] == "完成数据库期末冲刺"
    assert updated["preferredStyle"] == "exam"
    assert updated["examAt"] == "2026-06-30T14:30:00+08:00"


def test_switch_current_course_updates_recent_activity_order() -> None:
    older = _create_course("较早课程")
    newer = _create_course("较新课程")

    initial_status, initial_body = _api("GET", "/api/v1/courses")
    switch_status, switched = _api("POST", f"/api/v1/courses/{older['courseId']}/switch-current")
    after_status, after_body = _api("GET", "/api/v1/courses")

    assert initial_status == 200
    assert _items(initial_body)[0]["courseId"] == newer["courseId"]
    assert switch_status == 200
    assert switched["data"]["currentCourseId"] == older["courseId"]
    assert after_status == 200
    assert _items(after_body)[0]["courseId"] == older["courseId"]


def test_archive_and_restore_change_library_visibility_without_dropping_data() -> None:
    course = _create_course("可归档课程")
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="保留节课")
    runtime_store.create_resource(course["courseId"], _resource_payload(name="kept-material"))

    archive_status, archive_body = _api("POST", f"/api/v1/courses/{course['courseId']}/archive")
    default_status, default_body = _api("GET", "/api/v1/courses")
    only_status, only_body = _api("GET", "/api/v1/courses?archived=only")
    restore_status, restore_body = _api("POST", f"/api/v1/courses/{course['courseId']}/restore")
    workbench_status, workbench = _api("GET", f"/api/v1/courses/{course['courseId']}/workbench")

    assert archive_status == 200
    assert archive_body["data"]["course"]["archivedAt"] is not None
    assert default_status == 200
    assert _items(default_body) == []
    assert only_status == 200
    assert [item["courseId"] for item in _items(only_body)] == [course["courseId"]]
    assert restore_status == 200
    assert restore_body["data"]["course"]["archivedAt"] is None
    assert workbench_status == 200
    assert [item["lessonId"] for item in workbench["data"]["lessons"]] == [lesson["lessonId"]]
    assert workbench["data"]["progress"]["courseResourceCount"] == 1


def test_delete_impact_and_delete_blockers_then_soft_delete_safe_course() -> None:
    blocked = _create_course("有依赖课程")
    runtime_store.create_lesson(course_id=blocked["courseId"], title="阻塞节课")
    runtime_store.create_resource(blocked["courseId"], _resource_payload(name="blocking-resource"))

    impact_status, impact = _api("GET", f"/api/v1/courses/{blocked['courseId']}/delete-impact")
    delete_blocked_status, delete_blocked = _api("DELETE", f"/api/v1/courses/{blocked['courseId']}")

    assert impact_status == 200
    assert impact["data"]["canDelete"] is False
    assert impact["data"]["blockers"]["lessons"] == 1
    assert impact["data"]["blockers"]["resources"] == 1
    assert delete_blocked_status == 409
    assert delete_blocked["errorCode"] == "course.delete_blocked"
    assert delete_blocked["data"] is None

    safe = _create_course("可删除空课程")
    delete_safe_status, delete_safe = _api("DELETE", f"/api/v1/courses/{safe['courseId']}")
    list_status, list_body = _api("GET", "/api/v1/courses?archived=include")
    get_deleted_status, get_deleted = _api("GET", f"/api/v1/courses/{safe['courseId']}")

    assert delete_safe_status == 200
    assert delete_safe["data"]["deleted"] is True
    assert delete_safe["data"]["deletedAt"] is not None
    assert list_status == 200
    assert safe["courseId"] not in {item["courseId"] for item in _items(list_body)}
    assert get_deleted_status == 404
    assert get_deleted["errorCode"] == "course.not_found"


def test_course_workbench_aggregates_course_lessons_resources_and_quick_entries() -> None:
    course = _create_course("工作台课程")
    first = runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")
    second = runtime_store.create_lesson(course_id=course["courseId"], title="第 2 节")
    runtime_store.create_resource(course["courseId"], _resource_payload(name="course-level"))
    runtime_store.create_resource(
        course["courseId"],
        _resource_payload(
            name="lesson-level",
            scope_type="lesson",
            lesson_id=first["lessonId"],
            usage_role="lesson_material",
        ),
    )
    runtime_store.upsert_user_lesson_progress(
        course_id=course["courseId"],
        lesson_id=first["lessonId"],
        payload={"lastPositionSec": 120, "handoutReadPercent": 100, "quizStatus": "completed"},
    )
    runtime_store.set_current_course(course["courseId"])

    status, body = _api("GET", f"/api/v1/courses/{course['courseId']}/workbench")

    assert status == 200
    data = body["data"]
    assert data["course"]["courseId"] == course["courseId"]
    assert data["progress"]["lessonCount"] == 2
    assert data["progress"]["completedLessonCount"] == 1
    assert data["progress"]["courseResourceCount"] == 1
    assert data["progress"]["lessonResourceCount"] == 1
    assert data["currentLesson"]["lessonId"] == first["lessonId"]
    assert [lesson["lessonId"] for lesson in data["lessons"]] == [first["lessonId"], second["lessonId"]]
    assert [resource["scopeType"] for resource in data["courseResources"]] == ["course"]
    assert {entry["key"] for entry in data["quickEntries"]} == {
        "course_qa",
        "course_graph",
        "comprehensive_quiz",
        "course_review",
        "report",
        "export",
        "settings",
    }
    assert data["placeholderStates"]["graph"]["status"] == "placeholder"
