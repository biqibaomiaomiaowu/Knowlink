import asyncio
import importlib
import json
import logging
import re
import subprocess
import sys

import pytest

from server.app import app
from server.config.logging import JsonFormatter, configure_logging


AUTH_HEADERS = {"authorization": "Bearer knowlink-demo-token"}


async def request_raw(method: str, path: str, *, headers=None, json_body=None):
    raw_headers = [
        (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
    ]
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
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
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
    return status, payload


async def request(method: str, path: str, *, headers=None, json_body=None):
    status, payload = await request_raw(
        method,
        path,
        headers=headers,
        json_body=json_body,
    )
    return status, json.loads(payload.decode())


async def request_text(method: str, path: str, *, headers=None, json_body=None):
    status, payload = await request_raw(
        method,
        path,
        headers=headers,
        json_body=json_body,
    )
    return status, payload.decode()


def assert_idempotent_post(
    path: str,
    *,
    headers: dict[str, str],
    json_body=None,
    expected_status: int,
    identity_getter,
):
    first_status, first = asyncio.run(
        request("POST", path, headers=headers, json_body=json_body)
    )
    second_status, second = asyncio.run(
        request("POST", path, headers=headers, json_body=json_body)
    )
    assert first_status == expected_status
    assert second_status == expected_status
    assert identity_getter(first) == identity_getter(second)
    return first, second


def create_manual_course(*, idempotency_key: str, title: str) -> tuple[int, dict]:
    status, body = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": idempotency_key},
            json_body={
                "title": title,
                "entryType": "manual_import",
                "goalText": "Week 1 幂等验收",
                "preferredStyle": "balanced",
            },
        )
    )
    assert status == 201
    return body["data"]["course"]["courseId"], body


def upload_ready_pdf(*, course_id: int, idempotency_key: str, suffix: str) -> dict:
    return upload_ready_resource(
        course_id=course_id,
        idempotency_key=idempotency_key,
        suffix=suffix,
        resource_type="pdf",
        mime_type="application/pdf",
    )


def upload_ready_resource(
    *,
    course_id: int,
    idempotency_key: str,
    suffix: str,
    resource_type: str,
    mime_type: str,
) -> dict:
    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=AUTH_HEADERS | {"idempotency-key": idempotency_key},
            json_body={
                "resourceType": resource_type,
                "objectKey": f"raw/1/{course_id}/{suffix}.{resource_type}",
                "originalName": f"{suffix}.{resource_type}",
                "mimeType": mime_type,
                "sizeBytes": 1024,
                "checksum": f"sha256:{suffix}",
            },
        )
    )
    assert status == 201
    return body


def start_parse(*, course_id: int, idempotency_key: str) -> dict:
    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/parse/start",
            headers=AUTH_HEADERS | {"idempotency-key": idempotency_key},
        )
    )
    assert status == 200
    return body


def valid_inquiry_answers() -> list[dict[str, object]]:
    return [
        {"key": "goal_type", "value": "exam_sprint"},
        {"key": "mastery_level", "value": "intermediate"},
        {"key": "time_budget_minutes", "value": 90},
        {"key": "handout_style", "value": "exam"},
        {"key": "explanation_granularity", "value": "balanced"},
    ]


def test_health_check():
    status, payload = asyncio.run(request("GET", "/health"))
    assert status == 200
    assert payload == {"status": "ok"}


def test_metrics_endpoint_is_public_and_exposes_http_metrics():
    status, payload_text = asyncio.run(request_text("GET", "/metrics"))

    assert status == 200
    assert "knowlink_http_requests_total" in payload_text


def test_metrics_module_reload_reuses_registered_collectors():
    import server.observability.metrics as metrics

    reloaded = importlib.reload(metrics)

    assert reloaded.HTTP_REQUESTS_TOTAL is metrics.HTTP_REQUESTS_TOTAL
    status, payload_text = asyncio.run(request_text("GET", "/metrics"))
    assert status == 200
    assert "knowlink_http_requests_total" in payload_text


