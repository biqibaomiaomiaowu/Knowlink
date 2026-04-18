from fastapi import APIRouter, Depends, Request

from server.api.deps import get_quiz_service
from server.api.response import api_ok
from server.domain.services import QuizService
from server.schemas.requests import SubmitQuizRequest

router = APIRouter(tags=["quizzes"])


@router.post("/courses/{course_id}/quizzes/generate")
async def generate_quiz(
    course_id: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    data = service.generate_quiz(
        course_id=course_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/quizzes/{quiz_id}")
async def get_quiz(
    quiz_id: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.get_quiz(quiz_id=quiz_id))


@router.get("/quizzes/{quiz_id}/status")
async def get_quiz_status(
    quiz_id: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.get_quiz_status(quiz_id=quiz_id))


@router.post("/quizzes/{quiz_id}/attempts")
async def submit_quiz(
    quiz_id: int,
    payload: SubmitQuizRequest,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.submit_quiz(quiz_id=quiz_id, payload=payload))
