from fastapi import APIRouter, Depends, Request

from server.api.deps import get_inquiry_service
from server.api.response import api_ok
from server.domain.services import InquiryService
from server.schemas.requests import InquiryAnswersRequest

router = APIRouter(prefix="/courses", tags=["inquiry"])


@router.get("/{course_id}/inquiry/questions")
async def get_inquiry_questions(
    course_id: int,
    request: Request,
    service: InquiryService = Depends(get_inquiry_service),
):
    return api_ok(request, service.get_questions(course_id=course_id))


@router.post("/{course_id}/inquiry/answers")
async def save_inquiry_answers(
    course_id: int,
    payload: InquiryAnswersRequest,
    request: Request,
    service: InquiryService = Depends(get_inquiry_service),
):
    data = service.save_answers(
        course_id=course_id,
        payload=payload,
    )
    return api_ok(request, data)
