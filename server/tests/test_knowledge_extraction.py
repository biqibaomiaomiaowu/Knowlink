import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.knowledge_extraction import handout_block_to_knowledge_extraction


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_SCHEMA = json.loads(
    (ROOT / "schemas/ai/knowledge_point_extraction.schema.json").read_text(encoding="utf-8")
)
KNOWLEDGE_VALIDATOR = Draft202012Validator(KNOWLEDGE_SCHEMA)


def test_ready_block_derives_schema_valid_knowledge_extraction():
    extraction = handout_block_to_knowledge_extraction(_block(), _segments())

    KNOWLEDGE_VALIDATOR.validate(extraction)
    assert [item["knowledgePointKey"] for item in extraction["knowledgePoints"]] == ["kp-set"]
    assert extraction["segmentKnowledgePoints"]
    assert extraction["knowledgePointEvidences"]
    teacher_evidences = [
        item for item in extraction["knowledgePointEvidences"] if item["evidenceType"] == "teacher_emphasis"
    ]
    assert teacher_evidences
    assert teacher_evidences[0]["startSec"] == 0
    assert teacher_evidences[0]["endSec"] == 20


def test_extraction_does_not_reference_unknown_segments_or_knowledge_points():
    block = _block()
    block["sourceSegmentKeys"] = ["mp4-c1", "missing-source"]
    block["citations"].append(
        {"resourceId": 9, "segmentKey": "missing-citation", "pageNo": 1, "refLabel": "unknown"}
    )

    extraction = handout_block_to_knowledge_extraction(block, _segments())

    KNOWLEDGE_VALIDATOR.validate(extraction)
    known_segment_keys = {segment["segmentKey"] for segment in _segments()}
    known_kp_keys = {item["knowledgePointKey"] for item in extraction["knowledgePoints"]}
    assert {
        item["segmentKey"] for item in extraction["segmentKnowledgePoints"]
    }.issubset(known_segment_keys)
    assert {
        item["knowledgePointKey"] for item in extraction["segmentKnowledgePoints"]
    }.issubset(known_kp_keys)
    assert {item["segmentKey"] for item in extraction["knowledgePointEvidences"]}.issubset(known_segment_keys)
    assert {item["knowledgePointKey"] for item in extraction["knowledgePointEvidences"]}.issubset(known_kp_keys)


def _block():
    return {
        "outlineKey": "outline-1",
        "title": "集合",
        "summary": "理解集合与元素。",
        "contentMd": "集合是确定对象组成的整体。",
        "estimatedMinutes": 2,
        "sourceSegmentKeys": ["mp4-c1"],
        "knowledgePoints": [
            {
                "knowledgePointKey": "kp-set",
                "displayName": "集合",
                "description": "集合是确定对象组成的整体。",
                "difficultyLevel": "beginner",
                "importanceScore": 90,
                "sortNo": 1,
            }
        ],
        "citations": [
            {"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "视频"},
            {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "讲义"},
        ],
    }


def _segments():
    return [
        {
            "resourceId": 1,
            "segmentId": 101,
            "segmentKey": "mp4-c1",
            "segmentType": "video_caption",
            "textContent": "集合和元素。",
            "startSec": 0,
            "endSec": 20,
        },
        {
            "resourceId": 2,
            "segmentId": 201,
            "segmentKey": "pdf-p1",
            "segmentType": "pdf_page_text",
            "textContent": "集合定义。",
            "pageNo": 1,
        },
    ]
