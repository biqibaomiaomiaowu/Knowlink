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


def _create_course(title: str = "数据库系统") -> dict[str, Any]:
    course = runtime_store.create_course(
        title=title,
        entry_type="manual_import",
        goal_text="期末复习",
        preferred_style="balanced",
    )
    return course


def _mp4_resource(course_id: int, *, name: str, lesson_id: int | None = None) -> dict[str, Any]:
    return runtime_store.create_resource(
        course_id,
        {
            "resourceType": "mp4",
            "sourceType": "upload",
            "objectKey": f"raw/{name}.mp4",
            "originalName": f"{name}.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": 1024,
            "checksum": f"sha256:{name}",
            "scopeType": "lesson" if lesson_id is not None else "course",
            "lessonId": lesson_id,
            "usageRole": "primary_video" if lesson_id is not None else "course_material",
            "durationSec": 600,
        },
    )


def _pdf_resource(course_id: int, *, name: str, lesson_id: int | None = None) -> dict[str, Any]:
    return runtime_store.create_resource(
        course_id,
        {
            "resourceType": "pdf",
            "sourceType": "upload",
            "objectKey": f"raw/{name}.pdf",
            "originalName": f"{name}.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 1024,
            "checksum": f"sha256:{name}",
            "scopeType": "lesson" if lesson_id is not None else "course",
            "lessonId": lesson_id,
            "usageRole": "lesson_material" if lesson_id is not None else "course_material",
        },
    )


def _lesson_items(course_id: int) -> list[dict[str, Any]]:
    status, body = _api("GET", f"/api/v1/courses/{course_id}/lessons")
    assert status == 200
    return body["data"]["items"]


def test_create_lesson_appends_to_end() -> None:
    course = _create_course()
    runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons",
        json_body={"title": "第 2 节", "sourceType": "manual"},
    )

    assert status == 201
    created = body["data"]["lesson"]
    assert created["title"] == "第 2 节"
    assert created["orderIndex"] == 2
    assert [item["title"] for item in _lesson_items(course["courseId"])] == ["第 1 节", "第 2 节"]


def test_create_lesson_rejects_foreign_lesson_scoped_primary_video() -> None:
    course = _create_course()
    existing = runtime_store.create_lesson(course_id=course["courseId"], title="已有节课")
    video = _mp4_resource(course["courseId"], name="existing-video", lesson_id=existing["lessonId"])

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons",
        json_body={"title": "新节课", "primaryVideoResourceId": video["resourceId"]},
    )

    assert status == 400
    assert body["errorCode"] == "resource.lesson_mismatch"


def test_create_lesson_rejects_video_range_without_video() -> None:
    course = _create_course()

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons",
        json_body={"title": "新节课", "primaryVideoStartSec": 10},
    )

    assert status == 400
    assert body["errorCode"] == "common.validation_error"


def test_create_lesson_rejects_primary_video_without_full_range() -> None:
    course = _create_course()
    video = _mp4_resource(course["courseId"], name="course-video")

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons",
        json_body={"title": "新节课", "primaryVideoResourceId": video["resourceId"]},
    )

    assert status == 400
    assert body["errorCode"] == "common.validation_error"


def test_rename_lesson_updates_summary() -> None:
    course = _create_course()
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="旧标题")

    status, body = _api(
        "PATCH",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}",
        json_body={"title": "新标题"},
    )

    assert status == 200
    assert body["data"]["lesson"]["title"] == "新标题"
    assert _lesson_items(course["courseId"])[0]["title"] == "新标题"


def test_patch_lesson_cannot_delete_without_delete_endpoint() -> None:
    course = _create_course()
    first = runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")
    second = runtime_store.create_lesson(course_id=course["courseId"], title="第 2 节")

    status, _body = _api(
        "PATCH",
        f"/api/v1/courses/{course['courseId']}/lessons/{second['lessonId']}",
        json_body={"lessonStatus": "deleted"},
    )

    assert status == 422
    assert runtime_store.get_lesson(
        course_id=course["courseId"],
        lesson_id=second["lessonId"],
        include_deleted=True,
    )["deletedAt"] is None
    assert [(item["lessonId"], item["orderIndex"]) for item in _lesson_items(course["courseId"])] == [
        (first["lessonId"], 1),
        (second["lessonId"], 2),
    ]


