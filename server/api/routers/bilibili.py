from fastapi import APIRouter, Depends, Request

from server.api.deps import get_bilibili_service
from server.api.response import api_ok
from server.domain.services import BilibiliService
from server.schemas.requests import BilibiliImportRequest

router = APIRouter(tags=["bilibili"])


@router.post("/courses/{course_id}/resources/imports/bilibili")
async def create_bilibili_import(
    course_id: int,
    request: Request,
    payload: BilibiliImportRequest | None = None,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.create_import(
            course_id=course_id,
            video_url=payload.video_url if payload else None,
            idempotency_key=request.headers.get("Idempotency-Key"),
        ),
    )


@router.get("/courses/{course_id}/resources/imports/bilibili")
async def list_bilibili_imports(
    course_id: int,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.list_imports(course_id=course_id))


@router.get("/bilibili-import-runs/{import_run_id}/status")
async def get_bilibili_import_status(
    import_run_id: int,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.get_import_status(import_run_id=import_run_id))


@router.post("/bilibili-import-runs/{import_run_id}/cancel")
async def cancel_bilibili_import(
    import_run_id: int,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.cancel_import(
            import_run_id=import_run_id,
            idempotency_key=request.headers.get("Idempotency-Key"),
        ),
    )


@router.post("/bilibili/auth/qr/sessions")
async def create_bilibili_qr_session(
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.create_qr_session())


@router.get("/bilibili/auth/qr/sessions/{session_id}")
async def get_bilibili_qr_session(
    session_id: str,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(request, service.get_qr_session(session_id=session_id))


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
