from __future__ import annotations

import asyncio

import pytest
from minio.error import S3Error

from server.api.app_factory import _build_cors_origin_rules, create_app
from server.config.settings import get_settings
from scripts.init_minio_bucket import build_bucket_cors_xml, configure_bucket_cors


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _request(app, method: str, path: str, *, headers: dict[str, str]) -> tuple[int, dict[str, str]]:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
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
    incoming = [{"type": "http.request", "body": b"", "more_body": False}]
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
    start = next(message for message in outgoing if message["type"] == "http.response.start")
    response_headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}
    return start["status"], response_headers


def test_fastapi_cors_allows_default_flutter_web_localhost(monkeypatch):
    monkeypatch.delenv("KNOWLINK_CORS_ALLOW_ORIGINS", raising=False)
    get_settings.cache_clear()
    app = create_app()

    status, headers = asyncio.run(
        _request(
            app,
            "OPTIONS",
            "/api/v1/home/dashboard",
            headers={
                "origin": "http://localhost:5173",
                "access-control-request-method": "GET",
                "access-control-request-headers": "authorization,content-type",
            },
        )
    )

    assert status == 200
    assert headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "authorization" in headers["access-control-allow-headers"].lower()
    assert "content-type" in headers["access-control-allow-headers"].lower()


def test_fastapi_cors_allow_origins_can_be_explicitly_tightened(monkeypatch):
    monkeypatch.setenv("KNOWLINK_CORS_ALLOW_ORIGINS", "https://app.example.com")
    get_settings.cache_clear()
    app = create_app()

    allowed_status, allowed_headers = asyncio.run(
        _request(
            app,
            "OPTIONS",
            "/api/v1/home/dashboard",
            headers={
                "origin": "https://app.example.com",
                "access-control-request-method": "GET",
            },
        )
    )
    blocked_status, blocked_headers = asyncio.run(
        _request(
            app,
            "OPTIONS",
            "/api/v1/home/dashboard",
            headers={
                "origin": "http://localhost:5173",
                "access-control-request-method": "GET",
            },
        )
    )

    assert allowed_status == 200
    assert allowed_headers["access-control-allow-origin"] == "https://app.example.com"
    assert blocked_status == 400
    assert "access-control-allow-origin" not in blocked_headers


def test_cors_origin_rule_builder_handles_local_port_wildcards():
    exact, regex = _build_cors_origin_rules(("http://localhost:*", "https://app.example.com"))

    assert exact == ["https://app.example.com"]
    assert regex == r"^(?:http://localhost:\d+)$"


def test_minio_bucket_cors_xml_allows_video_playback_and_seek_headers():
    xml = build_bucket_cors_xml(("http://localhost:*", "http://127.0.0.1:*"))

    for token in (
        "<AllowedOrigin>http://localhost:*</AllowedOrigin>",
        "<AllowedOrigin>http://127.0.0.1:*</AllowedOrigin>",
        "<AllowedMethod>GET</AllowedMethod>",
        "<AllowedMethod>HEAD</AllowedMethod>",
        "<AllowedMethod>PUT</AllowedMethod>",
        "<AllowedHeader>Authorization</AllowedHeader>",
        "<AllowedHeader>Content-Type</AllowedHeader>",
        "<AllowedHeader>Range</AllowedHeader>",
        "<AllowedHeader>x-amz-*</AllowedHeader>",
        "<ExposeHeader>Accept-Ranges</ExposeHeader>",
        "<ExposeHeader>Content-Range</ExposeHeader>",
        "<ExposeHeader>Content-Length</ExposeHeader>",
        "<ExposeHeader>Content-Type</ExposeHeader>",
        "<ExposeHeader>ETag</ExposeHeader>",
    ):
        assert token in xml
    assert "<AllowedMethod>OPTIONS</AllowedMethod>" not in xml


def test_minio_bucket_init_applies_cors_configuration():
    class FakeMinioClient:
        def __init__(self) -> None:
            self.calls = []

        def _execute(self, method, *, bucket_name, body, headers, query_params):
            self.calls.append(
                {
                    "method": method,
                    "bucketName": bucket_name,
                    "body": body.decode("utf-8"),
                    "headers": headers,
                    "queryParams": query_params,
                }
            )

    client = FakeMinioClient()

    configured = configure_bucket_cors(
        client,
        bucket_name="knowlink",
        allowed_origins=("http://localhost:*",),
    )

    assert configured is True
    assert client.calls == [
        {
            "method": "PUT",
            "bucketName": "knowlink",
            "body": build_bucket_cors_xml(("http://localhost:*",)),
            "headers": {"Content-Type": "application/xml"},
            "queryParams": {"cors": ""},
        }
    ]


def test_minio_bucket_init_skips_unsupported_bucket_cors_configuration(capsys):
    class FakeMinioClient:
        def _execute(self, method, *, bucket_name, body, headers, query_params):
            raise S3Error(
                response=None,
                code="NotImplemented",
                message="A header you provided implies functionality that is not implemented",
                resource=f"/{bucket_name}",
                request_id="",
                host_id="",
                bucket_name=bucket_name,
            )

    configured = configure_bucket_cors(
        FakeMinioClient(),
        bucket_name="knowlink",
        allowed_origins=("http://localhost:*",),
    )

    assert configured is False
    assert "server-level CORS settings" in capsys.readouterr().out


def test_minio_bucket_init_reraises_other_cors_configuration_errors():
    class FakeMinioClient:
        def _execute(self, method, *, bucket_name, body, headers, query_params):
            raise S3Error(
                response=None,
                code="AccessDenied",
                message="Access denied",
                resource=f"/{bucket_name}",
                request_id="",
                host_id="",
                bucket_name=bucket_name,
            )

    with pytest.raises(S3Error, match="AccessDenied"):
        configure_bucket_cors(
            FakeMinioClient(),
            bucket_name="knowlink",
            allowed_origins=("http://localhost:*",),
        )
