from fastapi import APIRouter, Depends, Request

from server.api.deps import get_review_service
from server.api.response import api_ok
from server.domain.services import ReviewService

router = APIRouter(tags=["reviews"])


@router.get("/courses/{course_id}/review-tasks")
async def get_review_tasks(
    course_id: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.list_review_tasks(course_id=course_id))


@router.post("/courses/{course_id}/review-tasks/regenerate")
async def regenerate_review_tasks(
    course_id: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    data = service.regenerate_review_tasks(
        course_id=course_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/review-task-runs/{review_task_run_id}/status")
async def get_review_run_status(
    review_task_run_id: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.get_review_run_status(review_task_run_id=review_task_run_id))


@router.post("/review-tasks/{review_task_id}/complete")
async def complete_review_task(
    review_task_id: int,
    request: Request,
    service: ReviewService = Depends(get_review_service),
):
    return api_ok(request, service.complete_review_task(review_task_id=review_task_id))
