from fastapi import APIRouter, Depends, Request

from server.api.deps import get_bilibili_service
from server.api.response import api_ok
from server.domain.services import BilibiliService
from server.schemas.requests import BilibiliImportRequest, BilibiliPreviewRequest

router = APIRouter(tags=["bilibili"])


@router.post("/courses/{courseId}/resources/imports/bilibili/preview")
async def preview_bilibili_import(
    courseId: int,
    request: Request,
    payload: BilibiliPreviewRequest,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.preview_import(
            course_id=courseId,
            source_url=payload.source_url,
        ),
    )


@router.post("/courses/{courseId}/resources/imports/bilibili")
async def create_bilibili_import(
    courseId: int,
    request: Request,
    payload: BilibiliImportRequest,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.create_import(
            course_id=courseId,
            preview_id=payload.preview_id,
            source_url=payload.source_url,
            selection_mode=payload.selection_mode,
            selected_part_ids=payload.selected_part_ids,
            quality_preference=payload.quality_preference,
            lesson_mode=payload.lesson_mode,
            target_lesson_id=payload.target_lesson_id,
            part_lesson_titles=payload.part_lesson_titles,
            part_lesson_map=payload.part_lesson_map,
            create_lesson_if_missing=payload.create_lesson_if_missing,
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
