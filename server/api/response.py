from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def api_ok(request: Request, data: Any, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "code": 0,
                "message": "ok",
                "data": data,
                "requestId": request.state.request_id,
                "timestamp": _timestamp(),
            }
        ),
    )


def api_error(
    request: Request,
    *,
    message: str,
    error_code: str,
    status_code: int,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "code": 1,
                "message": message,
                "errorCode": error_code,
                "data": None,
                "requestId": request.state.request_id,
                "timestamp": _timestamp(),
            }
        ),
    )
