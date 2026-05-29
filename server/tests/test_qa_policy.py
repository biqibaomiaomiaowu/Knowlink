import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.core.errors import AIOutputParseError, AIProviderError
from server.ai.core.types import AIModelResult
from server.ai.qa_policy import (
    DeepSeekQaAnswerClient,
    VivoQaAnswerClient,
    build_qa_message_refs,
    build_block_scoped_qa_candidates,
    generate_block_qa_response,
    get_configured_qa_answer_client,
    normalize_qa_answer_with_refs,
)


ROOT = Path(__file__).resolve().parents[2]
QA_RESPONSE_SCHEMA = json.loads((ROOT / "schemas/ai/qa_response.schema.json").read_text(encoding="utf-8"))
QA_RESPONSE_VALIDATOR = Draft202012Validator(QA_RESPONSE_SCHEMA)


class FakeAIService:
    def __init__(self, payload: dict | None = None, error: BaseException | None = None):
        self.payload = payload if payload is not None else {}
        self.error = error
        self.requests = []

    def complete_json(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return AIModelResult(text=json.dumps(self.payload, ensure_ascii=False), parsed_json=self.payload)


class FakeUnreferencedAnswerClient:
    def __init__(self, payload: dict | None = None, error: BaseException | None = None):
        self.payload = payload if payload is not None else {}
        self.error = error
        self.unreferenced_requests = []

    def generate_answer(self, question, candidates):
        raise AssertionError("citation-backed QA path should not be used")

    def generate_unreferenced_answer(self, question, *, context_text, evidence_tier, course_scope=None):
        self.unreferenced_requests.append(
            {
                "question": question,
                "contextText": context_text,
                "evidenceTier": evidence_tier,
                "courseScope": course_scope,
            }
        )
        if self.error is not None:
            raise self.error
        return self.payload


def test_block_scoped_qa_prioritizes_current_block_refs_before_other_evidence():
    candidates = build_block_scoped_qa_candidates(
        "集合的定义是什么？",
        current_block=_current_block(),
        segments=_segments(),
        knowledge_point_evidences=[{"knowledgePointKey": "kp-set", "segmentKey": "pdf-p1"}],
        adjacent_blocks=[_adjacent_block()],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert [candidate.source for candidate in candidates[:4]] == [
        "current_block_ref",
        "knowledge_point_evidence",
        "adjacent_block",
        "course_document_segment",
    ]

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block=_current_block(),
        segments=_segments(),
        knowledge_point_evidences=[{"knowledgePointKey": "kp-set", "segmentKey": "pdf-p1"}],
        adjacent_blocks=[_adjacent_block()],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["generationMetadata"] == {
        "source": "fallback",
        "reason": "model_unavailable",
        "evidenceTier": "original_evidence",
    }
    assert response["citations"] == [{"resourceId": 1, "refLabel": "视频 00s-20s", "startSec": 0, "endSec": 20}]


def test_block_scoped_qa_expands_to_adjacent_block_before_course_documents():
    response = generate_block_qa_response(
        "集合和例题有什么联系？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        adjacent_blocks=[_adjacent_block()],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["citations"][0]["resourceId"] == 2
    assert response["citations"][0]["pageNo"] == 2
    assert "相邻讲义块" in response["answerMd"]


def test_block_scoped_qa_refuses_when_no_candidate_evidence_exists():
    response = generate_block_qa_response(
        "课程外的问题？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "insufficient_evidence"
    assert response["citations"] == []


def test_qa_uses_handout_context_when_original_evidence_is_missing():
    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["citations"] == []
    assert response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert response["generationMetadata"]["handoutContext"]["title"] == "集合的定义"
    assert "依据讲义内容回答" in response["answerMd"]
    assert "集合是确定对象组成的整体" in response["answerMd"]


def test_qa_uses_title_summary_handout_context_when_content_is_empty():
    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "",
            "summary": "集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert response["answerType"] == "direct_answer"
    assert response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert "集合是确定对象组成的整体" in response["answerMd"]


def test_qa_uses_unreferenced_model_for_handout_context_and_drops_citations():
    client = FakeUnreferencedAnswerClient(
        {
            "answerMd": "讲义说明集合是确定对象组成的整体。",
            "answerType": "direct_answer",
            "citations": [{"resourceId": 999, "pageNo": 1, "refLabel": "伪引用"}],
        }
    )

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerMd"].startswith("依据讲义内容回答，未找到可追溯原始资料引用。\n\n")
    assert "讲义说明集合是确定对象组成的整体。" in response["answerMd"]
    assert "依据讲义内容回答" in response["answerMd"]
    assert "未找到可追溯原始资料引用" in response["answerMd"]
    assert response["citations"] == []
    assert response["generationMetadata"]["source"] == "model"
    assert response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert response["generationMetadata"]["handoutContext"]["title"] == "集合的定义"
    assert client.unreferenced_requests[0]["evidenceTier"] == "handout_context"
    assert "集合是确定对象组成的整体" in client.unreferenced_requests[0]["contextText"]


def test_qa_unreferenced_model_keeps_existing_handout_context_disclosure_once():
    answer_md = "依据讲义内容回答，未找到可追溯原始资料引用。\n\n讲义说明集合是确定对象组成的整体。"
    client = FakeUnreferencedAnswerClient(
        {
            "answerMd": answer_md,
            "answerType": "direct_answer",
            "citations": [],
        }
    )

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerMd"] == answer_md.replace("\n\n", "\n")
    assert response["answerMd"].count("依据讲义内容回答") == 1


def test_qa_answers_course_related_question_without_direct_evidence():
    response = generate_block_qa_response(
        "空集为什么也是集合？",
        current_block={
            **_current_block(),
            "title": "",
            "summary": "",
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "集合论入门",
            "goalText": "理解集合、空集、元素和子集。",
            "handoutTitles": ["集合的定义"],
            "knowledgePointNames": ["集合", "空集"],
        },
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["citations"] == []
    assert response["generationMetadata"]["evidenceTier"] == "course_prior"
    assert "基于当前课程主题的补充解释" in response["answerMd"]
    assert "空集" in response["answerMd"]


def test_qa_uses_unreferenced_model_for_course_prior_and_drops_citations():
    course_scope = {
        "title": "集合论入门",
        "goalText": "理解集合、空集、元素和子集。",
        "handoutTitles": ["集合的定义"],
        "knowledgePointNames": ["集合", "空集"],
    }
    client = FakeUnreferencedAnswerClient(
        {
            "answer_md": "空集没有元素，但仍然满足集合的定义。",
            "answer_type": "direct_answer",
            "citations": [{"resourceId": 999, "pageNo": 1, "refLabel": "伪引用"}],
        }
    )

    response = generate_block_qa_response(
        "空集为什么也是集合？",
        current_block={
            **_current_block(),
            "title": "",
            "summary": "",
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope=course_scope,
        client=client,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerMd"].startswith("课程资料和讲义中未找到直接证据，以下是基于当前课程主题的补充解释。\n\n")
    assert "空集没有元素，但仍然满足集合的定义。" in response["answerMd"]
    assert "基于当前课程主题的补充解释" in response["answerMd"]
    assert response["citations"] == []
    assert response["generationMetadata"]["source"] == "model"
    assert response["generationMetadata"]["evidenceTier"] == "course_prior"
    assert client.unreferenced_requests[0]["evidenceTier"] == "course_prior"
    assert client.unreferenced_requests[0]["courseScope"] == course_scope


def test_qa_unreferenced_model_keeps_existing_course_prior_disclosure_once():
    course_scope = {
        "title": "集合论入门",
        "goalText": "理解集合、空集、元素和子集。",
        "handoutTitles": ["集合的定义"],
        "knowledgePointNames": ["集合", "空集"],
    }
    answer_md = "课程资料和讲义中未找到直接证据，以下是基于当前课程主题的补充解释。\n\n空集没有元素，但仍然满足集合的定义。"
    client = FakeUnreferencedAnswerClient(
        {
            "answerMd": answer_md,
            "answerType": "direct_answer",
            "citations": [],
        }
    )

    response = generate_block_qa_response(
        "空集为什么也是集合？",
        current_block={
            **_current_block(),
            "title": "",
            "summary": "",
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope=course_scope,
        client=client,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerMd"] == answer_md.replace("\n\n", "\n")
    assert response["answerMd"].count("基于当前课程主题的补充解释") == 1


def test_qa_unreferenced_model_error_falls_back_to_handout_context():
    client = FakeUnreferencedAnswerClient(error=AIOutputParseError("empty answer"))

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["citations"] == []
    assert response["generationMetadata"] == {
        "source": "fallback",
        "reason": "model_output_invalid",
        "evidenceTier": "handout_context",
        "handoutContext": {"handoutBlockId": 4001, "outlineKey": "outline-1", "title": "集合的定义"},
    }


def test_qa_rejects_out_of_scope_question_without_direct_evidence():
    response = generate_block_qa_response(
        "今天杭州天气怎么样？",
        current_block={**_current_block(), "citations": [], "sourceSegmentKeys": [], "knowledgePoints": [], "contentMd": ""},
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "集合论入门",
            "goalText": "理解集合、空集、元素和子集。",
            "handoutTitles": ["集合的定义"],
            "knowledgePointNames": ["集合", "空集"],
        },
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "clarification"
    assert response["citations"] == []
    assert response["generationMetadata"]["evidenceTier"] == "out_of_scope"


def test_qa_does_not_reject_domain_term_when_it_is_in_course_scope():
    response = generate_block_qa_response(
        "天气预报为什么会变化？",
        current_block={**_current_block(), "citations": [], "sourceSegmentKeys": [], "knowledgePoints": [], "contentMd": ""},
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "气象学入门",
            "goalText": "理解气象观测、气压、降水和预报。",
            "knowledgePointNames": ["气象", "气压", "降水"],
        },
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["citations"] == []
    assert response["generationMetadata"]["evidenceTier"] == "course_prior"


def test_qa_rejects_mixed_course_keyword_out_of_scope_question():
    response = generate_block_qa_response(
        "集合今天杭州天气怎么样？",
        current_block={
            **_current_block(),
            "title": "",
            "summary": "",
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "集合论入门",
            "goalText": "理解集合、空集、元素和子集。",
            "knowledgePointNames": ["集合", "空集"],
        },
    )

    assert response["answerType"] == "clarification"
    assert response["citations"] == []
    assert response["generationMetadata"]["evidenceTier"] == "out_of_scope"


def test_qa_rejects_out_of_scope_before_handout_context_when_no_original_evidence():
    response = generate_block_qa_response(
        "集合今天杭州天气怎么样？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "## 集合的定义\n\n集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "集合论入门",
            "goalText": "理解集合、空集、元素和子集。",
            "knowledgePointNames": ["集合", "空集"],
        },
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "clarification"
    assert response["citations"] == []
    assert response["generationMetadata"]["evidenceTier"] == "out_of_scope"


def test_qa_keeps_original_evidence_before_out_of_scope_terms():
    response = generate_block_qa_response(
        "集合今天杭州天气怎么样？",
        current_block=_current_block(),
        segments=_segments(),
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "集合论入门",
            "goalText": "理解集合、空集、元素和子集。",
            "knowledgePointNames": ["集合", "空集"],
        },
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["generationMetadata"]["evidenceTier"] == "original_evidence"
    assert response["citations"] == [{"resourceId": 1, "refLabel": "\u89c6\u9891 00s-20s", "startSec": 0, "endSec": 20}]


def test_qa_keeps_original_evidence_before_stock_and_news_terms():
    for question in [
        "\u96c6\u5408\u80a1\u7968\u8d70\u52bf\u600e\u4e48\u770b\uff1f",
        "\u96c6\u5408\u65b0\u95fb\u70ed\u641c\u662f\u4ec0\u4e48\uff1f",
    ]:
        response = generate_block_qa_response(
            question,
            current_block=_current_block(),
            segments=_segments(),
            knowledge_point_evidences=[],
            adjacent_blocks=[],
            active_course_id=101,
            active_parse_run_id=9001,
            active_handout_version_id=7001,
            course_scope={
                "title": "set theory basics",
                "goalText": "learn empty sets, subsets, and set operations",
                "knowledgePointNames": ["set", "empty set"],
            },
        )

        QA_RESPONSE_VALIDATOR.validate(response)
        assert response["answerType"] == "direct_answer"
        assert response["generationMetadata"]["evidenceTier"] == "original_evidence"
        assert response["citations"] == [{"resourceId": 1, "refLabel": "\u89c6\u9891 00s-20s", "startSec": 0, "endSec": 20}]


def test_qa_keeps_legacy_insufficient_evidence_for_out_of_scope_without_course_scope():
    response = generate_block_qa_response(
        "今天杭州天气怎么样？",
        current_block={**_current_block(), "citations": [], "sourceSegmentKeys": [], "knowledgePoints": [], "contentMd": ""},
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "insufficient_evidence"
    assert response["citations"] == []


def test_qa_does_not_reject_course_question_with_generic_time_word():
    response = generate_block_qa_response(
        "今天集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "sourceSegmentKeys": [],
            "knowledgePoints": [],
            "contentMd": "",
            "title": "集合的定义",
            "summary": "集合是确定对象组成的整体。",
        },
        segments=[],
        knowledge_point_evidences=[],
        adjacent_blocks=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        course_scope={
            "title": "集合论入门",
            "goalText": "理解集合、空集、元素和子集。",
            "knowledgePointNames": ["集合", "空集"],
        },
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert response["citations"] == []


def test_block_scoped_qa_refuses_when_candidates_do_not_support_question():
    response = generate_block_qa_response(
        "量子隧穿效应如何证明？",
        current_block=_current_block(),
        segments=_segments(),
        knowledge_point_evidences=[{"knowledgePointKey": "kp-set", "segmentKey": "pdf-p1"}],
        adjacent_blocks=[_adjacent_block()],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "insufficient_evidence"
    assert response["citations"] == []


def test_block_citation_requires_active_segment_reverse_lookup():
    candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={
            **_current_block(),
            "citations": [
                {"resourceId": 1, "segmentKey": "missing-mp4", "startSec": 0, "endSec": 20, "refLabel": "missing"}
            ],
            "knowledgePoints": [],
        },
        segments=[],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert candidates == []


def test_block_citation_locator_is_normalized_from_reverse_lookup_segment():
    candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={
            **_current_block(),
            "citations": [{"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 99, "refLabel": "bad-page"}],
            "knowledgePoints": [],
        },
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert candidates[0].to_qa_citation() == {"resourceId": 2, "refLabel": "bad-page", "pageNo": 1}


def test_video_only_block_uses_source_segment_keys_when_citations_are_missing():
    candidates = build_block_scoped_qa_candidates(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "knowledgePoints": [],
            "sourceSegmentKeys": ["mp4-c1"],
        },
        segments=[_segments()[0]],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert [candidate.segment_key for candidate in candidates] == ["mp4-c1"]

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={
            **_current_block(),
            "citations": [],
            "knowledgePoints": [],
            "sourceSegmentKeys": ["mp4-c1"],
        },
        segments=[_segments()[0]],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["citations"] == [
        {"resourceId": 1, "refLabel": "视频 00s-20s", "startSec": 0, "endSec": 20}
    ]


def test_block_video_citation_allows_subrange_but_rejects_cross_segment_time():
    video_segments = [_segments()[0]]
    subrange_candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={
            **_current_block(),
            "citations": [{"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 5, "endSec": 15, "refLabel": "subrange"}],
            "knowledgePoints": [],
        },
        segments=video_segments,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    cross_range_candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={
            **_current_block(),
            "citations": [{"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 5, "endSec": 25, "refLabel": "cross"}],
            "knowledgePoints": [],
        },
        segments=video_segments,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert subrange_candidates[0].to_qa_citation() == {
        "resourceId": 1,
        "refLabel": "subrange",
        "startSec": 5,
        "endSec": 15,
    }
    assert cross_range_candidates == []


def test_current_block_without_knowledge_points_does_not_accept_all_evidence():
    candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        knowledge_point_evidences=[{"knowledgePointKey": "kp-other", "segmentKey": "pdf-p1"}],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert "knowledge_point_evidence" not in [candidate.source for candidate in candidates]


def test_schema_valid_client_citation_is_mapped_back_to_candidate():
    class SchemaValidClient:
        def generate_answer(self, question, candidates):
            return {
                "answerMd": "集合是确定对象组成的整体。",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 2, "pageNo": 1, "refLabel": "PDF 第 1 页"}],
            }

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=SchemaValidClient(),
    )

    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"
    assert response["generationMetadata"] == {
        "source": "model",
        "reason": "model_response",
        "evidenceTier": "original_evidence",
    }
    assert response["citations"] == [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}]


def test_configured_qa_answer_client_requires_enable_and_app_key(monkeypatch):
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_QA", raising=False)
    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "fake-key")
    assert get_configured_qa_answer_client() is None

    monkeypatch.setenv("KNOWLINK_ENABLE_VIVO_QA", "true")
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)
    assert get_configured_qa_answer_client() is None

    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "fake-key")
    monkeypatch.setenv("KNOWLINK_VIVO_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("KNOWLINK_VIVO_QA_MODEL", "qa-model")
    monkeypatch.setenv("KNOWLINK_VIVO_QA_TIMEOUT_SEC", "9")

    assert isinstance(get_configured_qa_answer_client(), VivoQaAnswerClient)


def test_configured_qa_answer_client_supports_deepseek_provider_without_vivo_enable(monkeypatch):
    monkeypatch.setenv("KNOWLINK_QA_PROVIDER", "deepseek")
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_QA", raising=False)
    assert get_configured_qa_answer_client() is None

    monkeypatch.setenv("KNOWLINK_DEEPSEEK_API_KEY", "fake-deepseek-key")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_REASONING_EFFORT", "high")

    assert isinstance(get_configured_qa_answer_client(), DeepSeekQaAnswerClient)


def test_deepseek_qa_answer_client_uses_ai_service_request():
    model_payload = {
        "answerMd": "集合是确定对象组成的整体。",
        "answerType": "direct_answer",
        "citations": [
            {
                "resourceId": 1,
                "segmentKey": "mp4-c1",
                "startSec": 0,
                "endSec": 20,
                "refLabel": "视频 00s-20s",
            }
        ],
    }

    ai_service = FakeAIService(model_payload)
    client = DeepSeekQaAnswerClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        timeout_sec=13,
        ai_service=ai_service,
    )

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block=_current_block(),
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    request = ai_service.requests[0]
    assert request.provider == "deepseek"
    assert request.model == "deepseek-v4-flash"
    assert request.timeout_sec == 13
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 4096, "reasoning_effort": "high"}
    assert [message.role for message in request.messages] == ["system", "user"]
    QA_RESPONSE_VALIDATOR.validate(response)
    assert response["answerType"] == "direct_answer"


def test_deepseek_qa_answer_client_unreferenced_request_uses_scope_prompt():
    ai_service = FakeAIService({"answerMd": "空集没有元素。", "answerType": "direct_answer", "citations": []})
    client = DeepSeekQaAnswerClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        timeout_sec=13,
        ai_service=ai_service,
    )

    payload = client.generate_unreferenced_answer(
        "空集为什么也是集合？",
        context_text="集合论入门\n空集",
        evidence_tier="course_prior",
        course_scope={"title": "集合论入门", "knowledgePointNames": ["空集"]},
    )

    request = ai_service.requests[0]
    assert request.provider == "deepseek"
    assert request.model == "deepseek-v4-flash"
    assert request.timeout_sec == 13
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 4096, "reasoning_effort": "high"}
    assert [message.role for message in request.messages] == ["system", "user"]
    assert "evidenceTier" in request.messages[1].content
    assert "course_prior" in request.messages[1].content
    assert payload["answerMd"] == "空集没有元素。"


def test_vivo_qa_answer_client_uses_ai_service_request_and_normalizes_json():
    model_payload = {
        "answerMd": "集合是确定对象组成的整体。",
        "answerType": "direct_answer",
        "citations": [
            {
                "resourceId": 2,
                "segmentKey": "pdf-p1",
                "pageNo": 1,
                "refLabel": "PDF 第 1 页",
            }
        ],
    }
    ai_service = FakeAIService(model_payload)
    client = VivoQaAnswerClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=7,
        ai_service=ai_service,
    )
    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    request = ai_service.requests[0]
    assert request.provider == "vivo"
    assert request.model == "Doubao-Seed-2.0-pro"
    assert request.temperature == 0.1
    assert request.timeout_sec == 7
    assert request.response_format == {"type": "json_object"}
    assert request.metadata["max_tokens"] == 2048
    assert request.metadata["stream"] is False
    assert request.metadata["request_id"]
    assert "evidenceCandidates" in request.messages[1].content
    assert response["answerType"] == "direct_answer"
    assert response["citations"] == [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}]


def test_vivo_qa_answer_client_unreferenced_request_uses_scope_prompt():
    ai_service = FakeAIService({"answerMd": "讲义说明集合定义。", "answerType": "direct_answer", "citations": []})
    client = VivoQaAnswerClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=7,
        ai_service=ai_service,
    )

    payload = client.generate_unreferenced_answer(
        "集合的定义是什么？",
        context_text="集合是确定对象组成的整体。",
        evidence_tier="handout_context",
    )

    request = ai_service.requests[0]
    assert request.provider == "vivo"
    assert request.model == "Doubao-Seed-2.0-pro"
    assert request.temperature == 0.1
    assert request.timeout_sec == 7
    assert request.response_format == {"type": "json_object"}
    assert request.metadata["max_tokens"] == 2048
    assert request.metadata["stream"] is False
    assert request.metadata["request_id"]
    assert [message.role for message in request.messages] == ["system", "user"]
    assert "evidenceTier" in request.messages[1].content
    assert "handout_context" in request.messages[1].content
    assert payload["answerMd"] == "讲义说明集合定义。"


def test_vivo_qa_bad_json_falls_back_to_candidate():
    client = VivoQaAnswerClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=7,
        ai_service=FakeAIService(error=AIOutputParseError("model output does not contain a JSON object")),
    )

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    assert response["answerType"] == "direct_answer"
    assert response["generationMetadata"] == {
        "source": "fallback",
        "reason": "model_output_invalid",
        "evidenceTier": "original_evidence",
    }
    assert response["citations"] == [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}]


def test_vivo_qa_candidate_outside_citation_becomes_insufficient_evidence():
    model_payload = {
        "answerMd": "候选外引用不能被接受。",
        "answerType": "direct_answer",
        "citations": [{"resourceId": 999, "pageNo": 1, "refLabel": "外部资料"}],
    }
    client = VivoQaAnswerClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=7,
        ai_service=FakeAIService(model_payload),
    )

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    assert response["answerType"] == "insufficient_evidence"
    assert response["citations"] == []


def test_qa_maps_ai_provider_error_to_fallback_reason():
    client = VivoQaAnswerClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=7,
        ai_service=FakeAIService(error=AIProviderError("provider unavailable")),
    )

    response = generate_block_qa_response(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
        client=client,
    )

    assert response["generationMetadata"] == {
        "source": "fallback",
        "reason": "model_provider_error",
        "evidenceTier": "original_evidence",
    }


