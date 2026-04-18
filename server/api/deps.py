from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.config.settings import Settings, get_settings
from server.domain.services import (
    BilibiliService,
    CourseService,
    HandoutService,
    HomeService,
    InquiryService,
    PipelineService,
    ProgressService,
    QaService,
    QuizService,
    RecommendationFlowService,
    RecommendationService,
    ResourceService,
    ReviewService,
)
from server.infra.auth import DemoUser, authenticate_token
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import runtime_store

security = HTTPBearer(auto_error=False)


async def get_app_settings() -> Settings:
    return get_settings()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_app_settings),
) -> DemoUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Authorization token is missing.",
                "errorCode": "auth.token_missing",
            },
        )
    user = authenticate_token(credentials.credentials, settings)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Authorization token is invalid.",
                "errorCode": "auth.token_invalid",
            },
        )
    request.state.current_user = user
    return user


@lru_cache
def _get_memory_repository() -> MemoryScaffoldRepository:
    return MemoryScaffoldRepository(runtime_store)


@lru_cache
def _get_catalog_service() -> RecommendationService:
    settings = get_settings()
    return RecommendationService(settings.course_catalog_path)


async def get_memory_repository() -> MemoryScaffoldRepository:
    return _get_memory_repository()


async def get_catalog_service() -> RecommendationService:
    return _get_catalog_service()


async def get_course_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> CourseService:
    return CourseService(courses=repo, idempotency=repo)


async def get_bilibili_service() -> BilibiliService:
    return BilibiliService()


async def get_home_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> HomeService:
    return HomeService(courses=repo, reviews=repo)


async def get_recommendation_flow_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
    catalog: RecommendationService = Depends(get_catalog_service),
) -> RecommendationFlowService:
    return RecommendationFlowService(catalog=catalog, courses=repo, idempotency=repo)


async def get_resource_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> ResourceService:
    return ResourceService(courses=repo, resources=repo, idempotency=repo)


async def get_pipeline_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> PipelineService:
    return PipelineService(courses=repo, parse_runs=repo, resources=repo, idempotency=repo)


async def get_inquiry_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> InquiryService:
    return InquiryService(courses=repo, inquiry=repo)


async def get_handout_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> HandoutService:
    return HandoutService(courses=repo, handouts=repo, idempotency=repo)


async def get_qa_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> QaService:
    return QaService(courses=repo, qa=repo)


async def get_quiz_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> QuizService:
    return QuizService(courses=repo, quizzes=repo, idempotency=repo)


async def get_review_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> ReviewService:
    return ReviewService(courses=repo, reviews=repo, idempotency=repo)


async def get_progress_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> ProgressService:
    return ProgressService(courses=repo, progress=repo)
