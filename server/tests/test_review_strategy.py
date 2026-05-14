import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.quiz_strategy import generate_quiz_payload, grade_quiz_attempt
from server.ai.review_strategy import (
    build_mastery_record_updates,
    build_review_task_refs,
    generate_review_tasks,
)


ROOT = Path(__file__).resolve().parents[2]
REVIEW_SCHEMA = json.loads((ROOT / "schemas/ai/review_tasks.schema.json").read_text(encoding="utf-8"))
REVIEW_VALIDATOR = Draft202012Validator(REVIEW_SCHEMA)


def test_mastery_updates_raise_correct_points_and_lower_wrong_points():
    quiz_payload = _generate_quiz_payload()
    attempt = grade_quiz_attempt(
        quiz_payload,
        [
            {"questionKey": quiz_payload["questions"][0]["questionKey"], "selectedOption": "B"},
            {"questionKey": quiz_payload["questions"][1]["questionKey"], "selectedOption": "A"},
            {"questionKey": quiz_payload["questions"][2]["questionKey"], "selectedOption": "A"},
        ],
    )

    updates = build_mastery_record_updates(
        attempt,
        existing_records=[
            {"knowledgePointKey": "kp-limit", "masteryScore": 0.62, "confidenceScore": 0.55},
            {"knowledgePointKey": "kp-continuity", "masteryScore": 0.50, "confidenceScore": 0.42},
        ],
    )

    by_key = {item["knowledgePointKey"]: item for item in updates}
    assert by_key["kp-limit"]["status"] == "needs_review"
    assert by_key["kp-limit"]["nextMasteryScore"] < 0.62
    assert by_key["kp-limit"]["nextConfidenceScore"] < 0.55
    assert by_key["kp-continuity"]["status"] == "improved"
    assert by_key["kp-continuity"]["nextMasteryScore"] > 0.50


def test_generate_review_tasks_returns_top3_traceable_tasks_without_locators():
    quiz_payload = _generate_quiz_payload()
    attempt = grade_quiz_attempt(
        quiz_payload,
        [
            {"questionKey": quiz_payload["questions"][0]["questionKey"], "selectedOption": "B"},
            {"questionKey": quiz_payload["questions"][1]["questionKey"], "selectedOption": "B"},
            {"questionKey": quiz_payload["questions"][2]["questionKey"], "selectedOption": "A"},
        ],
    )

    review_payload = generate_review_tasks(
        attempt,
        quiz_payload=quiz_payload,
        handout_blocks=_handout_blocks(),
    )

    REVIEW_VALIDATOR.validate(review_payload)
    assert 1 <= len(review_payload["tasks"]) <= 3
    assert review_payload["tasks"][0]["taskType"] == "revisit_block"
    assert review_payload["tasks"][0]["sourceQuestionKeys"]
    assert review_payload["tasks"][0]["sourceBlockKey"] == "block-pdf"
    assert review_payload["tasks"][0]["sourceSegmentKeys"] == ["pdf-p2"]
    assert all("pageNo" not in task and "startSec" not in task for task in review_payload["tasks"])


def test_review_tasks_rank_by_final_priority_after_importance_bonus_before_top3():
    quiz_payload = {
        "quizType": "chapter_review",
        "questions": [
            {
                "questionKey": f"q-{key}",
                "questionType": "single_choice",
                "stemMd": f"{key}?",
                "options": ["A", "B", "C", "D"],
                "correctAnswer": "A",
                "explanationMd": "解释",
                "difficultyLevel": "medium",
                "knowledgePointKey": f"kp-{key}",
                "knowledgePointName": f"知识点 {key}",
                "sourceBlockKey": f"block-{key}",
                "sourceSegmentKeys": [f"seg-{key}"],
            }
            for key in ("a", "b", "c", "d")
        ],
    }
    mastery_updates = [
        _mastery_update("kp-a", priority=72),
        _mastery_update("kp-b", priority=71),
        _mastery_update("kp-c", priority=70),
        _mastery_update("kp-d", priority=65),
    ]
    handout_blocks = [
        _block_for_rank("a", importance=60),
        _block_for_rank("b", importance=60),
        _block_for_rank("c", importance=60),
        _block_for_rank("d", importance=95),
    ]

    review_payload = generate_review_tasks(
        {"masteryDelta": []},
        quiz_payload=quiz_payload,
        handout_blocks=handout_blocks,
        mastery_updates=mastery_updates,
    )

    REVIEW_VALIDATOR.validate(review_payload)
    assert [task["knowledgePointKey"] for task in review_payload["tasks"]] == ["kp-d", "kp-a", "kp-b"]
    assert review_payload["tasks"][0]["priorityScore"] == 73


