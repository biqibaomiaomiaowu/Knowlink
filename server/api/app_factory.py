from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from server.api.response import api_error
from server.api.router import build_router
from server.config.logging import configure_logging
from server.config.settings import get_settings
from server.domain.services import ServiceError


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


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(RequestIdMiddleware)

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

    app.include_router(build_router())
    return app
