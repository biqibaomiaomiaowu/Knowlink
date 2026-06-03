from fastapi import APIRouter, Depends, Request

from server.api.deps import get_review_service
from server.api.response import api_ok
from server.domain.services import ReviewService

router = APIRouter(tags=["reviews"])


@router.get("/courses/{courseId}/review-tasks")
async def get_review_tasks(
    courseId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.list_review_tasks(course_id=courseId))


@router.get("/courses/{courseId}/lessons/{lessonId}/review")
async def get_lesson_review(
    courseId: int,
    lessonId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.get_lesson_review(course_id=courseId, lesson_id=lessonId))


@router.post("/courses/{courseId}/lessons/{lessonId}/review/regenerate")
async def regenerate_lesson_review(
    courseId: int,
    lessonId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.regenerate_lesson_review(course_id=courseId, lesson_id=lessonId))


@router.get("/courses/{courseId}/review")
async def get_course_review(
    courseId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.get_course_review(course_id=courseId))


@router.post("/courses/{courseId}/review/regenerate")
async def regenerate_course_review(
    courseId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.regenerate_course_review(course_id=courseId))


@router.get("/courses/{courseId}/exam-review")
async def get_exam_review(
    courseId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.get_exam_review(course_id=courseId))


@router.post("/courses/{courseId}/review-tasks/regenerate")
async def regenerate_review_tasks(
    courseId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    data = service.regenerate_review_tasks(
        course_id=courseId,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/review-task-runs/{reviewTaskRunId}/status")
async def get_review_run_status(
    reviewTaskRunId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.get_review_run_status(review_task_run_id=reviewTaskRunId))


@router.post("/review-tasks/{reviewTaskId}/complete")
async def complete_review_task(
    reviewTaskId: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.complete_review_task(review_task_id=reviewTaskId))