def test_delete_lesson_marks_deleted_and_compresses_ordering() -> None:
    course = _create_course()
    first = runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")
    second = runtime_store.create_lesson(course_id=course["courseId"], title="第 2 节")
    third = runtime_store.create_lesson(course_id=course["courseId"], title="第 3 节")

    status, body = _api("DELETE", f"/api/v1/courses/{course['courseId']}/lessons/{second['lessonId']}")

    assert status == 200
    assert body["data"]["lesson"]["lessonStatus"] == "deleted"
    assert runtime_store.get_lesson(
        course_id=course["courseId"],
        lesson_id=second["lessonId"],
        include_deleted=True,
    )["lessonStatus"] == "deleted"
    items = _lesson_items(course["courseId"])
    assert [(item["lessonId"], item["orderIndex"]) for item in items] == [
        (first["lessonId"], 1),
        (third["lessonId"], 2),
    ]


def test_reorder_requires_all_non_deleted_lessons_in_same_course() -> None:
    course = _create_course("主课程")
    other = _create_course("外部课程")
    first = runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")
    second = runtime_store.create_lesson(course_id=course["courseId"], title="第 2 节")
    third = runtime_store.create_lesson(course_id=course["courseId"], title="第 3 节")
    foreign = runtime_store.create_lesson(course_id=other["courseId"], title="外部节课")

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/reorder",
        json_body={"lessonIds": [third["lessonId"], first["lessonId"], second["lessonId"]]},
    )
    missing_status, missing_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/reorder",
        json_body={"lessonIds": [first["lessonId"], second["lessonId"]]},
    )
    foreign_status, foreign_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/reorder",
        json_body={"lessonIds": [third["lessonId"], first["lessonId"], foreign["lessonId"]]},
    )

    assert status == 200
    assert [item["lessonId"] for item in body["data"]["items"]] == [
        third["lessonId"],
        first["lessonId"],
        second["lessonId"],
    ]
    assert missing_status == 409
    assert missing_body["errorCode"] == "lesson.order_conflict"
    assert foreign_status == 409
    assert foreign_body["errorCode"] == "lesson.order_conflict"


def test_set_primary_video_accepts_only_mp4_resource_in_same_course() -> None:
    course = _create_course("主课程")
    other = _create_course("外部课程")
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="主节课")
    mp4 = _mp4_resource(course["courseId"], name="main", lesson_id=lesson["lessonId"])
    range_optional_mp4 = _mp4_resource(course["courseId"], name="range-optional", lesson_id=lesson["lessonId"])
    pdf = _pdf_resource(course["courseId"], name="notes", lesson_id=lesson["lessonId"])
    foreign = _mp4_resource(other["courseId"], name="foreign")

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/primary-video",
        json_body={"resourceId": mp4["resourceId"], "startSec": 10, "endSec": 120},
    )
    range_optional_status, range_optional_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/primary-video",
        json_body={"resourceId": range_optional_mp4["resourceId"]},
    )
    pdf_status, pdf_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/primary-video",
        json_body={"resourceId": pdf["resourceId"]},
    )
    foreign_status, foreign_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/primary-video",
        json_body={"resourceId": foreign["resourceId"]},
    )

    assert status == 200
    updated = body["data"]["lesson"]
    assert updated["primaryVideoResourceId"] == mp4["resourceId"]
    assert updated["primaryVideoStartSec"] == 10
    assert updated["primaryVideoEndSec"] == 120
    assert range_optional_status == 200
    range_optional_lesson = range_optional_body["data"]["lesson"]
    assert range_optional_lesson["primaryVideoResourceId"] == range_optional_mp4["resourceId"]
    assert range_optional_lesson.get("primaryVideoStartSec") is None
    assert range_optional_lesson.get("primaryVideoEndSec") is None
    assert pdf_status == 409
    assert pdf_body["errorCode"] == "resource.not_video"
    assert foreign_status == 404
    assert foreign_body["errorCode"] == "resource.not_found"


