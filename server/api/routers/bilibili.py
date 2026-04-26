from fastapi import APIRouter, Depends, Request

from server.api.deps import get_bilibili_service
from server.api.response import api_ok
from server.domain.services import BilibiliService
from server.schemas.requests import BilibiliImportRequest

router = APIRouter(tags=["bilibili"])


@router.post("/courses/{courseId}/resources/imports/bilibili")
async def create_bilibili_import(
    courseId: int,
    request: Request,
    payload: BilibiliImportRequest | None = None,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.create_import(
            course_id=courseId,
            video_url=payload.video_url if payload else None,
            idempotency_key=request.headers.get("Idempotency-Key"),
        ),
    )


@router.get("/courses/{courseId}/resources/imports/bilibili")
async def list_bilibili_imports(
    courseId: int,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.list_imports(course_id=courseId))


@router.get("/bilibili-import-runs/{importRunId}/status")
async def get_bilibili_import_status(
    importRunId: int,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.get_import_status(import_run_id=importRunId))


@router.post("/bilibili-import-runs/{importRunId}/cancel")
async def cancel_bilibili_import(
    importRunId: int,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.cancel_import(
            import_run_id=importRunId,
            idempotency_key=request.headers.get("Idempotency-Key"),
        ),
    )


@router.post("/bilibili/auth/qr/sessions")
async def create_bilibili_qr_session(
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.create_qr_session())


@router.get("/bilibili/auth/qr/sessions/{sessionId}")
async def get_bilibili_qr_session(
    sessionId: str,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.get_qr_session(session_id=sessionId))


@router.get("/bilibili/auth/session")
async def get_bilibili_auth_session(
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.get_auth_session())


@router.delete("/bilibili/auth/session")
async def delete_bilibili_auth_session(
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.delete_auth_session())
