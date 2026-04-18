from fastapi import APIRouter, Depends, Request, status

from server.api.deps import get_course_service
from server.api.response import api_ok
from server.domain.services import CourseService
from server.schemas.requests import CreateCourseRequest

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("")
async def create_course(
    payload: CreateCourseRequest,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    data = service.create_course(
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data, status_code=status.HTTP_201_CREATED)


@router.get("/recent")
async def get_recent_courses(
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.list_recent_courses())
