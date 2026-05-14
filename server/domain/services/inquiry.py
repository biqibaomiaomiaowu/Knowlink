from __future__ import annotations

from copy import deepcopy
from typing import Any

from server.domain.repositories import CourseRepository, InquiryRepository
from server.domain.services.errors import ServiceError


TIME_BUDGET_MINUTES_MIN = 30
TIME_BUDGET_MINUTES_MAX = 600

INQUIRY_QUESTIONS: list[dict[str, Any]] = [
    {
        "key": "goal_type",
        "label": "当前学习目标",
        "type": "single_select",
        "required": True,
        "options": [
            {"label": "期末复习", "value": "final_review"},
            {"label": "考研冲刺", "value": "exam_sprint"},
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
        "minValue": TIME_BUDGET_MINUTES_MIN,
        "maxValue": TIME_BUDGET_MINUTES_MAX,
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
]


class InquiryService:
    def __init__(self, *, courses: CourseRepository, inquiry: InquiryRepository) -> None:
        self.courses = courses
        self.inquiry = inquiry

    def get_questions(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course_ready(course_id)
        return {
            "version": 1,
            "questions": deepcopy(INQUIRY_QUESTIONS),
        }

    def save_answers(self, *, course_id: int, payload) -> dict[str, object]:
        self._ensure_course_ready(course_id)
        self._validate_answers(payload.answers)
        return self.inquiry.save_inquiry_answers(
            course_id,
            [answer.model_dump(by_alias=True) for answer in payload.answers],
        )

    def _validate_answers(self, answers) -> None:
        questions_by_key = {question["key"]: question for question in INQUIRY_QUESTIONS}
        required_keys = {
            str(question["key"])
            for question in INQUIRY_QUESTIONS
            if question.get("required") is True
        }
        seen_keys: set[str] = set()

        for answer in answers:
            key = answer.key
            if key not in questions_by_key:
                self._raise_invalid_answers()
            if key in seen_keys:
                self._raise_invalid_answers()
            seen_keys.add(key)
            question = questions_by_key[key]
            value = answer.value
            if question["type"] == "single_select":
                allowed_values = {
                    option["value"]
                    for option in question.get("options", [])
                }
                if not isinstance(value, str) or value not in allowed_values:
                    self._raise_invalid_answers()
            elif question["type"] == "number":
                if isinstance(value, bool) or not isinstance(value, int):
                    self._raise_invalid_answers()
                min_value = question.get("minValue")
                max_value = question.get("maxValue")
                if (min_value is not None and value < min_value) or (
                    max_value is not None and value > max_value
                ):
                    self._raise_invalid_answers()

        if required_keys - seen_keys:
            self._raise_invalid_answers()

    def _raise_invalid_answers(self) -> None:
        raise ServiceError(
            message="Inquiry answers are invalid.",
            error_code="inquiry.answers_invalid",
            status_code=422,
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
