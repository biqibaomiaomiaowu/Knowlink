from fastapi import APIRouter, Depends, Request

from server.api.deps import get_handout_service
from server.api.response import api_ok
from server.domain.services import HandoutService

router = APIRouter(tags=["handouts"])


@router.post("/courses/{course_id}/handouts/generate")
async def generate_handout(
    course_id: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    data = service.generate_handout(
        course_id=course_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/handout-versions/{handout_version_id}/status")
async def get_handout_status(
    handout_version_id: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_status(handout_version_id=handout_version_id))


@router.get("/courses/{course_id}/handouts/latest")
async def get_latest_handout(
    course_id: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_latest_handout(course_id=course_id))


@router.get("/courses/{course_id}/handouts/latest/blocks")
async def get_latest_handout_blocks(
    course_id: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_latest_blocks(course_id=course_id))


@router.get("/handout-blocks/{block_id}/jump-target")
async def get_jump_target(
    block_id: int,
    request: Request,
    service: HandoutService = Depends(get_handout_service),
):
    return api_ok(request, service.get_jump_target(block_id=block_id))