def test_review_tasks_schema_allows_empty_payload_when_no_traceable_evidence():
    review_payload = generate_review_tasks(
        {"masteryDelta": [_mastery_update("kp-missing", priority=90)]},
        quiz_payload={"quizType": "chapter_review", "questions": []},
        handout_blocks=[],
    )

    assert review_payload == {"tasks": []}
    REVIEW_VALIDATOR.validate(review_payload)


def test_review_task_refs_are_written_only_when_source_evidence_can_be_traced():
    quiz_payload = _generate_quiz_payload()
    attempt = grade_quiz_attempt(
        quiz_payload,
        [{"questionKey": question["questionKey"], "selectedOption": "B"} for question in quiz_payload["questions"]],
    )
    review_payload = generate_review_tasks(
        attempt,
        quiz_payload=quiz_payload,
        handout_blocks=_handout_blocks(),
    )

    refs = build_review_task_refs(review_payload, handout_blocks=_handout_blocks(), segments=_segments())

    assert [ref["taskKey"] for ref in refs] == [task["taskKey"] for task in review_payload["tasks"]]
    assert refs[0]["segmentKey"] == "pdf-p2"
    assert refs[0]["pageNo"] == 2
    assert refs[1]["startSec"] == 120
    assert refs[1]["endSec"] == 180

    untraceable_payload = {
        "tasks": [
            {
                **review_payload["tasks"][0],
                "taskKey": "review-missing",
                "sourceBlockKey": "missing-block",
                "sourceSegmentKeys": ["missing-seg"],
            }
        ]
    }
    assert build_review_task_refs(untraceable_payload, handout_blocks=_handout_blocks(), segments=_segments()) == []


class FakeQuizClient:
    def generate_quiz(self, prompt_context):
        _ = prompt_context
        return {
            "quizType": "chapter_review",
            "questions": [
                {
                    "questionKey": "q1-kp-limit",
                    "questionType": "single_choice",
                    "stemMd": "关于极限定义，哪项说法符合当前材料？",
                    "options": ["A. 函数极限描述稳定趋势。", "B. 与当前材料无关。", "C. 不需要理解。", "D. 没有依据。"],
                    "correctAnswer": "A",
                    "explanationMd": "依据 PDF 第 2 页。",
                    "difficultyLevel": "hard",
                    "knowledgePointKey": "kp-limit",
                    "knowledgePointName": "函数极限",
                    "sourceBlockKey": "block-pdf",
                    "sourceSegmentKeys": ["pdf-p2"],
                },
                {
                    "questionKey": "q2-kp-continuity",
                    "questionType": "single_choice",
                    "stemMd": "关于连续性，哪项说法符合当前材料？",
                    "options": ["A. 函数值和极限一致。", "B. 与极限无关。", "C. 只看函数名。", "D. 没有依据。"],
                    "correctAnswer": "A",
                    "explanationMd": "依据视频 02:00-03:00。",
                    "difficultyLevel": "medium",
                    "knowledgePointKey": "kp-continuity",
                    "knowledgePointName": "连续性",
                    "sourceBlockKey": "block-video",
                    "sourceSegmentKeys": ["mp4-c2"],
                },
                {
                    "questionKey": "q3-kp-set",
                    "questionType": "single_choice",
                    "stemMd": "关于集合表示，哪项说法符合当前材料？",
                    "options": ["A. 可用列举法或描述法。", "B. 只能口头说明。", "C. 与材料无关。", "D. 没有依据。"],
                    "correctAnswer": "A",
                    "explanationMd": "依据 PPT 第 6 页。",
                    "difficultyLevel": "easy",
                    "knowledgePointKey": "kp-set",
                    "knowledgePointName": "集合表示",
                    "sourceBlockKey": "block-ppt",
                    "sourceSegmentKeys": ["ppt-s6"],
                },
            ],
        }


