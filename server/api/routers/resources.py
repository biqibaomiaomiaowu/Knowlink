from fastapi import APIRouter, Depends, Request, status

from server.api.deps import get_resource_service
from server.api.response import api_ok
from server.domain.services import ResourceService
from server.schemas.requests import UploadCompleteRequest, UploadInitRequest

router = APIRouter(prefix="/courses", tags=["resources"])


@router.post("/{course_id}/resources/upload-init")
async def upload_init(
    course_id: int,
    payload: UploadInitRequest,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    host = request.url.hostname or "minio.local"
    return api_ok(request, service.upload_init(course_id=course_id, payload=payload, request_host=host))


@router.post("/{course_id}/resources/upload-complete")
async def upload_complete(
    course_id: int,
    payload: UploadCompleteRequest,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    data = service.upload_complete(
        course_id=course_id,
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data, status_code=status.HTTP_201_CREATED)


@router.get("/{course_id}/resources")
async def list_resources(
    course_id: int,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    return api_ok(request, service.list_resources(course_id=course_id))


@router.delete("/{course_id}/resources/{resource_id}")
async def delete_resource(
    course_id: int,
    resource_id: int,
    request: Request,
    service: ResourceService = Depends(get_resource_service),
):
    return api_ok(request, service.delete_resource(course_id=course_id, resource_id=resource_id))
