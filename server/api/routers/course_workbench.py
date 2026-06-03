from fastapi import APIRouter, Depends, Request

from server.api.deps import get_course_workbench_service
from server.api.response import api_ok
from server.domain.services import CourseWorkbenchService


router = APIRouter(prefix="/courses", tags=["course-workbench"])


@router.get("/{courseId}/workbench")
async def get_course_workbench(
    courseId: int,
    request: Request,
    service: CourseWorkbenchService = Depends(get_course_workbench_service),
):
    return api_ok(request, service.get_course_workbench(course_id=courseId))
