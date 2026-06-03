from __future__ import annotations

from typing import Any

from server.domain.repositories import (
    CourseRepository,
    DashboardRepository,
    LessonProgressRepository,
    LessonRepository,
    ResourceRepository,
    ReviewRepository,
)
from server.domain.services.course_recommendations import CourseRecommendationService


_COURSE_QUICK_ENTRIES = (
    ("course_qa", "课程问答", "placeholder"),
    ("course_graph", "课程图谱", "placeholder"),
    ("comprehensive_quiz", "综合测验", "placeholder"),
    ("course_review", "总复习", "placeholder"),
    ("report", "学习报告", "placeholder"),
    ("export", "导出", "placeholder"),
    ("settings", "设置", "ready"),
)


class HomeService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        reviews: ReviewRepository,
        dashboard: DashboardRepository | None = None,
        lessons: LessonRepository | None = None,
        resources: ResourceRepository | None = None,
        lesson_progress: LessonProgressRepository | None = None,
        recommendations: CourseRecommendationService | None = None,
    ) -> None:
        self.courses = courses
        self.reviews = reviews
        self.dashboard = dashboard
        self.lessons = lessons
        self.resources = resources
        self.lesson_progress = lesson_progress
        self.recommendations = recommendations

    def get_dashboard(self) -> dict[str, object]:
        recent_courses = self.courses.list_recent_courses()[:3]
        top_review_tasks = self._top_review_tasks(recent_courses)
        dashboard = {
            "recentCourses": recent_courses,
            "topReviewTasks": top_review_tasks,
            "recommendationEntryEnabled": True,
            "dailyRecommendedKnowledgePoints": self._daily_recommendations(),
            "learningStats": self._learning_stats(),
        }
        dashboard.update(self._lesson_dashboard_fields())
        return dashboard

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

    def _lesson_dashboard_fields(self) -> dict[str, object]:
        if self.lessons is None or self.lesson_progress is None or self.recommendations is None:
            return {
                "currentCourse": None,
                "currentLesson": None,
                "continueLearning": None,
                "nextStep": None,
                "todayReviewTasks": [],
                "recommendedNextLesson": None,
                "recommendedStageQuiz": None,
                "courseQuickEntries": [],
            }
        current_course = self.courses.get_current_course()
        if current_course is None:
            return {
                "currentCourse": None,
                "currentLesson": None,
                "continueLearning": None,
                "nextStep": None,
                "todayReviewTasks": [],
                "recommendedNextLesson": None,
                "recommendedStageQuiz": None,
                "courseQuickEntries": [],
            }

        course_id = int(current_course["courseId"])
        lessons = [self._merge_lesson_progress(course_id, lesson) for lesson in self.lessons.list_lessons(course_id)]
        current_lesson = self._current_lesson(lessons)
        continue_learning = self._continue_learning(course_id=course_id, lesson=current_lesson)
        return {
            "currentCourse": current_course,
            "currentLesson": current_lesson,
            "continueLearning": continue_learning,
            "nextStep": self._next_step(course_id=course_id, lesson=current_lesson),
            "todayReviewTasks": self._today_review_tasks(course_id=course_id, lessons=lessons),
            "recommendedNextLesson": self.recommendations.recommended_next_lesson(course_id=course_id),
            "recommendedStageQuiz": self.recommendations.recommended_stage_quiz(course_id=course_id),
            "courseQuickEntries": self._course_quick_entries(course_id),
        }

    def _merge_lesson_progress(self, course_id: int, lesson: dict[str, Any]) -> dict[str, Any]:
        if self.lesson_progress is None:
            return lesson
        progress = self.lesson_progress.get_user_lesson_progress(
            course_id=course_id,
            lesson_id=int(lesson["lessonId"]),
        )
        if progress is None:
            return dict(lesson)
        merged = dict(lesson)
        for key in (
            "lastPositionSec",
            "lastHandoutBlockId",
            "handoutReadPercent",
            "quizStatus",
            "reviewStatus",
            "lastActivityAt",
        ):
            if key in progress:
                merged[key] = progress[key]
        return merged

    def _current_lesson(self, lessons: list[dict[str, Any]]) -> dict[str, Any] | None:
        with_activity = [
            lesson
            for lesson in lessons
            if lesson.get("lastActivityAt") is not None and not self._is_lesson_completed(lesson)
        ]
        if with_activity:
            return max(with_activity, key=lambda lesson: (lesson["lastActivityAt"], int(lesson["lessonId"])))
        for lesson in lessons:
            if not self._is_lesson_completed(lesson):
                return lesson
        return lessons[0] if lessons else None

    def _continue_learning(self, *, course_id: int, lesson: dict[str, Any] | None) -> dict[str, Any] | None:
        if lesson is None:
            return None
        position_sec = _int_or_none(lesson.get("lastPositionSec")) or 0
        return {
            "courseId": course_id,
            "lessonId": lesson["lessonId"],
            "lastPositionSec": position_sec,
            "lastHandoutBlockId": lesson.get("lastHandoutBlockId"),
            "nextRoute": f"/courses/{course_id}/lessons/{lesson['lessonId']}",
            "nextAction": {
                "type": "continue_video" if position_sec > 0 else "start_lesson",
                "label": f"继续学习 {lesson['title']}",
                "positionSec": position_sec,
            },
        }

    def _next_step(self, *, course_id: int, lesson: dict[str, Any] | None) -> dict[str, Any] | None:
        if lesson is None:
            return None
        return {
            "type": "continue_lesson",
            "courseId": course_id,
            "lessonId": lesson["lessonId"],
            "title": lesson["title"],
            "nextRoute": f"/courses/{course_id}/lessons/{lesson['lessonId']}",
        }

    def _today_review_tasks(self, *, course_id: int, lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tasks = []
        for lesson in lessons:
            if lesson.get("reviewStatus") != "due":
                continue
            tasks.append(
                {
                    "type": "lesson_review",
                    "courseId": course_id,
                    "lessonId": lesson["lessonId"],
                    "title": lesson["title"],
                    "priorityScore": 80,
                    "reasonText": "本节复习已到期。",
                    "nextRoute": f"/courses/{course_id}/lessons/{lesson['lessonId']}/review",
                }
            )
        return tasks

    def _course_quick_entries(self, course_id: int) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "title": title,
                "status": status,
                "enabled": True,
                "target": f"/courses/{course_id}/{key}",
            }
            for key, title, status in _COURSE_QUICK_ENTRIES
        ]

    def _is_lesson_completed(self, lesson: dict[str, Any]) -> bool:
        return (
            lesson.get("lessonStatus") == "completed"
            or lesson.get("quizStatus") == "completed"
            or lesson.get("handoutReadPercent") == 100
        )


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
