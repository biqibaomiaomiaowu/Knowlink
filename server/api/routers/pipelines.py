from fastapi import APIRouter, Depends, Request

from server.api.deps import get_pipeline_service
from server.api.response import api_ok
from server.domain.services import PipelineService

router = APIRouter(tags=["pipelines"])


@router.post("/courses/{courseId}/parse/start")
async def start_parse(
    courseId: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    data = service.start_parse(
        course_id=courseId,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/parse-runs/{parseRunId}")
async def get_parse_run(
    parseRunId: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.get_parse_run(parse_run_id=parseRunId))


@router.get("/courses/{courseId}/pipeline-status")
async def get_pipeline_status(
    courseId: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.get_pipeline_status(course_id=courseId))


@router.get("/courses/{courseId}/parse/summary")
async def get_parse_summary(
    courseId: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.get_parse_summary(course_id=courseId))


@router.post("/async-tasks/{taskId}/retry")
async def retry_async_task(
    taskId: int,
    request: Request,
    service: PipelineService = Depends(get_pipeline_service),
):
    return api_ok(request, service.retry_async_task(task_id=taskId))
