from fastapi import APIRouter, Depends, Request

from server.api.deps import get_progress_service
from server.api.response import api_ok
from server.domain.services import ProgressService
from server.schemas.requests import ProgressData

router = APIRouter(prefix="/courses", tags=["progress"])


@router.get("/{courseId}/progress")
async def get_progress(
    courseId: int,
    request: Request,
    service: ProgressService = Depends(get_progress_service),
):
    return api_ok(request, service.get_progress(course_id=courseId))


@router.post("/{courseId}/progress")
async def update_progress(
    courseId: int,
    payload: ProgressData,
    request: Request,
    service: ProgressService = Depends(get_progress_service),
):
    return api_ok(request, service.update_progress(course_id=courseId, payload=payload))
