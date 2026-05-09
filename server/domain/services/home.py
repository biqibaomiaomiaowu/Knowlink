from __future__ import annotations

from server.domain.repositories import CourseRepository, DashboardRepository, ReviewRepository


class HomeService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        reviews: ReviewRepository,
        dashboard: DashboardRepository | None = None,
    ) -> None:
        self.courses = courses
        self.reviews = reviews
        self.dashboard = dashboard

    def get_dashboard(self) -> dict[str, object]:
        recent_courses = self.courses.list_recent_courses()[:3]
        top_review_tasks = self._top_review_tasks(recent_courses)
        return {
            "recentCourses": recent_courses,
            "topReviewTasks": top_review_tasks,
            "recommendationEntryEnabled": True,
            "dailyRecommendedKnowledgePoints": self._daily_recommendations(),
            "learningStats": self._learning_stats(),
        }

    def _top_review_tasks(self, recent_courses: list[dict[str, object]]) -> list[dict[str, object]]:
        tasks: list[dict[str, object]] = []
        for course in recent_courses:
            course_id = course.get("courseId")
            if isinstance(course_id, int):
                tasks.extend(self.reviews.list_review_tasks(course_id))
        tasks.sort(
            key=lambda task: (
                -_int_value(task.get("priorityScore")),
                _int_value(task.get("reviewOrder")),
                _int_value(task.get("reviewTaskId")),
            )
        )
        return tasks[:3]

    def _daily_recommendations(self) -> list[dict[str, object]]:
        if self.dashboard is None:
            return []
        return self.dashboard.list_daily_recommended_knowledge_points(limit=3)

    def _learning_stats(self) -> dict[str, object]:
        if self.dashboard is None:
            return {
                "streakDays": 0,
                "completedCourses": 0,
                "reviewTasksCompleted": 0,
                "totalLearningMinutes": 0,
            }
        return self.dashboard.get_learning_stats()


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
