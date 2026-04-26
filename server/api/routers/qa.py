from fastapi import APIRouter, Depends, Request

from server.api.deps import get_qa_service
from server.api.response import api_ok
from server.domain.services import QaService
from server.schemas.requests import QaMessageRequest

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/messages")
async def create_qa_message(
    payload: QaMessageRequest,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    data = service.create_message(payload=payload)
    return api_ok(request, data)


@router.get("/sessions/{sessionId}/messages")
async def get_session_messages(
    sessionId: int,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    return api_ok(request, service.get_session_messages(session_id=sessionId))