def _generate_quiz_payload() -> dict:
    return generate_quiz_payload(_handout_blocks(), segments=_segments(), client=FakeQuizClient())


def _handout_blocks() -> list[dict]:
    return [
        {
            "handoutBlockId": "block-pdf",
            "title": "极限定义",
            "summary": "解释极限的直观定义。",
            "sourceSegmentKeys": ["pdf-p2"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "description": "自变量趋近某点时函数值的稳定趋势。",
                    "difficultyLevel": "advanced",
                    "importanceScore": 95,
                }
            ],
            "citations": [
                {"resourceId": 2, "segmentKey": "pdf-p2", "pageNo": 2, "refLabel": "PDF 第 2 页"}
            ],
        },
        {
            "handoutBlockId": "block-video",
            "title": "连续性的例题",
            "summary": "用例题说明连续性的判断。",
            "sourceSegmentKeys": ["mp4-c2"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-continuity",
                    "displayName": "连续性",
                    "description": "函数在一点连续需要函数值和极限一致。",
                    "difficultyLevel": "intermediate",
                    "importanceScore": 88,
                }
            ],
            "citations": [
                {
                    "resourceId": 1,
                    "segmentKey": "mp4-c2",
                    "startSec": 120,
                    "endSec": 180,
                    "refLabel": "视频 02:00-03:00",
                }
            ],
        },
        {
            "handoutBlockId": "block-ppt",
            "title": "集合表示法",
            "summary": "从列举法到描述法。",
            "sourceSegmentKeys": ["ppt-s6"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-set",
                    "displayName": "集合表示",
                    "description": "集合可以用列举法或描述法表示。",
                    "difficultyLevel": "beginner",
                    "importanceScore": 70,
                }
            ],
            "citations": [
                {"resourceId": 3, "segmentKey": "ppt-s6", "slideNo": 6, "refLabel": "PPT 第 6 页"}
            ],
        },
    ]


def _segments() -> list[dict]:
    return [
        {
            "segmentId": 202,
            "segmentKey": "pdf-p2",
            "resourceId": 2,
            "pageNo": 2,
            "textContent": "函数极限描述的是自变量趋近时函数值的稳定趋势。",
        },
        {
            "segmentId": 102,
            "segmentKey": "mp4-c2",
            "resourceId": 1,
            "startSec": 120,
            "endSec": 180,
            "textContent": "连续性要求函数值和极限保持一致。",
        },
        {
            "segmentId": 306,
            "segmentKey": "ppt-s6",
            "resourceId": 3,
            "slideNo": 6,
            "textContent": "集合可以用列举法或描述法表示。",
        },
    ]


def _mastery_update(knowledge_point_key: str, *, priority: int) -> dict:
    return {
        "knowledgePointKey": knowledge_point_key,
        "knowledgePoint": knowledge_point_key,
        "masteryScoreDelta": -0.1,
        "confidenceDelta": -0.04,
        "nextMasteryScore": 0.55,
        "nextConfidenceScore": 0.40,
        "correctCountDelta": 0,
        "wrongCountDelta": 1,
        "reviewPriority": priority,
        "sourceQuestionKeys": [f"q-{knowledge_point_key.removeprefix('kp-')}"],
        "status": "needs_review",
    }


def _block_for_rank(key: str, *, importance: int) -> dict:
    return {
        "handoutBlockId": f"block-{key}",
        "title": f"知识点 {key}",
        "sourceSegmentKeys": [f"seg-{key}"],
        "knowledgePoints": [
            {
                "knowledgePointKey": f"kp-{key}",
                "displayName": f"知识点 {key}",
                "importanceScore": importance,
            }
        ],
        "citations": [
            {"resourceId": 1, "segmentKey": f"seg-{key}", "pageNo": 1, "refLabel": f"资料 {key}"}
        ],
    }
