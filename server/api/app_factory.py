from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from server.api.response import api_error
from server.api.router import build_router
from server.config.logging import configure_logging
from server.config.settings import get_settings
from server.domain.services import ServiceError
from server.observability.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    metrics_response,
)


logger = logging.getLogger("server.api.access")


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope.setdefault("state", {})
            scope["state"]["request_id"] = None
            for key, value in scope.get("headers", []):
                if key == b"x-request-id":
                    scope["state"]["request_id"] = value.decode()
                    break
            if not scope["state"]["request_id"]:
                scope["state"]["request_id"] = f"req_{uuid4().hex}"
        await self.app(scope, receive, send)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = _route_label(request, status_code=status_code)
            duration_seconds = time.perf_counter() - started_at
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                route=route,
                status_code=str(status_code),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                route=route,
            ).observe(duration_seconds)
            logger.info(
                "http request completed",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "method": request.method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration_seconds * 1000, 3),
                },
            )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AccessLogMiddleware)
    cors_allow_origins, cors_allow_origin_regex = _build_cors_origin_rules(settings.cors_allow_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_origin_regex=cors_allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def on_http_exception(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return api_error(
            request,
            message=detail.get("message", "Request failed."),
            error_code=detail.get("errorCode", "common.not_found"),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError):
        return api_error(
            request,
            message="Request validation failed.",
            error_code="common.validation_error",
            status_code=422,
        )

    @app.exception_handler(ServiceError)
    async def on_service_error(request: Request, exc: ServiceError):
        return api_error(
            request,
            message=exc.message,
            error_code=exc.error_code,
            status_code=exc.status_code,
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        content, content_type = metrics_response()
        return Response(content=content, headers={"Content-Type": content_type})

    app.include_router(build_router())
    return app


def _route_label(request: Request, *, status_code: int) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    if status_code == 404:
        return "not_found"
    return "unknown"


def _build_cors_origin_rules(origins: tuple[str, ...]) -> tuple[list[str], str | None]:
    exact_origins: list[str] = []
    regex_parts: list[str] = []
    for origin in origins:
        if origin.endswith(":*"):
            regex_parts.append(re.escape(origin[:-2]) + r":\d+")
        else:
            exact_origins.append(origin)
    if not regex_parts:
        return exact_origins, None
    return exact_origins, r"^(?:" + "|".join(regex_parts) + r")$"
