import asyncio
import json

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