def test_qa_message_refs_include_only_answer_citations_not_all_candidates():
    candidates = build_block_scoped_qa_candidates(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    response = {
        "answerMd": "集合是确定对象组成的整体。",
        "answerType": "direct_answer",
        "citations": [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}],
    }

    refs = build_qa_message_refs(
        response,
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert [ref["segmentKey"] for ref in refs] == ["pdf-p1"]
    assert refs[0]["sortNo"] == 1
    assert refs[0]["rank"] == 1
    assert refs[0]["refType"] == "pdf_page"


def test_qa_answer_with_candidate_outside_citation_becomes_insufficient_evidence():
    candidates = build_block_scoped_qa_candidates(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    result = normalize_qa_answer_with_refs(
        {
            "answerMd": "候选外资料不能支撑答案。",
            "answerType": "direct_answer",
            "citations": [{"resourceId": 999, "pageNo": 1, "refLabel": "外部资料"}],
        },
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(result.response)
    assert result.response["answerType"] == "insufficient_evidence"
    assert result.refs == []


def test_qa_message_refs_dedupe_by_normalized_tuple_and_keep_answer_order():
    candidates = build_block_scoped_qa_candidates(
        "集合的定义和例题",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    response = {
        "answerMd": "先看例题，再回到定义。",
        "answerType": "direct_answer",
        "citations": [
            {"resourceId": 2, "refLabel": "PDF 第 2 页", "pageNo": 2},
            {"resourceId": 2, "refLabel": "PDF 第 2 页重复", "pageNo": 2},
            {"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1},
        ],
    }

    refs = build_qa_message_refs(
        response,
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert [(ref["segmentKey"], ref["sortNo"]) for ref in refs] == [("pdf-p2", 1), ("pdf-p1", 2)]


def test_qa_message_refs_use_exact_segment_identity_before_public_locator():
    segments = [
        *_segments(),
        {
            "courseId": 101,
            "parseRunId": 9001,
            "resourceId": 2,
            "segmentId": 204,
            "resourceType": "pdf",
            "segmentKey": "pdf-p1-alt",
            "segmentType": "pdf_page_text",
            "textContent": "集合定义页上的另一段说明。",
            "pageNo": 1,
        },
    ]
    candidates = build_block_scoped_qa_candidates(
        "集合定义",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=segments,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    result = normalize_qa_answer_with_refs(
        {
            "answerMd": "引用同一页上的第二个片段。",
            "answerType": "direct_answer",
            "citations": [{"resourceId": 2, "segmentId": 204, "pageNo": 1, "refLabel": "PDF 第 1 页"}],
        },
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(result.response)
    assert result.refs[0]["segmentId"] == 204
    assert result.refs[0]["segmentKey"] == "pdf-p1-alt"


def test_qa_message_refs_accept_valid_segment_key_identity_without_segment_id():
    candidates = build_block_scoped_qa_candidates(
        "集合定义",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    result = normalize_qa_answer_with_refs(
        {
            "answerMd": "引用合法候选 segmentKey。",
            "answerType": "direct_answer",
            "citations": [{"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "PDF 第 1 页"}],
        },
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(result.response)
    assert result.response["answerType"] == "direct_answer"
    assert result.refs[0]["segmentId"] == 201
    assert result.refs[0]["segmentKey"] == "pdf-p1"


def test_qa_response_and_refs_dedupe_mixed_id_key_and_public_citations():
    candidates = build_block_scoped_qa_candidates(
        "集合定义",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    result = normalize_qa_answer_with_refs(
        {
            "answerMd": "同一候选的不同引用形式只能写一次。",
            "answerType": "direct_answer",
            "citations": [
                {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "by key"},
                {"resourceId": 2, "segmentId": 201, "pageNo": 1, "refLabel": "by id"},
                {"resourceId": 2, "pageNo": 1, "refLabel": "public"},
            ],
        },
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    QA_RESPONSE_VALIDATOR.validate(result.response)
    assert result.response["citations"] == [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}]
    assert [(ref["segmentId"], ref["sortNo"]) for ref in result.refs] == [(201, 1)]


def test_qa_answer_with_explicit_candidate_outside_segment_identity_is_rejected():
    bad_identity_cases = [
        {"segmentId": 999},
        {"segmentId": 0},
        {"segmentId": "bad"},
        {"segmentKey": ""},
        {"segmentKey": "   "},
        {"segmentId": 201, "segmentKey": "wrong-key"},
    ]
    for identity_fields in bad_identity_cases:
        candidates = build_block_scoped_qa_candidates(
            "集合定义",
            current_block={**_current_block(), "citations": [], "knowledgePoints": []},
            segments=_segments(),
            active_course_id=101,
            active_parse_run_id=9001,
            active_handout_version_id=7001,
        )
        result = normalize_qa_answer_with_refs(
            {
                "answerMd": "不能把候选外 segmentId 改写成同页候选。",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 2, **identity_fields, "pageNo": 1, "refLabel": "PDF 第 1 页"}],
            },
            candidates,
            active_course_id=101,
            active_parse_run_id=9001,
            active_handout_version_id=7001,
        )

        QA_RESPONSE_VALIDATOR.validate(result.response)
        assert result.response["answerType"] == "insufficient_evidence"
        assert result.refs == []


def test_qa_message_refs_require_active_course_parse_run_and_handout_version():
    candidates = build_block_scoped_qa_candidates(
        "集合的定义是什么？",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )
    response = {
        "answerMd": "集合是确定对象组成的整体。",
        "answerType": "direct_answer",
        "citations": [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}],
    }

    refs = build_qa_message_refs(
        response,
        candidates,
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7002,
    )

    assert refs == []


def test_old_handout_block_version_does_not_receive_active_version_stamp():
    candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={**_current_block(), "handoutVersionId": 7000},
        segments=_segments(),
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert candidates == []


def test_old_adjacent_block_version_is_ignored():
    candidates = build_block_scoped_qa_candidates(
        "集合例题",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=_segments(),
        adjacent_blocks=[{**_adjacent_block(), "handoutVersionId": 7000}],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert "adjacent_block" not in [candidate.source for candidate in candidates]


def test_block_scoped_qa_filters_cross_course_and_old_parse_run_documents():
    candidates = build_block_scoped_qa_candidates(
        "集合",
        current_block={**_current_block(), "citations": [], "knowledgePoints": []},
        segments=[
            *_segments(),
            {
                "courseId": 202,
                "parseRunId": 9001,
                "resourceId": 9,
                "segmentId": 901,
                "segmentKey": "pdf-other-course",
                "segmentType": "pdf_page_text",
                "textContent": "跨课程资料不能进入 QA。",
                "pageNo": 9,
            },
            {
                "courseId": 101,
                "parseRunId": 8001,
                "resourceId": 8,
                "segmentId": 801,
                "segmentKey": "pdf-old-run",
                "segmentType": "pdf_page_text",
                "textContent": "旧解析版本资料不能进入 QA。",
                "pageNo": 8,
            },
        ],
        active_course_id=101,
        active_parse_run_id=9001,
        active_handout_version_id=7001,
    )

    assert [candidate.segment_key for candidate in candidates] == ["pdf-p1", "pdf-p2", "pdf-p3"]


def _current_block():
    return {
        "courseId": 101,
        "parseRunId": 9001,
        "handoutVersionId": 7001,
        "handoutBlockId": 4001,
        "outlineKey": "outline-1",
        "sortNo": 1,
        "title": "集合",
        "summary": "理解集合定义。",
        "contentMd": "## 集合\n\n集合是确定对象组成的整体。",
        "knowledgePoints": [{"knowledgePointKey": "kp-set", "displayName": "集合"}],
        "citations": [{"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "视频 00s-20s"}],
    }


def _adjacent_block():
    return {
        "courseId": 101,
        "parseRunId": 9001,
        "handoutVersionId": 7001,
        "handoutBlockId": 4002,
        "outlineKey": "outline-2",
        "sortNo": 2,
        "title": "集合例题",
        "summary": "相邻讲义块说明例题判断边界。",
        "contentMd": "## 集合例题\n\n相邻讲义块通过例题说明定义如何使用。",
        "citations": [{"resourceId": 2, "segmentKey": "pdf-p2", "pageNo": 2, "refLabel": "PDF 第 2 页"}],
    }


def _segments():
    return [
        {
            "courseId": 101,
            "parseRunId": 9001,
            "resourceId": 1,
            "segmentId": 101,
            "resourceType": "mp4",
            "segmentKey": "mp4-c1",
            "segmentType": "video_caption",
            "textContent": "集合是一些确定对象组成的整体。",
            "startSec": 0,
            "endSec": 20,
        },
        {
            "courseId": 101,
            "parseRunId": 9001,
            "resourceId": 2,
            "segmentId": 201,
            "resourceType": "pdf",
            "segmentKey": "pdf-p1",
            "segmentType": "pdf_page_text",
            "textContent": "集合是确定对象组成的整体，这个定义用于判断元素是否属于集合。",
            "pageNo": 1,
        },
        {
            "courseId": 101,
            "parseRunId": 9001,
            "resourceId": 2,
            "segmentId": 202,
            "resourceType": "pdf",
            "segmentKey": "pdf-p2",
            "segmentType": "pdf_page_text",
            "textContent": "例题要求先看对象是否确定，再判断它能否组成集合。",
            "pageNo": 2,
        },
        {
            "courseId": 101,
            "parseRunId": 9001,
            "resourceId": 2,
            "segmentId": 203,
            "resourceType": "pdf",
            "segmentKey": "pdf-p3",
            "segmentType": "pdf_page_text",
            "textContent": "补充资料说明集合符号和常见表达。",
            "pageNo": 3,
        },
    ]
