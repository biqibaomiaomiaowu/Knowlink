from server.ai.vector_projection import (
    build_vector_document_inputs,
    handout_block_to_vector_document,
    knowledge_point_to_vector_document,
    segment_to_vector_document,
)


def test_segment_vector_input_keeps_owner_content_and_locator_metadata():
    vector = segment_to_vector_document(
        {
            "courseId": 1,
            "parseRunId": 9001,
            "resourceId": 2,
            "segmentId": 201,
            "resourceType": "pdf",
            "segmentKey": "pdf-p1",
            "segmentType": "pdf_page_text",
            "textContent": "集合是确定对象组成的整体。",
            "pageNo": 1,
        }
    )

    assert vector is not None
    assert vector.owner_type == "segment"
    assert vector.owner_id == 201
    assert vector.content_text == "集合是确定对象组成的整体。"
    assert vector.metadata_json["resourceType"] == "pdf"
    assert vector.metadata_json["pageNo"] == 1
    assert "startSec" not in vector.metadata_json
    assert vector.resource_id == 2


def test_docx_segment_vector_input_accepts_section_path_locator():
    vector = segment_to_vector_document(
        {
            "segmentId": 202,
            "resourceType": "docx",
            "segmentKey": "docx-b1",
            "segmentType": "docx_block_text",
            "orderNo": 1,
            "textContent": "集合的初见。",
            "sectionPath": ["集合论基础", "学习目标"],
        }
    )

    assert vector is not None
    assert vector.owner_type == "segment"
    assert vector.owner_id == 202
    assert vector.metadata_json["sectionPath"] == ["集合论基础", "学习目标"]
    assert vector.metadata_json["orderNo"] == 1
    assert "anchorKey" not in vector.metadata_json


def test_docx_segment_vector_input_accepts_root_section_with_order_no():
    vector = segment_to_vector_document(
        {
            "segmentId": 203,
            "resourceType": "docx",
            "segmentKey": "docx-b1",
            "segmentType": "docx_block_text",
            "orderNo": 1,
            "textContent": "集合论基础",
            "sectionPath": [],
        }
    )

    assert vector is not None
    assert vector.metadata_json["sectionPath"] == []
    assert vector.metadata_json["orderNo"] == 1


def test_knowledge_point_vector_input_uses_description_aliases_and_related_segments():
    vector = knowledge_point_to_vector_document(
        {
            "knowledgePointId": 301,
            "knowledgePointKey": "kp-set",
            "displayName": "集合",
            "canonicalName": "集合",
            "description": "确定对象组成的整体。",
            "aliases": ["set", "集合论对象"],
        },
        segment_relations=[{"knowledgePointKey": "kp-set", "segmentKey": "mp4-c1"}],
        evidences=[{"knowledgePointKey": "kp-set", "segmentKey": "pdf-p1"}],
    )

    assert vector is not None
    assert vector.owner_type == "knowledge_point"
    assert vector.owner_id == 301
    assert "集合" in vector.content_text
    assert "set" in vector.content_text
    assert vector.metadata_json["segmentKeys"] == ["mp4-c1", "pdf-p1"]


def test_handout_block_vector_input_projects_content_and_reference_metadata():
    vector = handout_block_to_vector_document(
        {
            "handoutBlockId": 401,
            "handoutVersionId": 501,
            "outlineKey": "outline-1",
            "title": "集合",
            "summary": "理解集合。",
            "contentMd": "## 集合\n\n集合是确定对象组成的整体。",
            "sourceSegmentKeys": ["mp4-c1"],
            "knowledgePoints": [{"knowledgePointKey": "kp-set"}],
            "citations": [
                {"segmentKey": "pdf-p1", "pageNo": 1},
                {"segmentKey": "mp4-c1", "startSec": 0, "endSec": 20},
            ],
        }
    )

    assert vector is not None
    assert vector.owner_type == "handout_block"
    assert vector.owner_id == 401
    assert vector.handout_version_id == 501
    assert vector.metadata_json["outlineKey"] == "outline-1"
    assert vector.metadata_json["citationSegmentKeys"] == ["pdf-p1", "mp4-c1"]
    assert "mp4-c1" in vector.metadata_json["citationSegmentKeys"]
    assert vector.metadata_json["knowledgePointKeys"] == ["kp-set"]


def test_projection_filters_empty_text_and_mixed_locator_segment():
    assert segment_to_vector_document({"segmentKey": "empty", "textContent": "", "pageNo": 1}) is None
    assert (
        segment_to_vector_document(
            {
                "segmentKey": "mixed",
                "textContent": "invalid locator",
                "pageNo": 1,
                "startSec": 0,
                "endSec": 10,
            }
        )
        is None
    )
    assert (
        segment_to_vector_document(
            {
                "segmentKey": "mixed-docx",
                "textContent": "invalid locator",
                "sectionPath": ["第 1 章"],
                "orderNo": 1,
                "anchorKey": "legacy-anchor",
            }
        )
        is None
    )
    assert (
        segment_to_vector_document(
            {
                "resourceType": "docx",
                "segmentKey": "missing-order",
                "textContent": "invalid docx locator",
                "sectionPath": ["第 1 章"],
            }
        )
        is None
    )


def test_build_vector_document_inputs_combines_three_owner_types():
    items = build_vector_document_inputs(
        segments=[{"segmentId": 1, "segmentKey": "mp4-c1", "textContent": "视频字幕", "startSec": 0, "endSec": 10}],
        knowledge_extraction={
            "knowledgePoints": [
                {"knowledgePointKey": "kp-set", "displayName": "集合", "description": "集合定义。"}
            ],
            "segmentKnowledgePoints": [{"knowledgePointKey": "kp-set", "segmentKey": "mp4-c1"}],
            "knowledgePointEvidences": [],
        },
        handout_block={
            "outlineKey": "outline-1",
            "title": "集合",
            "summary": "理解集合。",
            "contentMd": "集合是确定对象组成的整体。",
        },
    )

    assert [item.owner_type for item in items] == ["segment", "knowledge_point", "handout_block"]
