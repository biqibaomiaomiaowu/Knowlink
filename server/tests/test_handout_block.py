import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.handout_block import (
    DeepSeekHandoutBlockClient,
    VivoHandoutBlockClient,
    build_handout_block_context,
    generate_handout_block,
    get_configured_handout_block_client,
    handout_block_ref_identity,
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


def test_handout_block_context_includes_current_asr_adjacent_context_and_related_docs():
    context = build_handout_block_context(_outline_item(), _segments())

    assert [segment["segmentKey"] for segment in context.source_segments] == ["mp4-c1", "mp4-c2"]
    assert [segment["segmentKey"] for segment in context.adjacent_segments] == ["mp4-c3"]
    assert [segment["segmentKey"] for segment in context.supplemental_segments] == ["pdf-p1"]
    assert [segment["segmentKey"] for segment in context.all_segments] == [
        "mp4-c1",
        "mp4-c2",
        "mp4-c3",
        "pdf-p1",
    ]


def test_handout_block_adjacent_context_stays_on_source_video_resource():
    context = build_handout_block_context(_outline_item(), [*_segments(), _other_video_segment()])

    assert [segment["segmentKey"] for segment in context.adjacent_segments] == ["mp4-c3"]
    assert "other-mp4-c1" not in [segment["segmentKey"] for segment in context.all_segments]


def test_model_receives_outline_context_preferences_and_ready_block_stays_schema_valid():
    class InspectingClient:
        def __init__(self):
            self.context_segments = []
            self.preferences = None

        def generate_block(self, outline_item, context_segments, *, preferences=None):
            self.context_segments = list(context_segments)
            self.preferences = preferences
            return {
                "title": "集合",
                "summary": "结合视频和文档解释集合。",
                "contentMd": "## 集合\n\n集合是确定对象组成的整体。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "确定对象组成的整体。",
                    }
                ],
                "citations": [
                    {"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "视频"},
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "讲义"},
                ],
            }

    client = InspectingClient()
    block = generate_handout_block(
        _outline_item(),
        _segments(),
        preferences={"difficultyLevel": "intermediate", "style": "example_first"},
        client=client,
    )

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert client.preferences == {"difficultyLevel": "intermediate", "style": "example_first"}
    assert [segment["segmentKey"] for segment in client.context_segments] == [
        "mp4-c1",
        "mp4-c2",
        "mp4-c3",
        "pdf-p1",
    ]
    assert block["sourceSegmentKeys"] == ["mp4-c1", "mp4-c2"]


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


def test_model_citations_are_candidate_segments_and_server_normalized_locators():
    class CandidateCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "模型只选择候选片段，定位由服务端反查。",
                "contentMd": "PDF 页码不能由模型自由决定。",
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
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 99, "refLabel": "corrected-page"},
                    {"resourceId": 999, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "wrong-resource"},
                    {"resourceId": 2, "segmentKey": "pdf-p1", "segmentId": 999, "pageNo": 1, "refLabel": "wrong-segment-id"},
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 1, "refLabel": "duplicate"},
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=CandidateCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [citation["segmentKey"] for citation in block["citations"]] == ["mp4-c1", "pdf-p1"]
    assert block["citations"][1]["refLabel"] == "corrected-page"
    assert block["citations"][1]["pageNo"] == 1
    assert handout_block_ref_identity(block["citations"][1]) == (2, "id:201", (("pageNo", 1),))


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


def test_model_video_time_range_is_clipped_to_outline_item_and_split_by_overlap():
    class WideTimeCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "跨范围视频引用需要裁剪。",
                "contentMd": "只允许引用当前 outline item 范围内的字幕。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合的定义。",
                    }
                ],
                "citations": [{"resourceId": 1, "startSec": 0, "endSec": 80, "refLabel": "wide"}],
            }

    outline_item = {**_outline_item(), "startSec": 10, "endSec": 45}
    block = generate_handout_block(outline_item, _segments(), client=WideTimeCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [
        (citation["segmentKey"], citation["startSec"], citation["endSec"])
        for citation in block["citations"]
    ] == [("mp4-c1", 10, 20), ("mp4-c2", 20, 45)]


def test_video_time_range_rejects_conflicting_segment_key_and_segment_id():
    class ConflictingSeedClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "冲突 identity 的视频引用不能被拆分接受。",
                "contentMd": "segmentKey 和 segmentId 必须指向同一候选片段。",
                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                "knowledgePoints": [
                    {
                        "knowledgePointKey": "kp-set",
                        "displayName": "集合",
                        "description": "集合的定义。",
                    }
                ],
                "citations": [
                    {
                        "resourceId": 1,
                        "segmentKey": "mp4-c1",
                        "segmentId": 102,
                        "startSec": 0,
                        "endSec": 60,
                        "refLabel": "conflict",
                    },
                    {
                        "resourceId": 2,
                        "segmentKey": "pdf-p1",
                        "pageNo": 1,
                        "refLabel": "valid-doc",
                    },
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=ConflictingSeedClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [citation["segmentKey"] for citation in block["citations"]] == ["mp4-c1", "pdf-p1"]
    assert all(citation["refLabel"] != "conflict" for citation in block["citations"])


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


def test_configured_handout_block_client_supports_deepseek_provider(monkeypatch):
    monkeypatch.setenv("KNOWLINK_HANDOUT_BLOCK_PROVIDER", "deepseek")
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    assert get_configured_handout_block_client() is None

    monkeypatch.setenv("KNOWLINK_DEEPSEEK_API_KEY", "fake-deepseek-key")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_REASONING_EFFORT", "high")

    assert isinstance(get_configured_handout_block_client(), DeepSeekHandoutBlockClient)


def test_deepseek_handout_block_client_uses_thinking_json_mode(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "reasoning_content": "思考内容不会被解析。",
                                "content": json.dumps(
                                    {
                                        "outlineKey": "outline-1",
                                        "title": "集合的基本概念",
                                        "summary": "集合由确定元素组成。",
                                        "contentMd": "集合是由确定对象组成的整体。",
                                        "estimatedMinutes": 3,
                                        "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                                        "knowledgePoints": [
                                            {
                                                "knowledgePointKey": "kp-outline-1-1",
                                                "displayName": "集合",
                                                "description": "理解集合与元素的关系。",
                                                "difficultyLevel": "beginner",
                                                "importanceScore": 80,
                                                "sortNo": 1,
                                            }
                                        ],
                                        "citations": [
                                            {
                                                "resourceId": 1,
                                                "segmentKey": "mp4-c1",
                                                "startSec": 0,
                                                "endSec": 20,
                                                "refLabel": "视频 00:00-00:20",
                                            }
                                        ],
                                    },
                                    ensure_ascii=False,
                                ),
                            }
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = DeepSeekHandoutBlockClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        timeout_sec=11,
    )

    block = generate_handout_block(_outline_item(), _segments(), client=client)

    body = json.loads(captured["body"])
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["timeout"] == 11
    assert body["model"] == "deepseek-v4-flash"
    assert body["thinking"] == {"type": "enabled"}
    assert body["reasoning_effort"] == "high"
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 8192
    assert "temperature" not in body
    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["title"] == "集合的基本概念"


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


def _other_video_segment():
    return {
        "resourceId": 9,
        "segmentId": 901,
        "resourceType": "mp4",
        "segmentKey": "other-mp4-c1",
        "segmentType": "video_caption",
        "orderNo": 3,
        "textContent": "另一段视频的字幕不应作为相邻上下文。",
        "startSec": 50,
        "endSec": 60,
    }
