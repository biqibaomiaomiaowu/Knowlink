from __future__ import annotations

from server.domain.repositories import CourseRepository, ReviewRepository


class HomeService:
    def __init__(self, *, courses: CourseRepository, reviews: ReviewRepository) -> None:
        self.courses = courses
        self.reviews = reviews

    def get_dashboard(self) -> dict[str, object]:
        recent_courses = self.courses.list_recent_courses()[:3]
        top_review_tasks: list[dict[str, object]] = []
        if recent_courses:
            top_review_tasks = self.reviews.list_review_tasks(recent_courses[0]["courseId"])[:3]
        return {
            "recentCourses": recent_courses,
            "topReviewTasks": top_review_tasks,
            "recommendationEntryEnabled": True,
            "dailyRecommendedKnowledgePoints": [
                {
                    "knowledgePoint": "极限定义",
                    "reason": "高频考点，且最近一次学习停留在该模块。",
                    "targetCourseId": recent_courses[0]["courseId"] if recent_courses else None,
                },
                {
                    "knowledgePoint": "导数几何意义",
                    "reason": "讲义块完成后适合立即回看并练习。",
                    "targetCourseId": recent_courses[0]["courseId"] if recent_courses else None,
                },
            ],
            "learningStats": {
                "streakDays": 3,
                "completedCourses": len(recent_courses),
                "reviewTasksCompleted": len(top_review_tasks),
                "totalLearningMinutes": 95,
            },
        }