def test_set_primary_video_rejects_invalid_ranges() -> None:
    course = _create_course()
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="主节课")
    mp4 = _mp4_resource(course["courseId"], name="range-video", lesson_id=lesson["lessonId"])

    inverted_status, inverted_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/primary-video",
        json_body={"resourceId": mp4["resourceId"], "startSec": 120, "endSec": 10},
    )
    too_long_status, too_long_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/primary-video",
        json_body={"resourceId": mp4["resourceId"], "startSec": 10, "endSec": 999},
    )

    assert inverted_status == 400
    assert inverted_body["errorCode"] == "common.validation_error"
    assert too_long_status == 400
    assert too_long_body["errorCode"] == "common.validation_error"


def test_lesson_detail_returns_read_model_placeholders_and_progress() -> None:
    course = _create_course()
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="细节节课")
    video = _mp4_resource(course["courseId"], name="detail-video", lesson_id=lesson["lessonId"])
    note = _pdf_resource(course["courseId"], name="detail-note", lesson_id=lesson["lessonId"])
    runtime_store.upsert_user_lesson_progress(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        payload={"lastPositionSec": 88, "handoutReadPercent": 42, "reviewStatus": "due"},
    )
    runtime_store.create_scoped_artifact(
        artifact_type="handout_version",
        course_id=course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="ready",
    )
    runtime_store.create_scoped_artifact(
        artifact_type="quiz",
        course_id=course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="ready",
    )
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        changes={"primaryVideoResourceId": video["resourceId"], "primaryVideoStartSec": 5, "primaryVideoEndSec": 300},
    )

    status, body = _api("GET", f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}")

    assert status == 200
    data = body["data"]
    assert data["lesson"]["lessonId"] == lesson["lessonId"]
    assert data["primaryVideo"]["resourceId"] == video["resourceId"]
    assert {item["resourceId"] for item in data["lessonResources"]} == {video["resourceId"], note["resourceId"]}
    assert {item["artifactType"]: item["status"] for item in data["artifactSummaries"]} == {
        "handout_version": "ready",
        "quiz": "ready",
    }
    assert data["progress"]["lastPositionSec"] == 88
    assert data["progress"]["handoutReadPercent"] == 42
    assert data["citations"] == []
    assert data["sourceOverview"]["resourceCount"] == 2
    assert data["sourceOverview"]["primaryVideoResourceId"] == video["resourceId"]
    assert data["knowledgePointPlaceholders"][0]["status"] == "placeholder"
    assert data["weaknessPlaceholders"][0]["status"] == "placeholder"
    assert data["nextAction"]["type"] == "continue_video"


