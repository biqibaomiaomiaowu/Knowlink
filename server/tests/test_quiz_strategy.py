import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.quiz_strategy import build_quiz_question_refs, generate_quiz_payload, grade_quiz_attempt


ROOT = Path(__file__).resolve().parents[2]
QUIZ_SCHEMA = json.loads((ROOT / "schemas/ai/quiz_generation.schema.json").read_text(encoding="utf-8"))
QUIZ_VALIDATOR = Draft202012Validator(QUIZ_SCHEMA)


def test_generate_quiz_payload_uses_current_blocks_kps_and_reverse_lookup_keys():
    payload = generate_quiz_payload(_handout_blocks(), question_count=3)

    QUIZ_VALIDATOR.validate(payload)
    assert payload["quizType"] == "chapter_review"
    assert len(payload["questions"]) == 3
    assert [question["knowledgePointKey"] for question in payload["questions"]] == [
        "kp-limit",
        "kp-continuity",
        "kp-set",
    ]
    assert {question["correctAnswer"] for question in payload["questions"]} == {"A"}
    assert all(question["questionType"] == "single_choice" for question in payload["questions"])
    assert all(len(question["options"]) == 4 for question in payload["questions"])
    assert all("pageNo" not in question and "startSec" not in question for question in payload["questions"])
    assert payload["questions"][0]["sourceSegmentKeys"] == ["pdf-p2"]


def test_quiz_question_refs_are_built_from_block_citations_not_question_locators():
    payload = generate_quiz_payload(_handout_blocks(), question_count=3)

    refs = build_quiz_question_refs(
        payload,
        handout_blocks=_handout_blocks(),
        segments=_segments(),
    )

    assert [ref["questionKey"] for ref in refs] == [question["questionKey"] for question in payload["questions"]]
    assert refs[0] == {
        "questionKey": payload["questions"][0]["questionKey"],
        "resourceId": 2,
        "segmentId": 202,
        "segmentKey": "pdf-p2",
        "refType": "pdf_page",
        "quoteText": "函数极限描述的是自变量趋近时函数值的稳定趋势。",
        "refLabel": "PDF 第 2 页",
        "sortNo": 1,
        "pageNo": 2,
    }
    assert refs[1]["startSec"] == 120
    assert refs[1]["endSec"] == 180
    assert refs[2]["refType"] == "ppt_slide"


def test_grade_quiz_attempt_returns_score_items_and_mastery_delta():
    payload = generate_quiz_payload(_handout_blocks(), question_count=3)

    result = grade_quiz_attempt(
        payload,
        [
            {"questionKey": payload["questions"][0]["questionKey"], "selectedOption": "A"},
            {"questionKey": payload["questions"][1]["questionKey"], "selectedOption": "B"},
            {"questionKey": payload["questions"][2]["questionKey"], "selectedOption": "A"},
        ],
    )

    assert result["score"] == 2
    assert result["totalScore"] == 3
    assert result["accuracy"] == 0.6667
    assert [item["isCorrect"] for item in result["items"]] == [True, False, True]
    assert result["masteryDelta"][0]["knowledgePointKey"] == "kp-limit"
    assert result["masteryDelta"][0]["status"] == "improved"
    assert result["masteryDelta"][1]["knowledgePointKey"] == "kp-continuity"
    assert result["masteryDelta"][1]["status"] == "weakened"
    assert result["recommendedReviewAction"]["type"] == "revisit_block"
    assert result["recommendedReviewAction"]["targetBlockKey"] == "block-video"


def test_grade_quiz_attempt_normalizes_selected_option_text_to_option_key():
    payload = generate_quiz_payload(_handout_blocks(), question_count=3)
    first_question = payload["questions"][0]

    result = grade_quiz_attempt(
        payload,
        [
            {
                "questionKey": first_question["questionKey"],
                "selectedOption": first_question["options"][0],
            }
        ],
    )

    assert result["items"][0]["selectedOption"] == "A"
    assert result["items"][0]["isCorrect"] is True


def test_grade_quiz_attempt_does_not_persist_unmatched_long_option_text():
    payload = generate_quiz_payload(_handout_blocks(), question_count=3)

    result = grade_quiz_attempt(
        payload,
        [
            {
                "questionKey": payload["questions"][0]["questionKey"],
                "selectedOption": "这是一段无法匹配任何选项的超长中文答案文本，不能写入短选项字段",
            }
        ],
    )

    assert result["items"][0]["selectedOption"] == ""
    assert result["items"][0]["isCorrect"] is False


def test_grade_quiz_attempt_accepts_api_question_id_answers_without_dto_change():
    payload = generate_quiz_payload(_handout_blocks(), question_count=3)
    persisted_payload = {
        **payload,
        "questions": [
            {**question, "questionId": question_id}
            for question, question_id in zip(payload["questions"], (8101, 8102, 8103), strict=True)
        ],
    }

    result = grade_quiz_attempt(
        persisted_payload,
        [
            {"questionId": 8101, "selectedOption": "A"},
            {"questionId": 8102, "selectedOption": "A"},
            {"questionId": 8103, "selectedOption": "A"},
        ],
    )

    assert result["score"] == 3
    assert result["accuracy"] == 1.0
    assert all(item["isCorrect"] for item in result["items"])


def test_quiz_question_refs_use_generated_fallback_block_key_consistently():
    blocks = [
        {
            "title": "缺少外部 block id 的讲义块",
            "summary": "仍应能通过 block-1 反查引用。",
            "sourceSegmentKeys": ["pdf-p2"],
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "description": "自变量趋近某点时函数值的稳定趋势。",
                    "importanceScore": 90,
                }
            ],
            "citations": [
                {"resourceId": 2, "segmentKey": "pdf-p2", "pageNo": 2, "refLabel": "PDF 第 2 页"}
            ],
        }
    ]
    payload = generate_quiz_payload(blocks, question_count=3)

    refs = build_quiz_question_refs(payload, handout_blocks=blocks, segments=_segments())

    assert payload["questions"][0]["sourceBlockKey"] == "block-1"
    assert refs[0]["questionKey"] == payload["questions"][0]["questionKey"]
    assert refs[0]["segmentKey"] == "pdf-p2"


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
