import asyncio
import json
import re

from server.app import app


AUTH_HEADERS = {"authorization": "Bearer knowlink-demo-token"}


async def request(method: str, path: str, *, headers=None, json_body=None):
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
    return status, json.loads(payload.decode())


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
    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=AUTH_HEADERS | {"idempotency-key": idempotency_key},
            json_body={
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/{suffix}.pdf",
                "originalName": f"{suffix}.pdf",
                "mimeType": "application/pdf",
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


def test_health_check():
    status, payload = asyncio.run(request("GET", "/health"))
    assert status == 200
    assert payload == {"status": "ok"}


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


def test_create_course_is_idempotent():
    headers = AUTH_HEADERS | {"idempotency-key": "manual-course-idempotent-1"}
    payload = {
        "title": "期末复习幂等课",
        "entryType": "manual_import",
        "goalText": "验证创建课程幂等",
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
            body["data"]["entity"]["type"],
            body["data"]["entity"]["id"],
        ),
    )
    assert first["data"]["entity"]["type"] == "review_task_run"


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
