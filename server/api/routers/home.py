from fastapi import APIRouter, Depends, Request

from server.api.deps import get_home_service
from server.api.response import api_ok
from server.domain.services import HomeService

router = APIRouter(tags=["home"])


@router.get("/home/dashboard")
async def get_dashboard(
    request: Request,
    service: HomeService = Depends(get_home_service),
):
    return api_ok(request, service.get_dashboard())
