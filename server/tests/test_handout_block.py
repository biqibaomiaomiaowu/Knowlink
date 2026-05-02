import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.handout_block import (
    VivoHandoutBlockClient,
    generate_handout_block,
    get_configured_handout_block_client,
)


ROOT = Path(__file__).resolve().parents[2]
HANDOUT_BLOCK_SCHEMA = json.loads((ROOT / "schemas/ai/handout_block.schema.json").read_text(encoding="utf-8"))
HANDOUT_BLOCK_VALIDATOR = Draft202012Validator(HANDOUT_BLOCK_SCHEMA)


def test_fallback_handout_block_uses_known_segments_and_validates_schema(monkeypatch):
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)

    block = generate_handout_block(_outline_item(), _segments())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["outlineKey"] == "outline-1"
    assert block["sourceSegmentKeys"] == ["mp4-c1", "mp4-c2"]
    assert block["knowledgePoints"][0]["knowledgePointKey"] == "kp-outline-1-1"
    assert {citation["segmentKey"] for citation in block["citations"]}.issubset(
        {segment["segmentKey"] for segment in _segments()}
    )


def test_fake_vivo_response_is_normalized_to_ready_block_schema():
    class FakeClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "outlineKey": "ignored-by-normalizer",
                "title": "集合与元素",
                "summary": "解释集合的基本记号。",
                "contentMd": "## 集合与元素\n\nA={1,2,3} 表示一个集合。",
                "estimatedMinutes": 2,
                "sourceSegmentKeys": ["mp4-c1", "unknown"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合是确定对象组成的整体。",
                        "difficultyLevel": "intermediate",
                        "importanceScore": 90,
                    }
                ],
                "citations": [
                    {"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "视频"},
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "讲义"},
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=FakeClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["outlineKey"] == "outline-1"
    assert block["sourceSegmentKeys"] == ["mp4-c1"]
    assert block["knowledgePoints"][0]["knowledgePointKey"] == "kp-set"
    assert [citation["segmentKey"] for citation in block["citations"]] == ["mp4-c1", "pdf-p1"]


def test_model_citations_filter_cross_time_unknown_and_mixed_locators():
    class DirtyCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "过滤不合法引用。",
                "contentMd": "合法引用只保留已知片段。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合的定义。",
                        "difficultyLevel": "beginner",
                        "importanceScore": 80,
                    }
                ],
                "citations": [
                    {"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "valid"},
                    {"resourceId": 1, "segmentKey": "mp4-c3", "startSec": 70, "endSec": 90, "refLabel": "cross"},
                    {"resourceId": 1, "segmentKey": "missing", "startSec": 0, "endSec": 20, "refLabel": "unknown"},
                    {
                        "resourceId": 2,
                        "segmentKey": "pdf-p1",
                        "pageNo": 1,
                        "startSec": 0,
                        "endSec": 20,
                        "refLabel": "mixed",
                    },
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "valid-doc"},
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=DirtyCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [citation["refLabel"] for citation in block["citations"]] == ["valid", "valid-doc"]
    assert [citation["segmentKey"] for citation in block["citations"]] == ["mp4-c1", "pdf-p1"]


def test_model_video_time_range_citation_expands_across_source_segments():
    class CrossSegmentCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "跨字幕片段引用。",
                "contentMd": "同一段讲义需要引用连续字幕。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合的定义。",
                        "difficultyLevel": "beginner",
                        "importanceScore": 80,
                    }
                ],
                "citations": [
                    {
                        "resourceId": 1,
                        "segmentKey": "mp4-c1",
                        "startSec": 0,
                        "endSec": 60,
                        "refLabel": "视频跨段",
                    }
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=CrossSegmentCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [
        (citation["segmentKey"], citation["segmentId"], citation["startSec"], citation["endSec"])
        for citation in block["citations"]
    ] == [("mp4-c1", 101, 0, 20), ("mp4-c2", 102, 20, 50)]


def test_model_video_time_range_without_segment_key_expands_by_resource_and_time_overlap():
    class ResourceTimeCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "按资源和时间定位。",
                "contentMd": "模型可能只返回资源 ID 和时间段。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合的定义。",
                        "difficultyLevel": "beginner",
                        "importanceScore": 80,
                    }
                ],
                "citations": [
                    {
                        "resourceId": 1,
                        "startSec": 10,
                        "endSec": 45,
                        "refLabel": "视频时间段",
                    }
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=ResourceTimeCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [
        (citation["segmentKey"], citation["segmentId"], citation["startSec"], citation["endSec"])
        for citation in block["citations"]
    ] == [("mp4-c1", 101, 10, 20), ("mp4-c2", 102, 20, 45)]


def test_model_citations_prepend_source_video_when_only_supplemental_citation_is_returned():
    class SupplementalOnlyCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "模型只返回讲义页引用。",
                "contentMd": "讲义块仍需要可跳转的视频来源。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合的定义。",
                        "difficultyLevel": "beginner",
                        "importanceScore": 80,
                    }
                ],
                "citations": [
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "讲义"}
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=SupplementalOnlyCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [citation["segmentKey"] for citation in block["citations"]] == ["mp4-c1", "pdf-p1"]
    assert block["citations"][0]["startSec"] == 0
    assert block["citations"][0]["endSec"] == 20


def test_configured_handout_block_client_requires_app_key(monkeypatch):
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)
    assert get_configured_handout_block_client() is None

    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "fake-key")
    monkeypatch.setenv("KNOWLINK_VIVO_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("KNOWLINK_VIVO_HANDOUT_BLOCK_MODEL", "block-model")
    monkeypatch.setenv("KNOWLINK_VIVO_HANDOUT_TIMEOUT_SEC", "9")
    monkeypatch.setenv("KNOWLINK_VIVO_HANDOUT_BLOCK_TIMEOUT_SEC", "120")

    client = get_configured_handout_block_client()
    assert isinstance(client, VivoHandoutBlockClient)
    assert client._timeout_sec == 120


def _outline_item():
    return {
        "outlineKey": "outline-1",
        "title": "集合的基本概念",
        "summary": "从视频片段理解集合和元素。",
        "startSec": 0,
        "endSec": 60,
        "sortNo": 1,
        "generationStatus": "pending",
        "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
    }


def _segments():
    return [
        {
            "resourceId": 1,
            "segmentId": 101,
            "resourceType": "mp4",
            "segmentKey": "mp4-c1",
            "segmentType": "video_caption",
            "orderNo": 1,
            "textContent": "今天我们从集合和元素开始。",
            "startSec": 0,
            "endSec": 20,
        },
        {
            "resourceId": 1,
            "segmentId": 102,
            "resourceType": "mp4",
            "segmentKey": "mp4-c2",
            "segmentType": "video_caption",
            "orderNo": 2,
            "textContent": "集合可以用大写字母表示。",
            "startSec": 20,
            "endSec": 50,
        },
        {
            "resourceId": 1,
            "segmentId": 103,
            "resourceType": "mp4",
            "segmentKey": "mp4-c3",
            "segmentType": "video_caption",
            "orderNo": 3,
            "textContent": "下一段内容。",
            "startSec": 70,
            "endSec": 90,
        },
        {
            "resourceId": 2,
            "segmentId": 201,
            "resourceType": "pdf",
            "segmentKey": "pdf-p1",
            "segmentType": "pdf_page_text",
            "orderNo": 4,
            "textContent": "集合是一些确定对象组成的整体。",
            "pageNo": 1,
        },
    ]
