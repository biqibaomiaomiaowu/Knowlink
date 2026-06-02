from __future__ import annotations

from typing import Any

from server.domain.repositories import CourseRepository, LessonProgressRepository, LessonRepository, ResourceRepository
from server.domain.services.errors import ServiceError


_QUICK_ENTRIES = (
    ("course_qa", "课程问答", "placeholder"),
    ("course_graph", "课程图谱", "placeholder"),
    ("comprehensive_quiz", "综合测验", "placeholder"),
    ("course_review", "总复习", "placeholder"),
    ("report", "学习报告", "placeholder"),
    ("export", "导出", "placeholder"),
    ("settings", "设置", "ready"),
)


class CourseWorkbenchService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        lessons: LessonRepository,
        resources: ResourceRepository,
        lesson_progress: LessonProgressRepository,
    ) -> None:
        self.courses = courses
        self.lessons = lessons
        self.resources = resources
        self.lesson_progress = lesson_progress

    def get_course_workbench(self, *, course_id: int) -> dict[str, Any]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )

        lessons = [self._lesson_summary(course_id, lesson) for lesson in self.lessons.list_lessons(course_id)]
        resources = self.resources.list_resources(course_id)
        course_resources = [resource for resource in resources if resource.get("scopeType") == "course"]
        lesson_resources = [resource for resource in resources if resource.get("scopeType") == "lesson"]
        progress = self._progress_summary(
            lessons=lessons,
            resources=resources,
            course_resources=course_resources,
            lesson_resources=lesson_resources,
        )
        current_lesson = self._current_lesson(lessons)
        next_actions = self._next_actions(current_lesson)
        return {
            "course": course,
            "progress": progress,
            "currentLesson": current_lesson,
            "lessons": lessons,
            "courseResources": course_resources,
            "quickEntries": self._quick_entries(course_id),
            "nextActions": next_actions,
            "placeholderStates": self._placeholder_states(),
        }

    def _lesson_summary(self, course_id: int, lesson: dict[str, Any]) -> dict[str, Any]:
        progress = self.lesson_progress.get_user_lesson_progress(
            course_id=course_id,
            lesson_id=int(lesson["lessonId"]),
        )
        if progress is None:
            return lesson
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

    def _progress_summary(
        self,
        *,
        lessons: list[dict[str, Any]],
        resources: list[dict[str, Any]],
        course_resources: list[dict[str, Any]],
        lesson_resources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        completed_lessons = [
            lesson
            for lesson in lessons
            if lesson.get("lessonStatus") == "completed"
            or lesson.get("handoutReadPercent") == 100
            or lesson.get("quizStatus") == "completed"
        ]
        lesson_count = len(lessons)
        mastery_scores = [
            float(lesson["masteryScore"])
            for lesson in lessons
            if lesson.get("masteryScore") is not None
        ]
        pending_review_count = sum(1 for lesson in lessons if lesson.get("reviewStatus") == "due")
        activity_times = [
            lesson.get("lastActivityAt")
            for lesson in lessons
            if lesson.get("lastActivityAt") is not None
        ]
        return {
            "lessonCount": lesson_count,
            "completedLessonCount": len(completed_lessons),
            "resourceCount": len(resources),
            "courseResourceCount": len(course_resources),
            "lessonResourceCount": len(lesson_resources),
            "overallMasteryScore": round(sum(mastery_scores) / len(mastery_scores), 2) if mastery_scores else None,
            "pendingReviewCount": pending_review_count,
            "completionPercent": int(len(completed_lessons) * 100 / lesson_count) if lesson_count else 0,
            "lastActivityAt": max(activity_times) if activity_times else None,
        }

    def _current_lesson(self, lessons: list[dict[str, Any]]) -> dict[str, Any] | None:
        for lesson in lessons:
            if lesson.get("lessonStatus") != "completed":
                return lesson
        return lessons[0] if lessons else None

    def _quick_entries(self, course_id: int) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "title": title,
                "status": status,
                "enabled": True,
                "target": f"/courses/{course_id}/{key}",
            }
            for key, title, status in _QUICK_ENTRIES
        ]

    def _next_actions(self, current_lesson: dict[str, Any] | None) -> list[dict[str, Any]]:
        if current_lesson is None:
            return []
        return [
            {
                "type": "continue_lesson",
                "lessonId": current_lesson["lessonId"],
                "title": current_lesson["title"],
            }
        ]

    def _placeholder_states(self) -> dict[str, dict[str, object]]:
        return {
            "graph": {"status": "placeholder", "canGenerate": False},
            "report": {"status": "placeholder", "canGenerate": False},
            "export": {"status": "placeholder", "canGenerate": False},
        }
