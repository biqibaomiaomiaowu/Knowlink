from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from server.domain.repositories import CourseRepository, IdempotencyRepository
from server.domain.services.errors import ServiceError
from server.schemas.common import ResourceManifestItem
from server.schemas.responses import RecommendationCard
from server.schemas.requests import ConfirmRecommendationRequest, RecommendationRequest


class RecommendationService:
    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path

    @lru_cache(maxsize=1)
    def load_catalog(self) -> list[dict]:
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def get_catalog_entry(self, catalog_id: str) -> dict | None:
        for item in self.load_catalog():
            if item["catalogId"] == catalog_id:
                return item
        return None

    def recommend(self, payload: RecommendationRequest) -> list[RecommendationCard]:
        results: list[RecommendationCard] = []
        goal_text = payload.goal_text.lower()
        time_budget_hours = payload.time_budget_minutes / 60

        for item in self.load_catalog():
            score = 50
            reasons: list[str] = []

            if payload.self_level == item["level"]:
                score += 20
                reasons.append("难度与当前基础匹配")
            elif payload.self_level == "intermediate" and item["level"] in {"beginner", "advanced"}:
                score += 10
                reasons.append("难度可控，适合作为过渡课程")

            if time_budget_hours >= item["estimatedHours"]:
                score += 15
                reasons.append("时长可在当前预算内完成")
            else:
                score += max(0, 15 - int((item["estimatedHours"] - time_budget_hours) * 5))
                reasons.append("需要拆分学习节奏，但仍可安排")

            if any(tag.lower() in goal_text for tag in item["tags"]):
                score += 20
                reasons.append("目标关键词与课程主题高度一致")

            if payload.preferred_style in item["supportedStyles"]:
                score += 5
                reasons.append("讲义风格与当前偏好一致")

            results.append(
                RecommendationCard(
                    catalog_id=item["catalogId"],
                    title=item["title"],
                    provider=item["provider"],
                    level=item["level"],
                    estimated_hours=item["estimatedHours"],
                    fit_score=min(score, 100),
                    reasons=reasons[:3],
                    default_resource_manifest=[
                        ResourceManifestItem(**resource)
                        for resource in item["defaultResourceManifest"]
                    ],
                )
            )

        return sorted(results, key=lambda result: result.fit_score, reverse=True)


class RecommendationFlowService:
    def __init__(
        self,
        *,
        catalog: RecommendationService,
        courses: CourseRepository,
        idempotency: IdempotencyRepository,
    ) -> None:
        self.catalog = catalog
        self.courses = courses
        self.idempotency = idempotency

    def recommend(self, *, payload: RecommendationRequest) -> dict[str, object]:
        recommendations = self.catalog.recommend(payload)
        if not recommendations:
            raise ServiceError(
                message="No course recommendation matched the current filters.",
                error_code="recommendation.no_match",
                status_code=404,
            )
        return {
            "recommendations": [
                item.model_dump(by_alias=True) for item in recommendations
            ],
            "requestEcho": payload.model_dump(by_alias=True),
        }

    def confirm(
        self,
        *,
        catalog_id: str,
        payload: ConfirmRecommendationRequest,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        catalog = self.catalog.get_catalog_entry(catalog_id)
        if catalog is None:
            raise ServiceError(
                message="The requested catalog entry does not exist.",
                error_code="recommendation.catalog_not_found",
                status_code=404,
            )

        def factory() -> dict[str, object]:
            course = self.courses.create_course(
                title=payload.title_override or catalog["title"],
                entry_type="recommendation",
                goal_text=payload.goal_text,
                preferred_style=payload.preferred_style,
                catalog_id=catalog_id,
            )
            return {
                "course": course,
                "createdFromCatalogId": catalog_id,
            }

        return self.idempotency.run_idempotent(
            "recommendation.confirm",
            idempotency_key,
            factory,
        )
