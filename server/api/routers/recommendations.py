from fastapi import APIRouter, Depends, Request, status

from server.api.deps import get_recommendation_flow_service
from server.api.response import api_ok
from server.domain.services import RecommendationFlowService
from server.schemas.requests import ConfirmRecommendationRequest, RecommendationRequest

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/courses")
async def recommend_courses(
    payload: RecommendationRequest,
    request: Request,
    flow_service: RecommendationFlowService = Depends(get_recommendation_flow_service),
):
    return api_ok(request, flow_service.recommend(payload=payload))


@router.post("/{catalog_id}/confirm")
async def confirm_recommendation(
    catalog_id: str,
    payload: ConfirmRecommendationRequest,
    request: Request,
    flow_service: RecommendationFlowService = Depends(get_recommendation_flow_service),
):
    data = flow_service.confirm(
        catalog_id=catalog_id,
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data, status_code=status.HTTP_201_CREATED)
