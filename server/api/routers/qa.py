from fastapi import APIRouter, Depends, Request

from server.api.deps import get_qa_service
from server.api.response import api_ok
from server.domain.services import QaService
from server.schemas.requests import QaMessageRequest, ScopedQaMessageRequest

router = APIRouter(tags=["qa"])


@router.post("/qa/messages")
async def create_qa_message(
    payload: QaMessageRequest,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    data = service.create_message(payload=payload)
    return api_ok(request, data)


@router.get("/courses/{courseId}/qa/sessions")
async def list_course_qa_sessions(
    courseId: int,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    return api_ok(request, service.list_course_sessions(course_id=courseId))


@router.post("/courses/{courseId}/qa/messages")
async def create_course_qa_message(
    courseId: int,
    payload: ScopedQaMessageRequest,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    return api_ok(request, service.create_course_message(course_id=courseId, payload=payload))


@router.get("/courses/{courseId}/lessons/{lessonId}/qa/sessions")
async def list_lesson_qa_sessions(
    courseId: int,
    lessonId: int,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    return api_ok(request, service.list_lesson_sessions(course_id=courseId, lesson_id=lessonId))


@router.post("/courses/{courseId}/lessons/{lessonId}/qa/messages")
async def create_lesson_qa_message(
    courseId: int,
    lessonId: int,
    payload: ScopedQaMessageRequest,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    return api_ok(request, service.create_lesson_message(course_id=courseId, lesson_id=lessonId, payload=payload))


@router.get("/qa/sessions/{sessionId}/messages")
async def get_session_messages(
    sessionId: int,
    request: Request,
    service: QaService = Depends(get_qa_service),
):
    return api_ok(request, service.get_session_messages(session_id=sessionId))
