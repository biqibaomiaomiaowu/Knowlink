import json
from pathlib import Path

from jsonschema import Draft202012Validator

from server.ai.core.errors import AIConfigurationError
from server.ai.core.types import AIModelResult
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


def test_fallback_handout_block_uses_known_segments_and_validates_schema(monkeypatch):
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)

    block = generate_handout_block(_outline_item(), _segments())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["outlineKey"] == "outline-1"
    assert block["generationMetadata"] == {"source": "fallback", "reason": "model_unavailable"}
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
    assert [citation["refLabel"] for citation in block["citations"]] == ["视频 00s-60s", "valid-doc"]
    assert [citation["segmentKey"] for citation in block["citations"]] == ["mp4-c1", "pdf-p1"]
    assert block["citations"][0]["startSec"] == 0
    assert block["citations"][0]["endSec"] == 60


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


def test_model_video_time_range_citation_collapses_to_one_block_range_video_citation():
    class CrossSegmentCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "跨字幕片段引用会收敛。",
                "contentMd": "同一段讲义只暴露一个视频跳转范围。",
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
        if "startSec" in citation
    ] == [("mp4-c1", 101, 0, 60)]


def test_block_range_video_citation_uses_outline_first_source_segment_even_with_model_source_subset():
    class SubsetSourceClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "模型只选择第二个 source segment。",
                "contentMd": "视频 citation 仍应绑定 block 的首个 source segment。",
                "sourceSegmentKeys": ["mp4-c2"],
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
                        "segmentKey": "mp4-c2",
                        "startSec": 20,
                        "endSec": 50,
                        "refLabel": "模型选择第二段",
                    }
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=SubsetSourceClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["sourceSegmentKeys"] == ["mp4-c2"]
    assert [
        (citation["segmentKey"], citation["segmentId"], citation["startSec"], citation["endSec"])
        for citation in block["citations"]
        if "startSec" in citation
    ] == [("mp4-c1", 101, 0, 60)]


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
        if "startSec" in citation
    ] == [("mp4-c1", 101, 0, 60)]


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
        if "startSec" in citation
    ] == [("mp4-c1", 10, 45)]


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
    assert block["citations"][0]["endSec"] == 60


def test_model_citations_adds_fallback_doc_citation_when_supplemental_doc_exists():
    class VideoOnlyCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "模型漏掉文档引用时需要兜底。",
                "contentMd": "讲义块仍应保留相关补充资料来源。",
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
                    {"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "视频"}
                ],
            }

    block = generate_handout_block(_outline_item(), _segments(), client=VideoOnlyCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [
        (citation["segmentKey"], citation.get("pageNo"), citation.get("slideNo"), citation.get("anchorKey"))
        for citation in block["citations"]
        if "startSec" not in citation
    ] == [("pdf-p1", 1, None, None)]


def test_model_citations_do_not_fallback_to_unrelated_document_segment():
    class VideoOnlyCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "无相关文档时不补引用。",
                "contentMd": "只有视频来源。",
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
                    {"resourceId": 1, "segmentKey": "mp4-c1", "startSec": 0, "endSec": 20, "refLabel": "视频"}
                ],
            }

    block = generate_handout_block(_outline_item(), _segments_with_unrelated_doc(), client=VideoOnlyCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [citation for citation in block["citations"] if "startSec" not in citation] == []


def test_fallback_handout_block_does_not_cite_unrelated_document_segment(monkeypatch):
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)

    block = generate_handout_block(_outline_item(), _segments_with_unrelated_doc())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert [citation for citation in block["citations"] if "startSec" not in citation] == []
    assert [
        (citation["segmentKey"], citation["startSec"], citation["endSec"])
        for citation in block["citations"]
        if "startSec" in citation
    ] == [("mp4-c1", 0, 60)]


