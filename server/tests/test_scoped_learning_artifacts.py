from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import fields
from typing import Any

import pytest

from server.infra.repositories.memory_runtime import RuntimeStore, runtime_store
from server.tests.test_api import AUTH_HEADERS, request


@pytest.fixture(autouse=True)
def isolated_runtime_store():
    store_fields = [field.name for field in fields(runtime_store) if field.name != "lock"]
    snapshot = {field_name: deepcopy(getattr(runtime_store, field_name)) for field_name in store_fields}
    fresh = RuntimeStore()
    for field_name in store_fields:
        setattr(runtime_store, field_name, deepcopy(getattr(fresh, field_name)))
    yield
    for field_name, value in snapshot.items():
        setattr(runtime_store, field_name, value)


def _api(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    return asyncio.run(request(method, path, headers=AUTH_HEADERS, json_body=json_body))


def _course(title: str = "数据库系统", **overrides: Any) -> dict[str, Any]:
    return runtime_store.create_course(
        title=title,
        entry_type="manual_import",
        goal_text="期末复习",
        preferred_style="balanced",
        **overrides,
    )


def _lesson(course_id: int, title: str, **overrides: Any) -> dict[str, Any]:
    return runtime_store.create_lesson(course_id=course_id, title=title, **overrides)


def _resource(course_id: int, *, name: str, resource_type: str, lesson_id: int | None = None) -> dict[str, Any]:
    return runtime_store.create_resource(
        course_id,
        {
            "resourceType": resource_type,
            "sourceType": "upload",
            "objectKey": f"raw/{name}.{resource_type}",
            "originalName": f"{name}.{resource_type}",
            "mimeType": "video/mp4" if resource_type == "mp4" else "application/pdf",
            "sizeBytes": 1024,
            "checksum": f"sha256:{name}",
            "scopeType": "lesson" if lesson_id is not None else "course",
            "lessonId": lesson_id,
            "usageRole": "primary_video" if resource_type == "mp4" and lesson_id is not None else "lesson_material",
            "visibleToCourseQa": lesson_id is None,
            "durationSec": 600 if resource_type == "mp4" else None,
        },
    )


def _bind_primary_video(course_id: int, lesson_id: int, name: str = "lesson-video") -> dict[str, Any]:
    video = _resource(course_id, name=name, resource_type="mp4", lesson_id=lesson_id)
    runtime_store.update_lesson(
        course_id=course_id,
        lesson_id=lesson_id,
        changes={"primary_video_resource_id": video["resourceId"]},
    )
    return video


def test_course_and_lesson_handout_placeholders_are_scoped() -> None:
    course = _course()
    lesson_without_video = _lesson(course["courseId"], "无主视频节课")
    lesson_with_video = _lesson(course["courseId"], "有主视频节课")
    _bind_primary_video(course["courseId"], lesson_with_video["lessonId"])

    course_status, course_body = _api("GET", f"/api/v1/courses/{course['courseId']}/handouts/course-summary")
    missing_status, missing_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson_without_video['lessonId']}/handout",
    )
    ready_status, ready_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson_with_video['lessonId']}/handout",
    )

    assert course_status == 200
    assert course_body["data"]["scopeType"] == "course"
    assert course_body["data"]["lessonId"] is None
    assert course_body["data"]["artifactKind"] == "course_summary_handout"
    assert {"lessons", "course_resources", "lesson_handouts"}.issubset(
        set(course_body["data"]["requiredSources"])
    )
    assert missing_status == 200
    assert missing_body["data"]["scopeType"] == "lesson"
    assert missing_body["data"]["lessonId"] == lesson_without_video["lessonId"]
    assert missing_body["data"]["artifactKind"] == "lesson_handout"
    assert missing_body["data"]["canGenerate"] is False
    assert "primary_video" in missing_body["data"]["requiredSources"]
    assert ready_status == 200
    assert ready_body["data"]["canGenerate"] is True