def test_merge_adjacent_lessons_keeps_target_and_marks_artifacts_stale() -> None:
    course = _create_course()
    first = runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")
    second = runtime_store.create_lesson(course_id=course["courseId"], title="第 2 节")
    third = runtime_store.create_lesson(course_id=course["courseId"], title="第 3 节")
    second_note = _pdf_resource(course["courseId"], name="second-note", lesson_id=second["lessonId"])
    first_artifact = runtime_store.create_scoped_artifact(
        artifact_type="handout_version",
        course_id=course["courseId"],
        scope_type="lesson",
        lesson_id=first["lessonId"],
        status="ready",
    )
    second_artifact = runtime_store.create_scoped_artifact(
        artifact_type="quiz",
        course_id=course["courseId"],
        scope_type="lesson",
        lesson_id=second["lessonId"],
        status="ready",
    )

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/merge",
        json_body={"lessonIds": [first["lessonId"], second["lessonId"]], "targetTitle": "合并节课"},
    )

    assert status == 200
    lesson = body["data"]["lesson"]
    assert lesson["lessonId"] == first["lessonId"]
    assert lesson["title"] == "合并节课"
    assert runtime_store.get_lesson(
        course_id=course["courseId"],
        lesson_id=second["lessonId"],
        include_deleted=True,
    )["lessonStatus"] == "deleted"
    assert [(item["lessonId"], item["orderIndex"]) for item in _lesson_items(course["courseId"])] == [
        (first["lessonId"], 1),
        (third["lessonId"], 2),
    ]
    moved_note = runtime_store.get_resource(second_note["resourceId"])
    assert moved_note["scopeType"] == "lesson"
    assert moved_note["lessonId"] == first["lessonId"]
    assert runtime_store.scoped_artifacts[first_artifact["artifactId"]]["status"] == "stale"
    assert runtime_store.scoped_artifacts[second_artifact["artifactId"]]["status"] == "stale"
    assert set(body["data"]["staleArtifactIds"]) == {
        f"handout_version:{first_artifact['artifactId']}",
        f"quiz:{second_artifact['artifactId']}",
    }
    assert {
        (artifact["artifactType"], artifact["artifactId"])
        for artifact in body["data"]["staleArtifacts"]
    } == {
        ("handout_version", first_artifact["artifactId"]),
        ("quiz", second_artifact["artifactId"]),
    }


def test_merge_non_adjacent_lessons_returns_order_conflict() -> None:
    course = _create_course()
    first = runtime_store.create_lesson(course_id=course["courseId"], title="第 1 节")
    runtime_store.create_lesson(course_id=course["courseId"], title="第 2 节")
    third = runtime_store.create_lesson(course_id=course["courseId"], title="第 3 节")

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/merge",
        json_body={"lessonIds": [first["lessonId"], third["lessonId"]]},
    )

    assert status == 409
    assert body["errorCode"] == "lesson.order_conflict"


def test_split_lesson_by_video_timestamp_creates_new_lesson_with_same_video_ranges() -> None:
    course = _create_course()
    lesson = runtime_store.create_lesson(course_id=course["courseId"], title="完整节课")
    video = _mp4_resource(course["courseId"], name="split-video", lesson_id=lesson["lessonId"])
    resource_count = len(runtime_store.list_resources(course["courseId"]))
    runtime_store.update_lesson(
        course_id=course["courseId"],
        lesson_id=lesson["lessonId"],
        changes={"primaryVideoResourceId": video["resourceId"], "primaryVideoStartSec": 0, "primaryVideoEndSec": 600},
    )
    artifact = runtime_store.create_scoped_artifact(
        artifact_type="handout_version",
        course_id=course["courseId"],
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="ready",
    )

    status, body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/split",
        json_body={"splitAtSec": 240, "firstTitle": "前半节", "secondTitle": "后半节"},
    )

    assert status == 200
    first = body["data"]["firstLesson"]
    second = body["data"]["secondLesson"]
    assert first["lessonId"] == lesson["lessonId"]
    assert first["title"] == "前半节"
    assert first["primaryVideoResourceId"] == video["resourceId"]
    assert first["primaryVideoStartSec"] == 0
    assert first["primaryVideoEndSec"] == 240
    assert second["title"] == "后半节"
    assert second["primaryVideoResourceId"] == video["resourceId"]
    assert second["primaryVideoStartSec"] == 240
    assert second["primaryVideoEndSec"] == 600
    shared_video = runtime_store.get_resource(video["resourceId"])
    assert shared_video["scopeType"] == "course"
    assert shared_video["lessonId"] is None
    assert len(runtime_store.list_resources(course["courseId"])) == resource_count
    assert [(item["lessonId"], item["orderIndex"]) for item in _lesson_items(course["courseId"])] == [
        (first["lessonId"], 1),
        (second["lessonId"], 2),
    ]
    assert runtime_store.scoped_artifacts[artifact["artifactId"]]["status"] == "stale"
    assert body["data"]["staleArtifactIds"] == [f"handout_version:{artifact['artifactId']}"]
    assert body["data"]["staleArtifacts"][0]["artifactType"] == "handout_version"
