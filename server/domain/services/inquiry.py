from __future__ import annotations

from server.domain.repositories import CourseRepository, InquiryRepository
from server.domain.services.errors import ServiceError


class InquiryService:
    def __init__(self, *, courses: CourseRepository, inquiry: InquiryRepository) -> None:
        self.courses = courses
        self.inquiry = inquiry

    def get_questions(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course_ready(course_id)
        return {
            "version": 1,
            "questions": [
                {
                    "key": "goal_type",
                    "label": "当前学习目标",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"label": "期末复习", "value": "final_review"},
                        {"label": "考研冲刺", "value": "exam_sprint"},
                        {"label": "日常学习", "value": "daily_learning"},
                        {"label": "查漏补缺", "value": "knowledge_gap_fix"},
                    ],
                },
                {
                    "key": "mastery_level",
                    "label": "当前掌握程度",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"label": "零基础", "value": "beginner"},
                        {"label": "基础一般", "value": "intermediate"},
                        {"label": "已经学过，想查漏补缺", "value": "advanced"},
                    ],
                },
                {
                    "key": "time_budget_minutes",
                    "label": "本轮学习时间预算",
                    "type": "number",
                    "required": True,
                    "options": [],
                },
                {
                    "key": "handout_style",
                    "label": "讲义风格偏好",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"label": "考试冲刺", "value": "exam"},
                        {"label": "平衡讲解", "value": "balanced"},
                        {"label": "详细解释", "value": "detailed"},
                    ],
                },
                {
                    "key": "explanation_granularity",
                    "label": "解释粒度",
                    "type": "single_select",
                    "required": True,
                    "options": [
                        {"label": "只看重点", "value": "quick"},
                        {"label": "关键步骤", "value": "balanced"},
                        {"label": "完整推导", "value": "detailed"},
                    ],
                },
            ],
        }

    def save_answers(self, *, course_id: int, payload) -> dict[str, object]:
        self._ensure_course_ready(course_id)
        return self.inquiry.save_inquiry_answers(
            course_id,
            [answer.model_dump(by_alias=True) for answer in payload.answers],
        )

    def _ensure_course_ready(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        if course.get("lifecycleStatus") not in {"inquiry_ready", "learning_ready"}:
            raise ServiceError(
                message="Course is not ready for inquiry.",
                error_code="inquiry.course_not_ready",
                status_code=409,
            )
        return course
