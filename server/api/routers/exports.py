from fastapi import APIRouter, Depends, Request

from server.api.deps import get_course_recommendation_service, get_export_service
from server.api.response import api_ok
from server.domain.services import CourseRecommendationService, ExportService
from server.schemas.requests import ExportCreateRequest


router = APIRouter(tags=["exports"])


@router.get("/courses/{courseId}/graph")
async def get_course_graph(
    courseId: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    return api_ok(request, service.get_course_graph(course_id=courseId))


@router.get("/courses/{courseId}/lessons/{lessonId}/graph")
async def get_lesson_graph(
    courseId: int,
    lessonId: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    return api_ok(request, service.get_lesson_graph(course_id=courseId, lesson_id=lessonId))


@router.get("/courses/{courseId}/reports/summary")
async def get_course_report_summary(
    courseId: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    return api_ok(request, service.get_course_report_summary(course_id=courseId))


@router.get("/courses/{courseId}/lessons/{lessonId}/reports/summary")
async def get_lesson_report_summary(
    courseId: int,
    lessonId: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    return api_ok(request, service.get_lesson_report_summary(course_id=courseId, lesson_id=lessonId))


@router.get("/courses/{courseId}/exports")
async def list_exports(
    courseId: int,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    return api_ok(request, service.list_exports(course_id=courseId))


@router.post("/courses/{courseId}/exports")
async def create_export(
    courseId: int,
    payload: ExportCreateRequest,
    request: Request,
    service: ExportService = Depends(get_export_service),
):
    return api_ok(request, service.create_export(course_id=courseId, payload=payload))


@router.get("/courses/{courseId}/recommendations/next-actions")
async def get_course_next_actions(
    courseId: int,
    request: Request,
    service: CourseRecommendationService = Depends(get_course_recommendation_service),
):
    return api_ok(request, service.list_course_next_actions(course_id=courseId))


@router.get("/courses/{courseId}/lessons/{lessonId}/recommendations/next-actions")
async def get_lesson_next_actions(
    courseId: int,
    lessonId: int,
    request: Request,
    service: CourseRecommendationService = Depends(get_course_recommendation_service),
):
    return api_ok(request, service.list_lesson_next_actions(course_id=courseId, lesson_id=lessonId))
