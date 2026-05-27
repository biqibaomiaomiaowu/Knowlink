from __future__ import annotations

from typing import Any

import pytest

from server.domain.services.errors import ServiceError
from server.domain.services.inquiry import InquiryService
from server.schemas.requests import InquiryAnswersRequest


class _InquiryRepo:
    def __init__(self) -> None:
        self.saved_answers: list[dict[str, Any]] | None = None

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        return {"courseId": course_id, "lifecycleStatus": "inquiry_ready"}

    def save_inquiry_answers(
        self,
        course_id: int,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.saved_answers = answers
        return {"saved": True, "answerCount": len(answers)}


def _service(repo: _InquiryRepo | None = None) -> InquiryService:
    inquiry_repo = repo or _InquiryRepo()
    return InquiryService(courses=inquiry_repo, inquiry=inquiry_repo)


def _valid_answers() -> list[dict[str, object]]:
    return [
        {"key": "goal_type", "value": "exam_sprint"},
        {"key": "mastery_level", "value": "intermediate"},
        {"key": "time_budget_minutes", "value": 90},
        {"key": "handout_style", "value": "exam"},
        {"key": "explanation_granularity", "value": "balanced"},
    ]


def test_questions_expose_number_bounds_from_the_shared_definition():
    questions = _service().get_questions(course_id=101)["questions"]
    time_budget = next(item for item in questions if item["key"] == "time_budget_minutes")

    assert time_budget["minValue"] == 30
    assert time_budget["maxValue"] == 600


@pytest.mark.parametrize(
    ("answers", "reason"),
    [
        (_valid_answers() + [{"key": "unexpected", "value": "x"}], "unknown key"),
        (
            _valid_answers() + [{"key": "goal_type", "value": "final_review"}],
            "duplicate key",
        ),
        (
            [answer for answer in _valid_answers() if answer["key"] != "handout_style"],
            "missing required key",
        ),
        (
            [
                answer if answer["key"] != "goal_type" else {"key": "goal_type", "value": "not-an-option"}
                for answer in _valid_answers()
            ],
            "invalid single-select option",
        ),
        (
            [
                answer if answer["key"] != "goal_type" else {"key": "goal_type", "value": ["exam_sprint"]}
                for answer in _valid_answers()
            ],
            "raw list single-select",
        ),
        (
            [
                answer if answer["key"] != "goal_type" else {"key": "goal_type", "value": {"value": "exam_sprint"}}
                for answer in _valid_answers()
            ],
            "raw dict single-select",
        ),
        (
            [
                answer if answer["key"] != "time_budget_minutes" else {"key": "time_budget_minutes", "value": "90"}
                for answer in _valid_answers()
            ],
            "non-integer number",
        ),
        (
            [
                answer if answer["key"] != "time_budget_minutes" else {"key": "time_budget_minutes", "value": 29}
                for answer in _valid_answers()
            ],
            "number below minimum",
        ),
        (
            [
                answer if answer["key"] != "time_budget_minutes" else {"key": "time_budget_minutes", "value": 601}
                for answer in _valid_answers()
            ],
            "number above maximum",
        ),
    ],
)
def test_save_answers_rejects_contract_drift(answers: list[dict[str, object]], reason: str):
    repo = _InquiryRepo()

    with pytest.raises(ServiceError) as exc_info:
        _service(repo).save_answers(
            course_id=101,
            payload=InquiryAnswersRequest(answers=answers),
        )

    assert reason
    assert exc_info.value.error_code == "common.validation_error"
    assert exc_info.value.status_code == 422
    assert repo.saved_answers is None


def test_save_answers_accepts_valid_answers():
    repo = _InquiryRepo()

    result = _service(repo).save_answers(
        course_id=101,
        payload=InquiryAnswersRequest(answers=_valid_answers()),
    )

    assert result == {"saved": True, "answerCount": 5}
    assert repo.saved_answers == _valid_answers()