def test_course_and_lesson_qa_sessions_are_separate_and_lesson_citations_are_scoped() -> None:
    course = _course()
    lesson = _lesson(course["courseId"], "关系模型")
    other_lesson = _lesson(course["courseId"], "事务隔离")
    lesson_video = _bind_primary_video(course["courseId"], lesson["lessonId"], name="relational-video")
    other_resource = _resource(
        course["courseId"],
        name="transaction-notes",
        resource_type="pdf",
        lesson_id=other_lesson["lessonId"],
    )

    course_status, course_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/qa/messages",
        json_body={"question": "全课程有哪些重点？"},
    )
    lesson_status, lesson_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/qa/messages",
        json_body={"question": "本节课讲了什么？"},
    )
    course_list_status, course_list_body = _api("GET", f"/api/v1/courses/{course['courseId']}/qa/sessions")
    lesson_list_status, lesson_list_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/qa/sessions",
    )
    resource_qa_status, _resource_qa_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/resources/{lesson_video['resourceId']}/qa/messages",
        json_body={"question": "不能按单资源提问"},
    )

    assert course_status == 200
    assert lesson_status == 200
    assert course_body["data"]["scopeType"] == "course"
    assert lesson_body["data"]["scopeType"] == "lesson"
    assert lesson_body["data"]["lessonId"] == lesson["lessonId"]
    assert course_body["data"]["sessionId"] != lesson_body["data"]["sessionId"]
    assert course_list_status == 200
    assert [item["sessionId"] for item in course_list_body["data"]["items"]] == [course_body["data"]["sessionId"]]
    assert lesson_list_status == 200
    assert [item["sessionId"] for item in lesson_list_body["data"]["items"]] == [lesson_body["data"]["sessionId"]]
    assert {citation["resourceId"] for citation in lesson_body["data"]["citations"]} == {lesson_video["resourceId"]}
    assert all(citation["lessonId"] == lesson["lessonId"] for citation in lesson_body["data"]["citations"])
    assert all(citation["lessonTitle"] == "关系模型" for citation in lesson_body["data"]["citations"])
    assert other_resource["resourceId"] not in {citation["resourceId"] for citation in lesson_body["data"]["citations"]}
    assert resource_qa_status == 404


def test_scoped_quiz_generation_and_subjective_grading_placeholder() -> None:
    course = _course()
    first = _lesson(course["courseId"], "第 1 节")
    second = _lesson(course["courseId"], "第 2 节")

    lesson_status, lesson_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/lessons/{first['lessonId']}/quizzes/generate",
        json_body={"questionCountLevel": "small"},
    )
    current_status, current_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{first['lessonId']}/quizzes/current",
    )
    stage_status, stage_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/quizzes/stage/generate",
        json_body={"startLessonId": first["lessonId"], "endLessonId": second["lessonId"]},
    )
    comprehensive_status, comprehensive_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/quizzes/comprehensive/generate",
    )
    grading_status, grading_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/subjective-grading/placeholder",
    )

    assert lesson_status == 200
    assert lesson_body["data"]["scopeType"] == "lesson"
    assert lesson_body["data"]["lessonId"] == first["lessonId"]
    assert current_status == 200
    assert current_body["data"]["quizId"] == lesson_body["data"]["quizId"]
    assert stage_status == 200
    assert stage_body["data"]["scopeType"] == "lesson_range"
    assert stage_body["data"]["startLessonId"] == first["lessonId"]
    assert stage_body["data"]["endLessonId"] == second["lessonId"]
    assert comprehensive_status == 200
    assert comprehensive_body["data"]["scopeType"] == "course"
    assert comprehensive_body["data"]["lessonId"] is None
    assert grading_status == 200
    assert grading_body["data"]["gradingStatus"] == "placeholder"
    assert grading_body["data"]["totalScore"] is None
    assert grading_body["data"]["needsHumanReview"] is False
    assert grading_body["data"]["citations"] == []


