from fastapi import APIRouter, Depends, Request

from server.api.deps import get_handout_service
from server.api.response import api_ok
from server.domain.services import HandoutService

router = APIRouter(tags=["handouts"])


@router.post("/courses/{courseId}/handouts/generate")
async def generate_handout(
    courseId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    data = service.generate_handout(
        course_id=courseId,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/handout-versions/{handoutVersionId}/status")
async def get_handout_status(
    handoutVersionId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_status(handout_version_id=handoutVersionId))


@router.get("/courses/{courseId}/handouts/latest")
async def get_latest_handout(
    courseId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_latest_handout(course_id=courseId))


@router.get("/courses/{courseId}/handouts/latest/outline")
async def get_latest_handout_outline(
    courseId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_latest_outline(course_id=courseId))


@router.get("/courses/{courseId}/handouts/latest/blocks")
async def get_latest_handout_blocks(
    courseId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_latest_blocks(course_id=courseId))


@router.post("/handout-blocks/{blockId}/generate")
async def generate_handout_block(
    blockId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(
        request,
        service.generate_block(
            block_id=blockId,
            idempotency_key=request.headers.get("Idempotency-Key"),
        ),
    )


@router.get("/handout-blocks/{blockId}/status")
async def get_handout_block_status(
    blockId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_block_status(block_id=blockId))


@router.get("/courses/{courseId}/handouts/current-block")
async def get_current_handout_block(
    courseId: int,
    currentSec: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(
        request,
        service.get_current_block(course_id=courseId, current_sec=currentSec),
    )


@router.get("/handout-blocks/{blockId}/jump-target")
async def get_jump_target(
    blockId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_jump_target(block_id=blockId))
