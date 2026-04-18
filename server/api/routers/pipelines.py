from fastapi import APIRouter, Depends, Request

from server.api.deps import get_pipeline_service
from server.api.response import api_ok
from server.domain.services import PipelineService

router = APIRouter(tags=["pipelines"])


@router.post("/courses/{course_id}/parse/start")
async def start_parse(
    course_id: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    data = service.start_parse(
        course_id=course_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/parse-runs/{parse_run_id}")
async def get_parse_run(
    parse_run_id: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.get_parse_run(parse_run_id=parse_run_id))


@router.get("/courses/{course_id}/pipeline-status")
async def get_pipeline_status(
    course_id: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.get_pipeline_status(course_id=course_id))


@router.get("/courses/{course_id}/parse/summary")
async def get_parse_summary(
    course_id: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.get_parse_summary(course_id=course_id))


@router.post("/async-tasks/{task_id}/retry")
async def retry_async_task(
    task_id: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.retry_async_task(task_id=task_id))
