from fastapi import APIRouter, Depends, Request, status

from server.api.deps import get_resource_service
from server.api.response import api_ok
from server.domain.services import ResourceService
from server.schemas.requests import UploadCompleteRequest, UploadInitRequest

router = APIRouter(prefix="/courses", tags=["resources"])


@router.post("/{courseId}/resources/upload-init")
async def upload_init(
    courseId: int,
    payload: UploadInitRequest,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    host = request.url.hostname or "minio.local"
    return api_ok(request, service.upload_init(course_id=courseId, payload=payload, request_host=host))


@router.post("/{courseId}/resources/upload-complete")
async def upload_complete(
    courseId: int,
    payload: UploadCompleteRequest,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    data = service.upload_complete(
        course_id=courseId,
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data, status_code=status.HTTP_201_CREATED)


@router.get("/{courseId}/resources")
async def list_resources(
    courseId: int,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    return api_ok(request, service.list_resources(course_id=courseId))


@router.delete("/{courseId}/resources/{resourceId}")
async def delete_resource(
    courseId: int,
    resourceId: int,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    return api_ok(request, service.delete_resource(course_id=courseId, resource_id=resourceId))
