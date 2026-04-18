from fastapi import APIRouter, Depends

from server.api.deps import get_current_user
from server.api.routers import (
    courses,
    handouts,
    health,
    home,
    inquiry,
    pipelines,
    progress,
    qa,
    quizzes,
    recommendations,
    resources,
    reviews,
)


def build_router() -> APIRouter:
    root = APIRouter()
    root.include_router(health.router)

    api_v1 = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])
    api_v1.include_router(home.router)
    api_v1.include_router(recommendations.router)
    api_v1.include_router(courses.router)
    api_v1.include_router(resources.router)
    api_v1.include_router(pipelines.router)
    api_v1.include_router(inquiry.router)
    api_v1.include_router(handouts.router)
    api_v1.include_router(qa.router)
    api_v1.include_router(quizzes.router)
    api_v1.include_router(reviews.router)
    api_v1.include_router(progress.router)
    root.include_router(api_v1)
    return root
