from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from server.api.deps import get_course_service
from server.api.response import api_ok
from server.domain.services import CourseService
from server.schemas.requests import CreateCourseRequest, UpdateCourseRequest

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


@router.get("")
async def list_courses(
    request: Request,
    q: str | None = None,
    learningStatus: str | None = None,
    source: str | None = None,
    archived: Literal["include", "only", "exclude"] = Query(default="exclude"),
    sort: Literal["recent_activity_desc", "created_at_desc", "exam_at_asc", "title_asc"] = Query(
        default="recent_activity_desc"
    ),
    service: CourseService = Depends(get_course_service),
):
    return api_ok(
        request,
        service.list_courses(
            filters={
                "q": q,
                "learningStatus": learningStatus,
                "source": source,
                "archived": archived,
                "sort": sort,
            }
        ),
    )


@router.get("/recent")
async def get_recent_courses(
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.list_recent_courses())


@router.get("/current")
async def get_current_course(
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.get_current_course())


@router.get("/{courseId}")
async def get_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.get_course(course_id=courseId))


@router.patch("/{courseId}")
async def update_course(
    courseId: int,
    payload: UpdateCourseRequest,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.update_course(course_id=courseId, payload=payload))


@router.post("/{courseId}/switch-current")
async def switch_current_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.switch_current_course(course_id=courseId))


@router.get("/{courseId}/delete-impact")
async def get_course_delete_impact(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.get_course_delete_impact(course_id=courseId))


@router.post("/{courseId}/archive")
async def archive_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.archive_course(course_id=courseId))


@router.post("/{courseId}/restore")
async def restore_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.restore_course(course_id=courseId))


@router.delete("/{courseId}")
async def delete_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.delete_course(course_id=courseId))
