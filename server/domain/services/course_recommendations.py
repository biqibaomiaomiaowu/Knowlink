from __future__ import annotations

from typing import Any

from server.domain.repositories import CourseRepository, LessonProgressRepository, LessonRepository, ResourceRepository
from server.domain.services.errors import ServiceError


LOW_MASTERY_THRESHOLD = 0.6
STAGE_QUIZ_COMPLETED_THRESHOLD = 1
SUPPORTING_MATERIAL_ROLES = {"lesson_material", "transcript", "supplement"}


class CourseRecommendationService:
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

    def list_course_next_actions(self, *, course_id: int) -> dict[str, Any]:
        course = self._ensure_course(course_id)
        lessons = self._lesson_summaries(course_id)
        resources = self.resources.list_resources(course_id)
        actions = self._course_actions(course=course, lessons=lessons, resources=resources)
        return {"courseId": course_id, "scopeType": "course", "items": actions}

    def list_lesson_next_actions(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
        course = self._ensure_course(course_id)
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        summary = self._merge_progress(course_id=course_id, lesson=lesson)
        resources = self.resources.list_resources(course_id)
        actions: list[dict[str, Any]] = []
        review = self._lesson_review_action(course=course, lesson=summary)
        if review is not None:
            actions.append(review)
        material = self._lesson_material_action(course=course, lesson=summary, resources=resources)
        if material is not None:
            actions.append(material)
        return {
            "courseId": course_id,
            "scopeType": "lesson",
            "lessonId": lesson_id,
            "items": actions,
        }

    def recommended_next_lesson(self, *, course_id: int) -> dict[str, Any] | None:
        course = self._ensure_course(course_id)
        lessons = self._lesson_summaries(course_id)
        return self._next_lesson_action(course=course, lessons=lessons)

    def recommended_stage_quiz(self, *, course_id: int) -> dict[str, Any] | None:
        course = self._ensure_course(course_id)
        lessons = self._lesson_summaries(course_id)
        return self._stage_quiz_action(course=course, lessons=lessons)

    def _course_actions(
        self,
        *,
        course: dict[str, Any],
        lessons: list[dict[str, Any]],
        resources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        next_lesson = self._next_lesson_action(course=course, lessons=lessons)
        if next_lesson is not None:
            actions.append(next_lesson)
        for lesson in lessons:
            review = self._lesson_review_action(course=course, lesson=lesson)
            if review is not None:
                actions.append(review)
        for lesson in lessons:
            material = self._lesson_material_action(course=course, lesson=lesson, resources=resources)
            if material is not None:
                actions.append(material)
        stage_quiz = self._stage_quiz_action(course=course, lessons=lessons)
        if stage_quiz is not None:
            actions.append(stage_quiz)
        return actions

    def _next_lesson_action(
        self,
        *,
        course: dict[str, Any],
        lessons: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        completed = [lesson for lesson in lessons if self._is_lesson_completed(lesson)]
        if not lessons:
            return None
        if completed:
            last_completed_order = max(int(lesson["orderIndex"]) for lesson in completed)
            candidates = [
                lesson
                for lesson in lessons
                if int(lesson["orderIndex"]) > last_completed_order and not self._is_lesson_completed(lesson)
            ]
        else:
            candidates = [lesson for lesson in lessons if not self._is_lesson_completed(lesson)]
        if not candidates:
            return None
        lesson = min(candidates, key=lambda item: (int(item["orderIndex"]), int(item["lessonId"])))
        return {
            "type": "next_lesson",
            "scopeType": "lesson",
            "courseId": course["courseId"],
            "lessonId": lesson["lessonId"],
            "title": f"继续第 {lesson['orderIndex']} 节：{lesson['title']}",
            "reason": self._reason(course=course, lessons=lessons, weak_lesson=lesson),
            "reasonPlaceholders": self._reason_placeholders(),
            "nextRoute": f"/courses/{course['courseId']}/lessons/{lesson['lessonId']}",
        }

    def _lesson_review_action(
        self,
        *,
        course: dict[str, Any],
        lesson: dict[str, Any],
    ) -> dict[str, Any] | None:
        mastery_score = lesson.get("masteryScore")
        if mastery_score is None or float(mastery_score) >= LOW_MASTERY_THRESHOLD:
            return None
        return {
            "type": "lesson_review",
            "scopeType": "lesson",
            "courseId": course["courseId"],
            "lessonId": lesson["lessonId"],
            "title": f"复习薄弱课时：{lesson['title']}",
            "masteryScore": float(mastery_score),
            "reason": self._reason(course=course, lessons=[lesson], weak_lesson=lesson),
            "reasonPlaceholders": self._reason_placeholders(),
            "nextRoute": f"/courses/{course['courseId']}/lessons/{lesson['lessonId']}/review",
        }

    def _lesson_material_action(
        self,
        *,
        course: dict[str, Any],
        lesson: dict[str, Any],
        resources: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        lesson_resources = [
            resource
            for resource in resources
            if resource.get("scopeType") == "lesson" and resource.get("lessonId") == lesson["lessonId"]
        ]
        has_primary_video = bool(lesson.get("primaryVideoResourceId")) or any(
            resource.get("usageRole") == "primary_video" for resource in lesson_resources
        )
        has_supporting_material = any(
            resource.get("usageRole") in SUPPORTING_MATERIAL_ROLES for resource in lesson_resources
        )
        if not has_primary_video:
            missing = ["primary_video"]
            title = f"补充主视频：{lesson['title']}"
        elif not has_supporting_material:
            missing = ["supporting_material"]
            title = f"补充本节资料：{lesson['title']}"
        else:
            return None
        return {
            "type": "add_lesson_material",
            "scopeType": "lesson",
            "courseId": course["courseId"],
            "lessonId": lesson["lessonId"],
            "title": title,
            "missing": missing,
            "reason": self._reason(course=course, lessons=[lesson], weak_lesson=lesson),
            "reasonPlaceholders": self._reason_placeholders(),
            "nextRoute": f"/courses/{course['courseId']}/lessons/{lesson['lessonId']}/resources",
        }

    def _stage_quiz_action(
        self,
        *,
        course: dict[str, Any],
        lessons: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        completed = [lesson for lesson in lessons if self._is_lesson_completed(lesson)]
        if len(completed) < STAGE_QUIZ_COMPLETED_THRESHOLD:
            return None
        ordered = sorted(completed, key=lambda item: (int(item["orderIndex"]), int(item["lessonId"])))
        return {
            "type": "stage_quiz",
            "scopeType": "lesson_range",
            "courseId": course["courseId"],
            "startLessonId": ordered[0]["lessonId"],
            "endLessonId": ordered[-1]["lessonId"],
            "completedLessonCount": len(completed),
            "title": "生成阶段测验",
            "reason": self._reason(course=course, lessons=lessons, weak_lesson=None),
            "reasonPlaceholders": self._reason_placeholders(),
            "nextRoute": f"/courses/{course['courseId']}/quizzes/stage",
        }

    def _lesson_summaries(self, course_id: int) -> list[dict[str, Any]]:
        return [
            self._merge_progress(course_id=course_id, lesson=lesson)
            for lesson in self.lessons.list_lessons(course_id)
        ]

    def _merge_progress(self, *, course_id: int, lesson: dict[str, Any]) -> dict[str, Any]:
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

    def _ensure_course(self, course_id: int) -> dict[str, Any]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _ensure_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
        lesson = self.lessons.get_lesson(course_id=course_id, lesson_id=lesson_id)
        if lesson is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        return lesson

    def _is_lesson_completed(self, lesson: dict[str, Any]) -> bool:
        return (
            lesson.get("lessonStatus") == "completed"
            or lesson.get("quizStatus") == "completed"
            or lesson.get("handoutReadPercent") == 100
        )

    def _reason(
        self,
        *,
        course: dict[str, Any],
        lessons: list[dict[str, Any]],
        weak_lesson: dict[str, Any] | None,
    ) -> str:
        lesson_count = len(lessons)
        completed_count = sum(1 for lesson in lessons if self._is_lesson_completed(lesson))
        weak_title = weak_lesson["title"] if weak_lesson is not None else "待由图谱细化"
        exam_at = course.get("examAt") or "未设置考试时间"
        return (
            f"当前进度：已完成 {completed_count}/{lesson_count} 节；"
            f"薄弱点占位：{weak_title}；"
            f"考试紧迫度占位：{exam_at}。"
        )

    def _reason_placeholders(self) -> dict[str, str]:
        return {
            "currentProgress": "rule_based",
            "weakPoints": "placeholder",
            "examUrgency": "placeholder",
            "graphDriven": "placeholder",
        }