def test_unknown_routes_use_low_cardinality_metric_label():
    unique_path = "/missing-route-for-metrics-cardinality-89231"

    status, _ = asyncio.run(request_text("GET", unique_path))
    _, payload_text = asyncio.run(request_text("GET", "/metrics"))

    assert status == 404
    assert 'route="not_found"' in payload_text
    assert unique_path not in payload_text


def test_json_formatter_preserves_unknown_extra_fields():
    record = logging.LogRecord(
        name="server.tests",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="task updated",
        args=(),
        exc_info=None,
    )
    record.quiz_id = 17
    record.task_status = "finished"
    record.review_task_run_id = 23
    record.target_id = "target-9"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["quiz_id"] == 17
    assert payload["task_status"] == "finished"
    assert payload["review_task_run_id"] == 23
    assert payload["target_id"] == "target-9"


def test_configure_logging_writes_json_to_stderr():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import logging

from server.config.logging import configure_logging

configure_logging()
logging.getLogger("server.tests.logging").info(
    "stderr routing check",
    extra={"request_id": "req_logging_test"},
)
""",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    assert '"message":"stderr routing check"' in result.stderr
    assert '"request_id":"req_logging_test"' in result.stderr


def test_auth_is_required_for_api_routes():
    status, body = asyncio.run(request("GET", "/api/v1/home/dashboard"))
    assert status == 401
    assert body["errorCode"] == "auth.token_missing"


def test_recommendation_confirm_is_idempotent():
    status, recommendation_response = asyncio.run(
        request(
            "POST",
            "/api/v1/recommendations/courses",
            headers=AUTH_HEADERS,
            json_body={
                "goalText": "高等数学期末复习",
                "selfLevel": "intermediate",
                "timeBudgetMinutes": 240,
                "preferredStyle": "exam",
            },
        )
    )
    assert status == 200
    catalog_id = recommendation_response["data"]["recommendations"][0]["catalogId"]

    headers = AUTH_HEADERS | {"idempotency-key": "rec-confirm-1"}
    payload = {
        "goalText": "高等数学期末复习",
        "examAt": "2026-06-20T09:30:00+08:00",
        "preferredStyle": "exam",
        "titleOverride": "高数期末冲刺课",
    }
    first_status, first = asyncio.run(
        request(
            "POST",
            f"/api/v1/recommendations/{catalog_id}/confirm",
            headers=headers,
            json_body=payload,
        )
    )
    second_status, second = asyncio.run(
        request(
            "POST",
            f"/api/v1/recommendations/{catalog_id}/confirm",
            headers=headers,
            json_body=payload,
        )
    )
    assert first_status == 201
    assert second_status == 201
    assert first["data"]["course"]["courseId"] == second["data"]["course"]["courseId"]
    assert first["data"]["course"]["examAt"] == "2026-06-20T09:30:00+08:00"


def test_recommendation_confirm_idempotency_key_is_scoped_by_catalog():
    headers = AUTH_HEADERS | {"idempotency-key": "phase3-rec-confirm-shared"}
    first_status, first = asyncio.run(
        request(
            "POST",
            "/api/v1/recommendations/math-final-01/confirm",
            headers=headers,
            json_body={
                "goalText": "高数期末复习",
                "preferredStyle": "exam",
            },
        )
    )
    second_status, second = asyncio.run(
        request(
            "POST",
            "/api/v1/recommendations/linear-final-01/confirm",
            headers=headers,
            json_body={
                "goalText": "线性代数期末复习",
                "preferredStyle": "quick",
            },
        )
    )

    assert first_status == 201
    assert second_status == 201
    assert first["data"]["createdFromCatalogId"] == "math-final-01"
    assert second["data"]["createdFromCatalogId"] == "linear-final-01"
    assert first["data"]["course"]["courseId"] != second["data"]["course"]["courseId"]


def test_recommendation_confirm_rejects_naive_exam_at():
    status, body = asyncio.run(
        request(
            "POST",
            "/api/v1/recommendations/math-final-01/confirm",
            headers=AUTH_HEADERS | {"idempotency-key": "rec-confirm-naive-exam-at"},
            json_body={
                "goalText": "高数期末复习",
                "examAt": "2026-06-20T09:30:00",
                "preferredStyle": "exam",
            },
        )
    )

    assert status == 422
    assert body["errorCode"] == "common.validation_error"


def test_create_course_is_idempotent():
    headers = AUTH_HEADERS | {"idempotency-key": "manual-course-idempotent-1"}
    payload = {
        "title": "期末复习幂等课",
        "entryType": "manual_import",
        "goalText": "验证创建课程幂等",
        "examAt": "2026-06-20T09:30:00+08:00",
        "preferredStyle": "balanced",
    }
    first, _ = assert_idempotent_post(
        "/api/v1/courses",
        headers=headers,
        json_body=payload,
        expected_status=201,
        identity_getter=lambda body: body["data"]["course"]["courseId"],
    )
    assert first["data"]["course"]["title"] == "期末复习幂等课"
    assert first["data"]["course"]["examAt"] == "2026-06-20T09:30:00+08:00"


def test_create_course_rejects_naive_exam_at():
    status, body = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "manual-course-naive-exam-at"},
            json_body={
                "title": "naive examAt 课程",
                "entryType": "manual_import",
                "goalText": "验证 naive examAt",
                "examAt": "2026-06-20T09:30:00",
                "preferredStyle": "balanced",
            },
        )
    )

    assert status == 422
    assert body["errorCode"] == "common.validation_error"


def test_create_course_then_dashboard_shows_recent_course():
    status, _ = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "manual-course-1"},
            json_body={
                "title": "线性代数强化课",
                "entryType": "manual_import",
                "goalText": "期末复习",
                "preferredStyle": "balanced",
            },
        )
    )
    assert status == 201

    dashboard_status, dashboard = asyncio.run(
        request("GET", "/api/v1/home/dashboard", headers=AUTH_HEADERS)
    )
    assert dashboard_status == 200
    recent_courses = dashboard["data"]["recentCourses"]
    assert recent_courses
    assert recent_courses[0]["title"] in {"线性代数强化课", "高数期末冲刺课"}


def test_upload_complete_is_idempotent():
    course_id, _ = create_manual_course(
        idempotency_key="upload-complete-course-1",
        title="上传完成幂等课",
    )
    headers = AUTH_HEADERS | {"idempotency-key": "upload-complete-1"}
    payload = {
        "resourceType": "pdf",
        "objectKey": f"raw/1/{course_id}/upload-complete.pdf",
        "originalName": "upload-complete.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 1024,
        "checksum": "sha256:upload-complete-1",
    }
    first, _ = assert_idempotent_post(
        f"/api/v1/courses/{course_id}/resources/upload-complete",
        headers=headers,
        json_body=payload,
        expected_status=201,
        identity_getter=lambda body: body["data"]["resourceId"],
    )
    assert first["data"]["resourceType"] == "pdf"


def test_upload_complete_rejects_same_idempotency_key_with_different_body():
    course_id, _ = create_manual_course(
        idempotency_key="upload-complete-mismatch-course",
        title="上传完成幂等冲突课",
    )
    headers = AUTH_HEADERS | {"idempotency-key": "upload-complete-body-mismatch"}
    first_payload = {
        "resourceType": "pdf",
        "objectKey": f"raw/1/{course_id}/upload-mismatch-a.pdf",
        "originalName": "upload-mismatch-a.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 1024,
        "checksum": "sha256:upload-mismatch-a",
    }
    second_payload = first_payload | {
        "objectKey": f"raw/1/{course_id}/upload-mismatch-b.pdf",
        "originalName": "upload-mismatch-b.pdf",
        "checksum": "sha256:upload-mismatch-b",
    }

    first_status, first = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=headers,
            json_body=first_payload,
        )
    )
    second_status, second = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=headers,
            json_body=second_payload,
        )
    )

    assert first_status == 201
    assert first["data"]["resourceId"]
    assert second_status == 409
    assert second["errorCode"] == "idempotency.body_mismatch"


def test_upload_complete_idempotency_key_is_scoped_by_course():
    first_course_id, _ = create_manual_course(
        idempotency_key="phase3-upload-scope-course-1",
        title="上传幂等范围课 A",
    )
    second_course_id, _ = create_manual_course(
        idempotency_key="phase3-upload-scope-course-2",
        title="上传幂等范围课 B",
    )

    first = upload_ready_pdf(
        course_id=first_course_id,
        idempotency_key="phase3-upload-shared-key",
        suffix="phase3-upload-a",
    )
    second = upload_ready_pdf(
        course_id=second_course_id,
        idempotency_key="phase3-upload-shared-key",
        suffix="phase3-upload-b",
    )

    assert first["data"]["courseId"] == first_course_id
    assert second["data"]["courseId"] == second_course_id
    assert first["data"]["resourceId"] != second["data"]["resourceId"]


def test_resource_playback_returns_presigned_url_for_video():
    course_id, _ = create_manual_course(
        idempotency_key="playback-course-1",
        title="视频播放课",
    )
    upload = upload_ready_resource(
        course_id=course_id,
        idempotency_key="playback-video-upload-1",
        suffix="playback-video",
        resource_type="mp4",
        mime_type="video/mp4",
    )
    resource_id = upload["data"]["resourceId"]

    status, body = asyncio.run(
        request(
            "GET",
            f"/api/v1/course-resources/{resource_id}/playback",
            headers=AUTH_HEADERS,
        )
    )

    assert status == 200
    assert body["data"]["resourceId"] == resource_id
    assert body["data"]["resourceType"] == "mp4"
    assert body["data"]["playbackUrl"].startswith("http://object-storage.local/")
    assert "method=get" in body["data"]["playbackUrl"]
    assert body["data"]["mimeType"] == "video/mp4"
    assert body["data"]["durationSec"] is None


def test_resource_playback_rejects_non_video_and_missing_resource():
    course_id, _ = create_manual_course(
        idempotency_key="playback-course-2",
        title="非视频播放边界课",
    )
    upload = upload_ready_pdf(
        course_id=course_id,
        idempotency_key="playback-pdf-upload-1",
        suffix="playback-pdf",
    )

    non_video_status, non_video_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/course-resources/{upload['data']['resourceId']}/playback",
            headers=AUTH_HEADERS,
        )
    )
    missing_status, missing_body = asyncio.run(
        request(
            "GET",
            "/api/v1/course-resources/99999999/playback",
            headers=AUTH_HEADERS,
        )
    )

    assert non_video_status == 409
    assert non_video_body["errorCode"] == "resource.not_video"
    assert missing_status == 404
    assert missing_body["errorCode"] == "resource.not_found"


def test_parse_start_is_idempotent():
    course_id, _ = create_manual_course(
        idempotency_key="parse-start-course-1",
        title="解析幂等课",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key="parse-start-upload-1",
        suffix="parse-start",
    )
    headers = AUTH_HEADERS | {"idempotency-key": "parse-start-1"}
    first, _ = assert_idempotent_post(
        f"/api/v1/courses/{course_id}/parse/start",
        headers=headers,
        expected_status=200,
        identity_getter=lambda body: (
            body["data"]["entity"]["type"],
            body["data"]["entity"]["id"],
        ),
    )
    assert first["data"]["entity"]["type"] == "parse_run"


@pytest.mark.parametrize(
    ("raw_value", "suffix"),
    [
        (90.0, "float-zero-fraction"),
        (90.5, "float-fraction"),
    ],
)
def test_inquiry_answers_reject_raw_non_int_numbers_with_service_error(raw_value: float, suffix: str):
    course_id, _ = create_manual_course(
        idempotency_key=f"inquiry-number-course-{suffix}",
        title=f"问询数字校验课 {suffix}",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key=f"inquiry-number-upload-{suffix}",
        suffix=f"inquiry-number-{suffix}",
    )
    start_parse(
        course_id=course_id,
        idempotency_key=f"inquiry-number-parse-{suffix}",
    )
    answers = [
        answer if answer["key"] != "time_budget_minutes" else {"key": "time_budget_minutes", "value": raw_value}
        for answer in valid_inquiry_answers()
    ]

    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/inquiry/answers",
            headers=AUTH_HEADERS,
            json_body={"answers": answers},
        )
    )

    assert status == 422
    assert body["errorCode"] == "inquiry.answers_invalid"


@pytest.mark.parametrize(
    ("raw_value", "suffix"),
    [
        (["exam_sprint"], "list"),
        ({"value": "exam_sprint"}, "dict"),
    ],
)
def test_inquiry_answers_reject_raw_non_string_single_select_values(raw_value, suffix: str):
    course_id, _ = create_manual_course(
        idempotency_key=f"inquiry-select-course-{suffix}",
        title=f"问询单选校验课 {suffix}",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key=f"inquiry-select-upload-{suffix}",
        suffix=f"inquiry-select-{suffix}",
    )
    start_parse(
        course_id=course_id,
        idempotency_key=f"inquiry-select-parse-{suffix}",
    )
    answers = [
        answer if answer["key"] != "goal_type" else {"key": "goal_type", "value": raw_value}
        for answer in valid_inquiry_answers()
    ]

    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/inquiry/answers",
            headers=AUTH_HEADERS,
            json_body={"answers": answers},
        )
    )

    assert status == 422
    assert body["errorCode"] == "inquiry.answers_invalid"


def test_handout_generate_is_idempotent():
    course_id, _ = create_manual_course(
        idempotency_key="handout-generate-course-1",
        title="讲义幂等课",
    )
    upload_ready_pdf(
        course_id=course_id,
        idempotency_key="handout-generate-upload-1",
        suffix="handout-generate",
    )
    parse_start = start_parse(
        course_id=course_id,
        idempotency_key="handout-generate-parse-1",
    )
    assert parse_start["data"]["entity"]["type"] == "parse_run"
    headers = AUTH_HEADERS | {"idempotency-key": "handout-generate-1"}
    first, _ = assert_idempotent_post(
        f"/api/v1/courses/{course_id}/handouts/generate",
        headers=headers,
        expected_status=200,
        identity_getter=lambda body: (
            body["data"]["entity"]["type"],
            body["data"]["entity"]["id"],
        ),
    )
    assert first["data"]["entity"]["type"] == "handout_version"


def test_quiz_generate_is_idempotent():
    course_id, _ = create_manual_course(
        idempotency_key="quiz-generate-course-1",
        title="测验幂等课",
    )
    headers = AUTH_HEADERS | {"idempotency-key": "quiz-generate-1"}
    first, _ = assert_idempotent_post(
        f"/api/v1/courses/{course_id}/quizzes/generate",
        headers=headers,
        expected_status=200,
        identity_getter=lambda body: (
            body["data"]["entity"]["type"],
            body["data"]["entity"]["id"],
        ),
    )
    assert first["data"]["entity"]["type"] == "quiz"


def test_quiz_generate_accepts_question_count_level_and_defaults_to_medium():
    course_id, _ = create_manual_course(
        idempotency_key="quiz-generate-level-course",
        title="测验档位课",
    )

    default_status, default_body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/quizzes/generate",
            headers=AUTH_HEADERS | {"idempotency-key": "quiz-generate-level-default"},
        )
    )
    small_status, small_body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/quizzes/generate",
            headers=AUTH_HEADERS | {"idempotency-key": "quiz-generate-level-small"},
            json_body={"questionCountLevel": "small"},
        )
    )
    invalid_status, invalid_body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/quizzes/generate",
            headers=AUTH_HEADERS | {"idempotency-key": "quiz-generate-level-invalid"},
            json_body={"questionCountLevel": "tiny"},
        )
    )

    assert default_status == 200
    assert default_body["data"]["entity"]["type"] == "quiz"
    assert small_status == 200
    assert small_body["data"]["entity"]["type"] == "quiz"
    assert invalid_status == 422
    assert invalid_body["code"] == 1


def test_review_regenerate_is_idempotent():
    course_id, _ = create_manual_course(
        idempotency_key="review-regenerate-course-1",
        title="复习幂等课",
    )
    headers = AUTH_HEADERS | {"idempotency-key": "review-regenerate-1"}
    first, _ = assert_idempotent_post(
        f"/api/v1/courses/{course_id}/review-tasks/regenerate",
        headers=headers,
        expected_status=200,
        identity_getter=lambda body: (
            "review_task_run",
            body["data"]["reviewTaskRunId"],
        ),
    )
    assert first["data"]["status"] == "ready"
    assert isinstance(first["data"]["reviewTaskRunId"], int)


def test_delete_missing_resource_returns_not_found():
    status, created = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "delete-resource-course-1"},
            json_body={
                "title": "资源删除边界课",
                "entryType": "manual_import",
                "goalText": "验证资源删除错误码",
                "preferredStyle": "balanced",
            },
        )
    )
    assert status == 201
    course_id = created["data"]["course"]["courseId"]

    delete_status, delete_payload = asyncio.run(
        request(
            "DELETE",
            f"/api/v1/courses/{course_id}/resources/99999",
            headers=AUTH_HEADERS,
        )
    )
    assert delete_status == 404
    assert delete_payload["errorCode"] == "resource.not_found"


def test_bilibili_routes_require_auth():
    requests_to_check = [
        ("POST", "/api/v1/courses/101/resources/imports/bilibili", {"videoUrl": "https://www.bilibili.com/video/BV1LLDCYJEU3/"}),
        ("GET", "/api/v1/courses/101/resources/imports/bilibili", None),
        ("GET", "/api/v1/bilibili-import-runs/9001/status", None),
        ("POST", "/api/v1/bilibili-import-runs/9001/cancel", None),
        ("POST", "/api/v1/bilibili/auth/qr/sessions", None),
        ("GET", "/api/v1/bilibili/auth/qr/sessions/session-demo-1", None),
        ("GET", "/api/v1/bilibili/auth/session", None),
        ("DELETE", "/api/v1/bilibili/auth/session", None),
    ]

    for method, path, payload in requests_to_check:
        status, body = asyncio.run(request(method, path, json_body=payload))
        assert status == 401
        assert body["errorCode"] == "auth.token_missing"


def test_bilibili_reserved_routes_return_not_implemented():
    requests_to_check = [
        ("POST", "/api/v1/courses/101/resources/imports/bilibili", None),
        ("POST", "/api/v1/courses/101/resources/imports/bilibili", {}),
        ("POST", "/api/v1/courses/101/resources/imports/bilibili", {"videoUrl": ""}),
        ("POST", "/api/v1/courses/101/resources/imports/bilibili", {"videoUrl": "https://www.bilibili.com/video/BV1LLDCYJEU3/"}),
        ("GET", "/api/v1/courses/101/resources/imports/bilibili", None),
        ("GET", "/api/v1/bilibili-import-runs/9001/status", None),
        ("POST", "/api/v1/bilibili-import-runs/9001/cancel", None),
        ("POST", "/api/v1/bilibili/auth/qr/sessions", None),
        ("GET", "/api/v1/bilibili/auth/qr/sessions/session-demo-1", None),
        ("GET", "/api/v1/bilibili/auth/session", None),
        ("DELETE", "/api/v1/bilibili/auth/session", None),
    ]

    for method, path, payload in requests_to_check:
        status, body = asyncio.run(
            request(
                method,
                path,
                headers=AUTH_HEADERS,
                json_body=payload,
            )
        )
        assert status == 501
        assert body["errorCode"] == "bilibili.not_implemented"


def test_bilibili_import_openapi_keeps_reserved_request_body():
    schema = app.openapi()
    snake_case_placeholder = re.compile(r"\{[a-z]+(?:_[a-z0-9]+)+\}")
    assert not [
        path for path in schema["paths"] if snake_case_placeholder.search(path)
    ]
    path, operation = next(
        (path, item["post"])
        for path, item in schema["paths"].items()
        if path.endswith("/courses/{courseId}/resources/imports/bilibili")
    )

    assert path.startswith("/api/v1/")
    request_body = operation["requestBody"]
    content_schema = request_body["content"]["application/json"]["schema"]
    assert any(
        item.get("$ref", "").endswith("/BilibiliImportRequest")
        for item in content_schema.get("anyOf", [])
    )
    component_schema = schema["components"]["schemas"]["BilibiliImportRequest"]
    assert "videoUrl" in component_schema["properties"]
