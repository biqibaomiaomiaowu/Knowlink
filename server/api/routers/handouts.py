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


@router.get("/courses/{courseId}/handouts/latest/blocks")
async def get_latest_handout_blocks(
    courseId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_latest_blocks(course_id=courseId))


@router.get("/handout-blocks/{blockId}/jump-target")
async def get_jump_target(
    blockId: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_jump_target(block_id=blockId))
