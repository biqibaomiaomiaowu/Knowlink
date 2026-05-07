import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.qa_policy import (
    build_qa_message_refs,
    build_block_scoped_qa_candidates,
    generate_block_qa_response,
    normalize_qa_answer_with_refs,
)


ROOT = Path(__file__).resolve().parents[2]
QA_RESPONSE_SCHEMA = json.loads((ROOT / "schemas/ai/qa_response.schema.json").read_text(encoding="utf-8"))
QA_RESPONSE_VALIDATOR = Draft202012Validator(QA_RESPONSE_SCHEMA)


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
    assert response["citations"] == [{"resourceId": 2, "refLabel": "PDF 第 1 页", "pageNo": 1}]


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
