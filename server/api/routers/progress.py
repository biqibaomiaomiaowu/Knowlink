from fastapi import APIRouter, Depends, Request

from server.api.deps import get_progress_service
from server.api.response import api_ok
from server.domain.services import ProgressService
from server.schemas.requests import LessonProgressData, ProgressData

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


@router.put("/{courseId}/progress")
async def put_progress(
    courseId: int,
    payload: ProgressData,
    request: Request,
    service: ProgressService = Depends(get_progress_service),
):
    return api_ok(request, service.update_progress(course_id=courseId, payload=payload))


@router.get("/{courseId}/lessons/{lessonId}/progress")
async def get_lesson_progress(
    courseId: int,
    lessonId: int,
    request: Request,
    service: ProgressService = Depends(get_progress_service),
):
    return api_ok(request, service.get_lesson_progress(course_id=courseId, lesson_id=lessonId))


@router.put("/{courseId}/lessons/{lessonId}/progress")
async def update_lesson_progress(
    courseId: int,
    lessonId: int,
    payload: LessonProgressData,
    request: Request,
    service: ProgressService = Depends(get_progress_service),
):
    return api_ok(request, service.update_lesson_progress(course_id=courseId, lesson_id=lessonId, payload=payload))
