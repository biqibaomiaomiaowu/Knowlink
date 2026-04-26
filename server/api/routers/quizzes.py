from fastapi import APIRouter, Depends, Request

from server.api.deps import get_quiz_service
from server.api.response import api_ok
from server.domain.services import QuizService
from server.schemas.requests import SubmitQuizRequest

router = APIRouter(tags=["quizzes"])


@router.post("/courses/{courseId}/quizzes/generate")
async def generate_quiz(
    courseId: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    data = service.generate_quiz(
        course_id=courseId,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.get("/quizzes/{quizId}")
async def get_quiz(
    quizId: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.get_quiz(quiz_id=quizId))


@router.get("/quizzes/{quizId}/status")
async def get_quiz_status(
    quizId: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.get_quiz_status(quiz_id=quizId))


@router.post("/quizzes/{quizId}/attempts")
async def submit_quiz(
    quizId: int,
    payload: SubmitQuizRequest,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.submit_quiz(quiz_id=quizId, payload=payload))
