from __future__ import annotations

from typing import Any

from server.domain.repositories import CourseRepository, LessonProgressRepository, LessonRepository, ResourceRepository
from server.domain.services.errors import ServiceError


_QUICK_ENTRIES = (
    ("course_qa", "课程问答", "ready", "基于全课程内容提问", "open_course_qa"),
    ("course_graph", "课程图谱", "placeholder", "课程图谱暂未启用", "open_course_graph"),
    ("course_quiz", "课程测试", "ready", "开始课程测试", "start_course_quiz"),
    ("course_review", "总复习", "ready", "进入课程复习中心", "open_course_review"),
    ("report", "学习报告", "placeholder", "学习报告暂未启用", "open_course_report"),
    ("export", "导出", "placeholder", "课程导出暂未启用", "open_course_export"),
    ("settings", "设置", "ready", "调整课程设置", "open_course_settings"),
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
        next_actions = self._next_actions(course_id, current_lesson)
        return {
            "course": course,
            "progress": progress,
            "currentLesson": current_lesson,
            "lessons": lessons,
            "courseResources": course_resources,
            "quickEntries": self._quick_entries(course_id, current_lesson),
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
        completed_lessons = [lesson for lesson in lessons if _is_lesson_completed(lesson)]
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
            if not _is_lesson_completed(lesson):
                return lesson
        return lessons[0] if lessons else None

    def _quick_entries(self, course_id: int, current_lesson: dict[str, Any] | None) -> list[dict[str, Any]]:
        entries = []
        if current_lesson is not None:
            lesson_route = _lesson_handout_route(course_id, int(current_lesson["lessonId"]))
            entries.append(
                {
                    "key": "lesson_study",
                    "title": "课时学习",
                    "status": "ready",
                    "enabled": True,
                    "target": lesson_route,
                    "message": "继续当前课时讲义学习",
                    "route": lesson_route,
                    "action": "open_lesson_study",
                }
            )
        else:
            entries.append(
                {
                    "key": "lesson_study",
                    "title": "课时学习",
                    "status": "placeholder",
                    "enabled": False,
                    "target": None,
                    "message": "创建课时后可进入学习",
                    "route": None,
                    "action": "open_lesson_study",
                }
            )
        entries.extend(
            {
                "key": key,
                "title": title,
                "status": status,
                "enabled": status == "ready",
                "target": _course_quick_entry_route(course_id, key),
                "message": message,
                "route": _course_quick_entry_route(course_id, key),
                "action": action,
            }
            for key, title, status, message, action in _QUICK_ENTRIES
        )
        return entries

    def _next_actions(self, course_id: int, current_lesson: dict[str, Any] | None) -> list[dict[str, Any]]:
        if current_lesson is None:
            return []
        lesson_route = _lesson_handout_route(course_id, int(current_lesson["lessonId"]))
        return [
            {
                "type": "continue_lesson",
                "lessonId": current_lesson["lessonId"],
                "title": current_lesson["title"],
                "route": lesson_route,
                "action": "open_lesson_study",
            }
        ]

    def _placeholder_states(self) -> dict[str, dict[str, object]]:
        return {
            "graph": {"status": "placeholder", "canGenerate": False},
            "report": {"status": "placeholder", "canGenerate": False},
            "export": {"status": "placeholder", "canGenerate": False},
        }


def _lesson_handout_route(course_id: int, lesson_id: int) -> str:
    return f"/courses/{course_id}/lessons/{lesson_id}/handout"


def _is_lesson_completed(lesson: dict[str, Any]) -> bool:
    handout_read_percent = lesson.get("handoutReadPercent")
    return (
        lesson.get("lessonStatus") == "completed"
        or (isinstance(handout_read_percent, (int, float)) and handout_read_percent >= 100)
        or lesson.get("quizStatus") == "completed"
    )


def _course_quick_entry_route(course_id: int, key: str) -> str:
    routes = {
        "course_qa": f"/courses/{course_id}/qa",
        "course_graph": f"/courses/{course_id}/graph",
        "course_quiz": f"/courses/{course_id}/quiz",
        "course_review": f"/courses/{course_id}/review",
        "report": f"/courses/{course_id}/review?kind=report",
        "export": f"/courses/{course_id}/exports",
        "settings": f"/courses/{course_id}/settings",
    }
    return routes[key]
