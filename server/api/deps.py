from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from server.ai.qa_policy import get_configured_qa_answer_client
from server.config.settings import Settings, get_settings
from server.domain.services import (
    BilibiliService,
    CourseWorkbenchService,
    CourseService,
    HandoutService,
    HomeService,
    InquiryService,
    LessonService,
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
from server.infra.bilibili.client import BiliClient
from server.infra.db.session import create_session
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import runtime_store
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.infra.storage import ObjectStorage, build_object_storage
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
    return build_task_dispatcher(get_settings().task_queue)


@lru_cache
def _get_object_storage() -> ObjectStorage | None:
    return _build_object_storage(get_settings())


@lru_cache
def _get_bili_client() -> BiliClient:
    return BiliClient()


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
    # This backend switch covers the SQL-backed runtime flows as their
    # repositories land. Services still on scaffold memory use get_memory_repository.
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
    if isinstance(async_tasks, InMemoryAsyncTaskRepository) or (
        isinstance(repo, MemoryScaffoldRepository)
        and _supports_async_task_repository(async_tasks)
    ):
        return InMemoryTaskDispatcher(parse_runs=repo, async_tasks=async_tasks)
    return _get_task_dispatcher()


async def get_catalog_service() -> RecommendationService:
    return _get_catalog_service()


async def get_course_service(
    repo=Depends(get_week2_runtime_repository),
) -> CourseService:
    course_repo = getattr(repo, "store", repo)
    return CourseService(courses=course_repo, idempotency=course_repo)


async def get_course_workbench_service(
    repo=Depends(get_week2_runtime_repository),
) -> CourseWorkbenchService:
    course_repo = getattr(repo, "store", repo)
    return CourseWorkbenchService(
        courses=course_repo,
        lessons=course_repo,
        resources=course_repo,
        lesson_progress=course_repo,
    )


async def get_lesson_service(
    repo=Depends(get_week2_runtime_repository),
) -> LessonService:
    course_repo = getattr(repo, "store", repo)
    return LessonService(
        courses=course_repo,
        lessons=course_repo,
        resources=course_repo,
        lesson_progress=course_repo,
        scoped_artifacts=course_repo,
    )


async def get_bilibili_service(
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
    task_dispatcher=Depends(get_task_dispatcher),
) -> BilibiliService:
    lesson_repo = getattr(repo, "store", repo)
    return BilibiliService(
        courses=repo,
        bilibili=repo,
        lessons=lesson_repo,
        async_tasks=async_tasks,
        task_dispatcher=task_dispatcher,
        bili_client=_get_bili_client(),
    )


async def get_home_service(
    repo=Depends(get_week2_runtime_repository),
) -> HomeService:
    return HomeService(courses=repo, reviews=repo, dashboard=repo)


async def get_recommendation_flow_service(
    repo=Depends(get_week2_runtime_repository),
    catalog: RecommendationService = Depends(get_catalog_service),
) -> RecommendationFlowService:
    return RecommendationFlowService(catalog=catalog, courses=repo, idempotency=repo)


async def get_resource_service(
    repo=Depends(get_week2_runtime_repository),
) -> ResourceService:
    lesson_repo = getattr(repo, "store", repo)
    return ResourceService(
        courses=repo,
        resources=repo,
        idempotency=repo,
        lessons=lesson_repo,
        storage=_get_object_storage(),
    )


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
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
    task_dispatcher=Depends(get_task_dispatcher),
) -> HandoutService:
    return HandoutService(
        courses=repo,
        handouts=repo,
        idempotency=repo,
        task_dispatcher=task_dispatcher,
        async_tasks=async_tasks,
    )


async def get_qa_service(
    repo=Depends(get_week2_runtime_repository),
) -> QaService:
    return QaService(courses=repo, qa=repo, qa_answer_client=get_configured_qa_answer_client())


async def get_quiz_service(
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
    task_dispatcher=Depends(get_task_dispatcher),
) -> QuizService:
    return QuizService(
        courses=repo,
        quizzes=repo,
        idempotency=repo,
        task_dispatcher=task_dispatcher,
        async_tasks=async_tasks,
    )


async def get_review_service(
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
    task_dispatcher=Depends(get_task_dispatcher),
) -> ReviewService:
    return ReviewService(
        courses=repo,
        reviews=repo,
        idempotency=repo,
        task_dispatcher=task_dispatcher,
        async_tasks=async_tasks,
    )


async def get_progress_service(
    repo=Depends(get_week2_runtime_repository),
) -> ProgressService:
    return ProgressService(courses=repo, progress=repo)


def _build_object_storage(settings: Settings) -> ObjectStorage | None:
    return build_object_storage(settings)
