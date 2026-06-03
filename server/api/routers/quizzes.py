from fastapi import APIRouter, Depends, Request

from server.api.deps import get_quiz_service
from server.api.response import api_ok
from server.domain.services import QuizService
from server.schemas.requests import QuizGenerateRequest, StageQuizGenerateRequest, SubmitQuizRequest

router = APIRouter(tags=["quizzes"])


@router.post("/courses/{courseId}/quizzes/generate")
async def generate_quiz(
    courseId: int,
    request: Request,
    payload: QuizGenerateRequest | None = None,
    service: QuizService = Depends(get_quiz_service),
):
    data = service.generate_quiz(
        course_id=courseId,
        question_count_level=payload.question_count_level if payload is not None else "medium",
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return api_ok(request, data)


@router.post("/courses/{courseId}/lessons/{lessonId}/quizzes/generate")
async def generate_lesson_quiz(
    courseId: int,
    lessonId: int,
    request: Request,
    payload: QuizGenerateRequest | None = None,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(
        request,
        service.generate_lesson_quiz(
            course_id=courseId,
            lesson_id=lessonId,
            question_count_level=payload.question_count_level if payload is not None else "medium",
        ),
    )


@router.get("/courses/{courseId}/lessons/{lessonId}/quizzes/current")
async def get_current_lesson_quiz(
    courseId: int,
    lessonId: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.get_current_lesson_quiz(course_id=courseId, lesson_id=lessonId))


@router.post("/courses/{courseId}/quizzes/stage/generate")
async def generate_stage_quiz(
    courseId: int,
    payload: StageQuizGenerateRequest,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.generate_stage_quiz(course_id=courseId, payload=payload))


@router.post("/courses/{courseId}/quizzes/comprehensive/generate")
async def generate_comprehensive_quiz(
    courseId: int,
    request: Request,
    payload: QuizGenerateRequest | None = None,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(
        request,
        service.generate_comprehensive_quiz(
            course_id=courseId,
            question_count_level=payload.question_count_level if payload is not None else "medium",
        ),
    )


@router.get("/courses/{courseId}/subjective-grading/placeholder")
async def get_subjective_grading_placeholder(
    courseId: int,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.subjective_grading_placeholder(course_id=courseId))


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


@router.post("/quizzes/{quizId}/submit")
async def submit_quiz_contract(
    quizId: int,
    payload: SubmitQuizRequest,
    request: Request,
    service: QuizService = Depends(get_quiz_service),
):
    return api_ok(request, service.submit_quiz(quiz_id=quizId, payload=payload))