def test_review_scope_exam_review_and_lesson_progress() -> None:
    course = _course(exam_at="2026-07-01T09:00:00+08:00")
    lesson = _lesson(course["courseId"], "索引优化")
    runtime_store.create_handout(course["courseId"])
    handout_id = runtime_store.handout_by_course[course["courseId"]]
    block_id = runtime_store.handouts[handout_id]["blocks"][0]["blockId"]

    lesson_review_status, lesson_review_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/review",
    )
    course_review_status, course_review_body = _api("GET", f"/api/v1/courses/{course['courseId']}/review")
    exam_review_status, exam_review_body = _api("GET", f"/api/v1/courses/{course['courseId']}/exam-review")
    update_status, update_body = _api(
        "PUT",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/progress",
        json_body={
            "lastPositionSec": 321,
            "lastHandoutBlockId": block_id,
            "handoutReadPercent": 45,
            "quizStatus": "completed",
            "reviewStatus": "in_progress",
        },
    )
    get_status, get_body = _api("GET", f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/progress")

    assert lesson_review_status == 200
    assert lesson_review_body["data"]["scopeType"] == "lesson"
    assert lesson_review_body["data"]["lessonId"] == lesson["lessonId"]
    assert lesson_review_body["data"]["items"][0]["lessonId"] == lesson["lessonId"]
    assert "evidenceChain" in lesson_review_body["data"]["items"][0]
    assert course_review_status == 200
    assert course_review_body["data"]["scopeType"] == "course"
    assert course_review_body["data"]["weakLessons"][0]["lessonId"] == lesson["lessonId"]
    assert course_review_body["data"]["crossLessonWeakPoints"]
    assert exam_review_status == 200
    assert exam_review_body["data"]["status"] == "placeholder"
    assert exam_review_body["data"]["examAt"] == "2026-07-01T09:00:00+08:00"
    assert update_status == 200
    assert update_body["data"]["lastPositionSec"] == 321
    assert get_status == 200
    assert get_body["data"]["lastPositionSec"] == 321
    assert get_body["data"]["lastHandoutBlockId"] == block_id
    assert get_body["data"]["handoutReadPercent"] == 45
    assert get_body["data"]["quizStatus"] == "completed"
    assert get_body["data"]["reviewStatus"] == "in_progress"


def test_graph_report_and_export_placeholders() -> None:
    course = _course()
    lesson = _lesson(course["courseId"], "查询优化")

    course_graph_status, course_graph_body = _api("GET", f"/api/v1/courses/{course['courseId']}/graph")
    lesson_graph_status, lesson_graph_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/graph",
    )
    course_report_status, course_report_body = _api("GET", f"/api/v1/courses/{course['courseId']}/reports/summary")
    lesson_report_status, lesson_report_body = _api(
        "GET",
        f"/api/v1/courses/{course['courseId']}/lessons/{lesson['lessonId']}/reports/summary",
    )
    export_list_status, export_list_body = _api("GET", f"/api/v1/courses/{course['courseId']}/exports")
    export_create_status, export_create_body = _api(
        "POST",
        f"/api/v1/courses/{course['courseId']}/exports",
        json_body={"exportType": "course_summary"},
    )

    assert course_graph_status == 200
    assert course_graph_body["data"]["scopeType"] == "course"
    assert course_graph_body["data"]["status"] == "placeholder"
    assert course_graph_body["data"]["nodes"] == []
    assert course_graph_body["data"]["edges"] == []
    assert lesson_graph_status == 200
    assert lesson_graph_body["data"]["scopeType"] == "lesson"
    assert lesson_graph_body["data"]["lessonId"] == lesson["lessonId"]
    assert course_report_status == 200
    assert course_report_body["data"]["summaryStatus"] == "placeholder"
    assert lesson_report_status == 200
    assert lesson_report_body["data"]["scopeType"] == "lesson"
    assert export_list_status == 200
    assert "course_summary" in export_list_body["data"]["availableExportTypes"]
    assert export_list_body["data"]["downloadUrl"] is None
    assert export_create_status == 200
    assert export_create_body["data"]["status"] == "placeholder"
    assert export_create_body["data"]["exportType"] == "course_summary"
