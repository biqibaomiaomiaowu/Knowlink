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
from server.infra.db.session import create_session
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import runtime_store
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks import InMemoryAsyncTaskRepository, InMemoryTaskDispatcher, build_task_dispatcher

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
def _get_memory_task_repository() -> InMemoryAsyncTaskRepository:
    return InMemoryAsyncTaskRepository(task_id_factory=_get_memory_repository().next_task_id)


@lru_cache
def _get_task_dispatcher():
    return build_task_dispatcher()


@lru_cache
def _get_catalog_service() -> RecommendationService:
    settings = get_settings()
    return RecommendationService(settings.course_catalog_path)


async def get_memory_repository() -> MemoryScaffoldRepository:
    return _get_memory_repository()


async def get_week2_runtime_repository(
    current_user: DemoUser = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
):
    # This backend switch only covers the Week 2 course/resource/parse/inquiry
    # runtime flow. Home, handout, QA, quiz, review, and progress stay on the
    # scaffold memory repository until their own SQL repositories exist.
    if settings.runtime_repository_backend.lower() != "sql":
        yield _get_memory_repository()
        return

    session = create_session()
    try:
        yield SqlAlchemyRuntimeRepository(session, user_id=current_user.user_id)
    finally:
        session.close()


def _supports_async_task_repository(repo: object) -> bool:
    return all(
        callable(getattr(repo, method_name, None))
        for method_name in (
            "create_async_task",
            "get_async_task",
            "list_async_tasks",
            "update_async_task",
        )
    )


async def get_async_task_repository(
    repo: object = Depends(get_week2_runtime_repository),
):
    if _supports_async_task_repository(repo):
        return repo
    return _get_memory_task_repository()


async def get_task_dispatcher(
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
):
    if isinstance(async_tasks, InMemoryAsyncTaskRepository):
        return InMemoryTaskDispatcher(parse_runs=repo, async_tasks=async_tasks)
    return _get_task_dispatcher()


async def get_catalog_service() -> RecommendationService:
    return _get_catalog_service()


async def get_course_service(
    repo=Depends(get_week2_runtime_repository),
) -> CourseService:
    return CourseService(courses=repo, idempotency=repo)


async def get_bilibili_service() -> BilibiliService:
    return BilibiliService()


async def get_home_service(
    repo: MemoryScaffoldRepository = Depends(get_memory_repository),
) -> HomeService:
    return HomeService(courses=repo, reviews=repo)


async def get_recommendation_flow_service(
    repo=Depends(get_week2_runtime_repository),
    catalog: RecommendationService = Depends(get_catalog_service),
) -> RecommendationFlowService:
    return RecommendationFlowService(catalog=catalog, courses=repo, idempotency=repo)


async def get_resource_service(
    repo=Depends(get_week2_runtime_repository),
) -> ResourceService:
    return ResourceService(courses=repo, resources=repo, idempotency=repo)


async def get_pipeline_service(
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
    task_dispatcher=Depends(get_task_dispatcher),
) -> PipelineService:
    return PipelineService(
        courses=repo,
        parse_runs=repo,
        resources=repo,
        async_tasks=async_tasks,
        task_dispatcher=task_dispatcher,
        idempotency=repo,
    )


async def get_inquiry_service(
    repo=Depends(get_week2_runtime_repository),
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
