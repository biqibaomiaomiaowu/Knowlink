from fastapi import APIRouter, Depends, Request, status

from server.api.deps import get_lesson_service
from server.api.response import api_ok
from server.domain.services import LessonService
from server.schemas.requests import (
    CreateLessonRequest,
    MergeLessonsRequest,
    ReorderLessonsRequest,
    SetPrimaryVideoRequest,
    SplitLessonRequest,
    UpdateLessonRequest,
)


router = APIRouter(prefix="/courses", tags=["lessons"])


@router.get("/{courseId}/lessons")
async def list_lessons(
    courseId: int,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.list_lessons(course_id=courseId))


@router.post("/{courseId}/lessons")
async def create_lesson(
    courseId: int,
    payload: CreateLessonRequest,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(
        request,
        service.create_lesson(course_id=courseId, payload=payload),
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/{courseId}/lessons/reorder")
async def reorder_lessons(
    courseId: int,
    payload: ReorderLessonsRequest,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.reorder_lessons(course_id=courseId, payload=payload))


@router.post("/{courseId}/lessons/merge")
async def merge_lessons(
    courseId: int,
    payload: MergeLessonsRequest,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.merge_lessons(course_id=courseId, payload=payload))


@router.get("/{courseId}/lessons/{lessonId}")
async def get_lesson_detail(
    courseId: int,
    lessonId: int,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.get_lesson_detail(course_id=courseId, lesson_id=lessonId))


@router.patch("/{courseId}/lessons/{lessonId}")
async def update_lesson(
    courseId: int,
    lessonId: int,
    payload: UpdateLessonRequest,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.update_lesson(course_id=courseId, lesson_id=lessonId, payload=payload))


@router.delete("/{courseId}/lessons/{lessonId}")
async def delete_lesson(
    courseId: int,
    lessonId: int,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.delete_lesson(course_id=courseId, lesson_id=lessonId))


@router.post("/{courseId}/lessons/{lessonId}/primary-video")
async def set_primary_video(
    courseId: int,
    lessonId: int,
    payload: SetPrimaryVideoRequest,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.set_primary_video(course_id=courseId, lesson_id=lessonId, payload=payload))


@router.post("/{courseId}/lessons/{lessonId}/split")
async def split_lesson(
    courseId: int,
    lessonId: int,
    payload: SplitLessonRequest,
    request: Request,
    service: LessonService = Depends(get_lesson_service),
):
    return api_ok(request, service.split_lesson(course_id=courseId, lesson_id=lessonId, payload=payload))