def test_model_citations_preserve_up_to_three_selected_document_citations_with_server_locators():
    class MultiDocCitationClient:
        def generate_block(self, outline_item, context_segments, *, preferences=None):
            return {
                "title": "集合",
                "summary": "模型可选择多个补充资料引用。",
                "contentMd": "PDF、PPT、DOCX 引用由服务端反查真实 locator。",
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
                    {"resourceId": 2, "segmentKey": "pdf-p1", "pageNo": 99, "refLabel": "pdf"},
                    {"resourceId": 3, "segmentKey": "ppt-s2", "slideNo": 99, "refLabel": "ppt"},
                    {"resourceId": 4, "segmentKey": "docx-a", "anchorKey": "fake", "refLabel": "docx"},
                    {"resourceId": 5, "segmentKey": "pdf-p2", "pageNo": 99, "refLabel": "extra"},
                ],
            }

    block = generate_handout_block(_outline_item(), _segments_with_multiple_docs(), client=MultiDocCitationClient())

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    doc_citations = [citation for citation in block["citations"] if "startSec" not in citation]
    assert [
        (citation["segmentKey"], citation.get("pageNo"), citation.get("slideNo"), citation.get("anchorKey"))
        for citation in doc_citations
    ] == [
        ("pdf-p1", 1, None, None),
        ("ppt-s2", None, 2, None),
        ("docx-a", None, None, "docx-a"),
    ]


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


def test_deepseek_handout_block_client_uses_ai_service_request():
    model_payload = {
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
    }

    ai_service = FakeAIService(model_payload)
    client = DeepSeekHandoutBlockClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        timeout_sec=11,
        ai_service=ai_service,
    )

    block = generate_handout_block(_outline_item(), _segments(), client=client)

    request = ai_service.requests[0]
    assert request.provider == "deepseek"
    assert request.model == "deepseek-v4-flash"
    assert request.timeout_sec == 11
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 8192, "reasoning_effort": "high"}
    assert [message.role for message in request.messages] == ["system", "user"]
    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["title"] == "集合的基本概念"


def test_vivo_handout_block_client_uses_ai_service_request():
    model_payload = {
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
    }
    ai_service = FakeAIService(model_payload)
    client = VivoHandoutBlockClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=9,
        ai_service=ai_service,
    )

    block = generate_handout_block(_outline_item(), _segments(), client=client)

    request = ai_service.requests[0]
    assert request.provider == "vivo"
    assert request.model == "Doubao-Seed-2.0-pro"
    assert request.temperature == 0.1
    assert request.timeout_sec == 9
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 4096, "stream": False}
    assert [message.role for message in request.messages] == ["system", "user"]
    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["generationMetadata"] == {"source": "model", "reason": "model_response"}


def test_handout_block_maps_ai_configuration_error_to_fallback_reason():
    client = VivoHandoutBlockClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-pro",
        timeout_sec=9,
        ai_service=FakeAIService(error=AIConfigurationError("missing provider")),
    )

    block = generate_handout_block(_outline_item(), _segments(), client=client)

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    assert block["generationMetadata"] == {"source": "fallback", "reason": "model_unconfigured"}


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


def _segments_with_multiple_docs():
    return [
        *_segments(),
        {
            "resourceId": 3,
            "segmentId": 301,
            "resourceType": "pptx",
            "segmentKey": "ppt-s2",
            "segmentType": "ppt_slide_text",
            "orderNo": 5,
            "textContent": "课件用文氏图展示集合关系。",
            "slideNo": 2,
        },
        {
            "resourceId": 4,
            "segmentId": 401,
            "resourceType": "docx",
            "segmentKey": "docx-a",
            "segmentType": "docx_block_text",
            "orderNo": 6,
            "textContent": "DOCX 补充集合表示法。",
            "anchorKey": "docx-a",
        },
        {
            "resourceId": 5,
            "segmentId": 501,
            "resourceType": "pdf",
            "segmentKey": "pdf-p2",
            "segmentType": "pdf_page_text",
            "orderNo": 7,
            "textContent": "额外 PDF 资料不应超过三条文档引用上限。",
            "pageNo": 2,
        },
    ]


def _segments_with_unrelated_doc():
    return [
        *_segments()[:3],
        {
            "resourceId": 8,
            "segmentId": 801,
            "resourceType": "pdf",
            "segmentKey": "pdf-unrelated",
            "segmentType": "pdf_page_text",
            "orderNo": 4,
            "textContent": "矩阵特征值与线性变换的例题。",
            "pageNo": 8,
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
