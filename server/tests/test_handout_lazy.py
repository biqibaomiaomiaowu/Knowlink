import json

from server.ai.core.errors import AIProviderError
from server.ai.core.types import AIModelResult
from server.ai.handout_lazy import (
    DeepSeekHandoutOutlineClient,
    VivoHandoutOutlineClient,
    build_handout_outline_from_captions,
    current_outline_item,
    generate_handout_outline,
    get_configured_handout_outline_client,
    jump_target_for_outline_item,
    next_prefetch_outline_item,
    outline_leaf_items,
    outline_source_issues,
    outline_timeline_issues,
)


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


def test_build_handout_outline_from_captions_sorts_pending_items_and_keeps_sources():
    outline = build_handout_outline_from_captions(
        [
            {
                "segmentKey": "caption-3",
                "segmentType": "video_caption",
                "textContent": "第三段内容",
                "startSec": 80,
                "endSec": 120,
                "orderNo": 3,
            },
            {
                "segmentKey": "ignored-text",
                "segmentType": "text",
                "textContent": "不应进入视频目录",
                "startSec": 0,
                "endSec": 10,
            },
            {
                "segmentKey": "caption-1",
                "segmentType": "video_caption",
                "textContent": "第一段内容",
                "startSec": 0,
                "endSec": 30,
                "orderNo": 1,
            },
            {
                "segmentKey": "caption-2",
                "segmentType": "video_caption",
                "textContent": "第二段内容",
                "startSec": 31,
                "endSec": 45,
                "orderNo": 2,
            },
        ],
        max_block_duration_sec=60,
    )

    leaves = outline_leaf_items(outline["items"])
    assert [item["startSec"] for item in leaves] == [0, 80]
    assert [item["endSec"] for item in leaves] == [45, 120]
    assert [item["generationStatus"] for item in leaves] == ["pending", "pending"]
    assert leaves[0]["sourceSegmentKeys"] == ["caption-1", "caption-2"]
    assert leaves[1]["sourceSegmentKeys"] == ["caption-3"]
    assert outline["items"][0]["children"] == [leaves[0]]


def test_outline_timeline_issues_detects_invalid_timeline_and_accepts_valid_outline():
    valid_items = [
        _outline_section(
            "section-1",
            start_sec=0,
            end_sec=60,
            sort_no=1,
            children=[
                _outline_item("outline-1", start_sec=0, end_sec=30, sort_no=1),
                _outline_item("outline-2", start_sec=30, end_sec=60, sort_no=2),
            ],
        ),
    ]
    invalid_items = [
        _outline_section(
            "section-1",
            start_sec=0,
            end_sec=70,
            sort_no=1,
            children=[
                _outline_item("outline-1", start_sec=0, end_sec=40, sort_no=1),
                _outline_item("outline-1", start_sec=35, end_sec=70, sort_no=1),
            ],
        ),
    ]

    assert outline_timeline_issues(valid_items) == []
    assert outline_timeline_issues(invalid_items) == [
        "outline.key_duplicate",
        "outline.sort_not_increasing",
        "outline.time_overlap",
    ]


def test_outline_timeline_issues_detects_nested_overlaps():
    items = [
        _outline_section(
            "section-1",
            start_sec=0,
            end_sec=100,
            sort_no=1,
            children=[
                _outline_item("outline-1", start_sec=0, end_sec=100, sort_no=1),
                _outline_item("outline-2", start_sec=10, end_sec=20, sort_no=2),
                _outline_item("outline-3", start_sec=30, end_sec=40, sort_no=3),
            ],
        ),
    ]

    assert outline_timeline_issues(items) == [
        "outline.time_overlap",
        "outline.time_overlap",
    ]


def test_outline_timeline_issues_detects_nested_parent_mismatch_and_child_overlap():
    items = [
        {
            "outlineKey": "section-1",
            "title": "集合基础",
            "summary": "集合基础",
            "startSec": 0,
            "endSec": 80,
            "sortNo": 1,
            "children": [
                _outline_item("outline-1", start_sec=0, end_sec=50, sort_no=1),
                _outline_item("outline-2", start_sec=40, end_sec=70, sort_no=2),
            ],
        }
    ]

    assert outline_timeline_issues(items) == [
        "outline.time_overlap",
        "outline.parent_time_mismatch",
    ]


def test_outline_source_issues_rejects_unknown_sources_and_time_drift():
    captions = _caption_segments()

    assert outline_source_issues(
        [
            _outline_section(
                "section-1",
                start_sec=0,
                end_sec=30,
                sort_no=1,
                children=[
                    {
                        "outlineKey": "bad-source",
                        "startSec": 0,
                        "endSec": 30,
                        "sourceSegmentKeys": ["not-a-real-segment"],
                    },
                    {
                        "outlineKey": "bad-time",
                        "startSec": 1,
                        "endSec": 30,
                        "sourceSegmentKeys": ["mp4-c1"],
                    },
                ],
            ),
        ],
        captions,
    ) == ["outline.source_segment_unknown", "outline.source_time_mismatch"]


def test_current_outline_item_returns_active_item_and_includes_last_end_boundary():
    items = [
        {
            "outlineKey": "section-1",
            "title": "第一部分",
            "summary": "第一部分",
            "startSec": 0,
            "endSec": 60,
            "sortNo": 1,
            "children": [
                _outline_item("outline-1", start_sec=0, end_sec=30, sort_no=1),
                _outline_item("outline-2", start_sec=30, end_sec=60, sort_no=2),
            ],
        }
    ]

    assert current_outline_item(items, current_sec=15)["outlineKey"] == "outline-1"
    assert current_outline_item(items, current_sec=30)["outlineKey"] == "outline-2"
    assert current_outline_item(items, current_sec=60)["outlineKey"] == "outline-2"
    assert current_outline_item(items, current_sec=61) is None


def test_jump_target_for_outline_item_returns_timeline_locator():
    item = _outline_item("outline-1", start_sec=12, end_sec=34, sort_no=1)

    assert jump_target_for_outline_item(item) == {
        "outlineKey": "outline-1",
        "startSec": 12,
        "endSec": 34,
    }


def test_next_prefetch_outline_item_returns_next_pending_only_near_active_end():
    items = [
        {
            "outlineKey": "section-1",
            "title": "第一部分",
            "summary": "第一部分",
            "startSec": 0,
            "endSec": 180,
            "sortNo": 1,
            "children": [
                _outline_item("outline-1", start_sec=0, end_sec=60, sort_no=1, generation_status="ready"),
                _outline_item("outline-2", start_sec=60, end_sec=120, sort_no=2),
                _outline_item("outline-3", start_sec=120, end_sec=180, sort_no=3, generation_status="ready"),
            ],
        }
    ]

    assert next_prefetch_outline_item(items, current_sec=40, threshold_sec=15) is None
    assert next_prefetch_outline_item(items, current_sec=50, threshold_sec=15)["outlineKey"] == "outline-2"
    assert next_prefetch_outline_item(items, current_sec=110, threshold_sec=15) is None


def test_configured_handout_outline_client_requires_app_key(monkeypatch):
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)
    assert get_configured_handout_outline_client() is None

    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "fake-key")
    monkeypatch.setenv("KNOWLINK_VIVO_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("KNOWLINK_VIVO_OUTLINE_MODEL", "outline-model")
    monkeypatch.setenv("KNOWLINK_VIVO_HANDOUT_TIMEOUT_SEC", "9")

    assert isinstance(get_configured_handout_outline_client(), VivoHandoutOutlineClient)


def test_configured_handout_outline_client_supports_deepseek_provider(monkeypatch):
    monkeypatch.setenv("KNOWLINK_HANDOUT_OUTLINE_PROVIDER", "deepseek")
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    assert get_configured_handout_outline_client() is None

    monkeypatch.setenv("KNOWLINK_DEEPSEEK_API_KEY", "fake-deepseek-key")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_REASONING_EFFORT", "high")

    assert isinstance(get_configured_handout_outline_client(), DeepSeekHandoutOutlineClient)


def test_vivo_handout_outline_client_uses_ai_service_request_and_normalizes_model_output():
    model_payload = {
        "title": "集合论目录",
        "summary": "按时间线学习集合概念。",
        "items": [
            {
                "outlineKey": "set-concepts",
                "title": "集合概念",
                "summary": "理解集合和关系。",
                "startSec": 0,
                "endSec": 70,
                "sortNo": 1,
                "children": [
                    {
                        "outlineKey": "intro",
                        "title": "集合基础",
                        "summary": "认识集合。",
                        "startSec": 0,
                        "endSec": 30,
                        "sortNo": 1,
                        "generationStatus": "ready",
                        "sourceSegmentKeys": ["mp4-c1"],
                        "topicTags": ["集合", "集合"],
                    },
                    {
                        "outlineKey": "relation",
                        "title": "集合关系",
                        "summary": "理解包含关系。",
                        "startSec": 30,
                        "endSec": 70,
                        "sortNo": 2,
                        "generationStatus": "pending",
                        "sourceSegmentKeys": ["mp4-c2"],
                    },
                ],
            }
        ],
    }
    ai_service = FakeAIService(model_payload)
    client = VivoHandoutOutlineClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-mini",
        timeout_sec=7,
        ai_service=ai_service,
    )

    outline = client.generate_outline(_caption_segments(), title="集合论")

    request = ai_service.requests[0]
    assert request.provider == "vivo"
    assert request.model == "Doubao-Seed-2.0-mini"
    assert request.temperature == 0.1
    assert request.timeout_sec == 7
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 2048, "stream": False}
    assert "sourceSegmentKeys" in request.messages[0].content
    assert "video_caption segments" in request.messages[1].content
    assert outline == {
        "title": "集合论目录",
        "summary": "按时间线学习集合概念。",
        "items": [
            {
                "outlineKey": "set-concepts",
                "title": "集合概念",
                "summary": "理解集合和关系。",
                "startSec": 0,
                "endSec": 70,
                "sortNo": 1,
                "children": [
                    {
                        "outlineKey": "intro",
                        "title": "集合基础",
                        "summary": "认识集合。",
                        "startSec": 0,
                        "endSec": 30,
                        "sortNo": 1,
                        "generationStatus": "pending",
                        "sourceSegmentKeys": ["mp4-c1"],
                        "topicTags": ["集合"],
                    },
                    {
                        "outlineKey": "relation",
                        "title": "集合关系",
                        "summary": "理解包含关系。",
                        "startSec": 30,
                        "endSec": 70,
                        "sortNo": 2,
                        "generationStatus": "pending",
                        "sourceSegmentKeys": ["mp4-c2"],
                        "topicTags": [],
                    },
                ],
            },
        ],
    }


def test_deepseek_handout_outline_client_uses_ai_service_request():
    model_payload = {
        "title": "集合论目录",
        "summary": "按时间线学习集合概念。",
        "items": [
            {
                "outlineKey": "set-concepts",
                "title": "集合概念",
                "summary": "理解集合和关系。",
                "startSec": 0,
                "endSec": 70,
                "sortNo": 1,
                "children": [
                    {
                        "outlineKey": "intro",
                        "title": "集合基础",
                        "summary": "认识集合。",
                        "startSec": 0,
                        "endSec": 30,
                        "sortNo": 1,
                        "sourceSegmentKeys": ["mp4-c1"],
                    },
                    {
                        "outlineKey": "relation",
                        "title": "集合关系",
                        "summary": "理解包含关系。",
                        "startSec": 30,
                        "endSec": 70,
                        "sortNo": 2,
                        "sourceSegmentKeys": ["mp4-c2"],
                    },
                ],
            }
        ],
    }

    ai_service = FakeAIService(model_payload)
    client = DeepSeekHandoutOutlineClient(
        api_key="fake-deepseek-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        timeout_sec=7,
        ai_service=ai_service,
    )

    outline = client.generate_outline(_caption_segments(), title="集合论")

    request = ai_service.requests[0]
    assert request.provider == "deepseek"
    assert request.model == "deepseek-v4-flash"
    assert request.timeout_sec == 7
    assert request.response_format == {"type": "json_object"}
    assert request.metadata == {"max_tokens": 8192, "reasoning_effort": "high"}
    assert [message.role for message in request.messages] == ["system", "user"]
    assert outline["items"][0]["children"][0]["generationStatus"] == "pending"


def test_generate_handout_outline_falls_back_when_llm_fails():
    class FailingClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            raise RuntimeError("boom")

    result = generate_handout_outline(_caption_segments(), client=FailingClient(), title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.llm_failed", "outline.model_unavailable"]
    assert result.outline["title"] == "集合论"
    assert result.outline["items"][0]["children"][0]["sourceSegmentKeys"] == ["mp4-c1", "mp4-c2"]


def test_generate_handout_outline_maps_ai_provider_error_to_issue():
    client = VivoHandoutOutlineClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-mini",
        timeout_sec=7,
        ai_service=FakeAIService(error=AIProviderError("provider unavailable")),
    )

    result = generate_handout_outline(_caption_segments(), client=client, title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.llm_failed", "outline.model_provider_error"]


def test_generate_handout_outline_falls_back_when_llm_timeline_is_invalid():
    class InvalidTimelineClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            return {
                "title": "bad",
                "summary": "bad",
                "items": [
                    {
                        "outlineKey": "section-1",
                        "title": "非法分组",
                        "summary": "非法分组。",
                        "startSec": 0,
                        "endSec": 70,
                        "sortNo": 1,
                        "children": [
                            {
                                **_outline_item("outline-1", start_sec=0, end_sec=70, sort_no=1),
                                "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
                            },
                            {
                                **_outline_item("outline-2", start_sec=30, end_sec=70, sort_no=2),
                                "sourceSegmentKeys": ["mp4-c2"],
                            },
                        ],
                    },
                ],
            }

    result = generate_handout_outline(_caption_segments(), client=InvalidTimelineClient(), title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.time_overlap"]
    assert result.outline["items"][0]["children"][0]["generationStatus"] == "pending"


def test_generate_handout_outline_falls_back_when_llm_references_unknown_source():
    class UnknownSourceClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            return {
                "title": "bad",
                "summary": "bad",
                "items": [
                    {
                        "outlineKey": "section-1",
                        "title": "集合基础",
                        "summary": "集合基础。",
                        "startSec": 0,
                        "endSec": 30,
                        "sortNo": 1,
                        "children": [
                            {
                                **_outline_item("outline-1", start_sec=0, end_sec=30, sort_no=1),
                                "sourceSegmentKeys": ["missing-source"],
                            }
                        ],
                    }
                ],
            }

    result = generate_handout_outline(_caption_segments(), client=UnknownSourceClient(), title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.source_segment_unknown"]


def test_generate_handout_outline_falls_back_when_llm_returns_flat_outline():
    class FlatOutlineClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            return {
                "title": "flat",
                "summary": "flat",
                "items": [
                    {
                        "outlineKey": "outline-1",
                        "title": "集合基础",
                        "summary": "集合基础。",
                        "startSec": 0,
                        "endSec": 30,
                        "sortNo": 1,
                        "generationStatus": "pending",
                        "sourceSegmentKeys": ["mp4-c1"],
                    }
                ],
            }

    result = generate_handout_outline(_caption_segments(), client=FlatOutlineClient(), title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.parent_leaf_fields_present", "outline.children_missing"]
    assert "children" in result.outline["items"][0]


def test_generate_handout_outline_normalizes_injected_client_child_status_to_pending():
    class ReadyStatusClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            return {
                "title": "集合论",
                "summary": "集合论目录。",
                "items": [
                    {
                        "outlineKey": "section-1",
                        "title": "集合基础",
                        "summary": "集合基础。",
                        "startSec": 0,
                        "endSec": 70,
                        "sortNo": 1,
                        "children": [
                            {
                                "outlineKey": "outline-1",
                                "title": "集合定义",
                                "summary": "集合定义。",
                                "startSec": 0,
                                "endSec": 30,
                                "sortNo": 1,
                                "generationStatus": "ready",
                                "sourceSegmentKeys": ["mp4-c1"],
                            },
                            {
                                "outlineKey": "outline-2",
                                "title": "集合关系",
                                "summary": "集合关系。",
                                "startSec": 30,
                                "endSec": 70,
                                "sortNo": 2,
                                "generationStatus": "failed",
                                "sourceSegmentKeys": ["mp4-c2"],
                            },
                        ],
                    }
                ],
            }

    result = generate_handout_outline(_caption_segments(), client=ReadyStatusClient(), title="集合论")

    assert result.used_fallback is False
    assert [item["generationStatus"] for item in outline_leaf_items(result.outline["items"])] == [
        "pending",
        "pending",
    ]


def test_build_handout_outline_merges_overlapping_asr_segments_to_preserve_source_times():
    outline = build_handout_outline_from_captions(
        [
            {
                "segmentKey": "mp4-c1",
                "segmentType": "video_caption",
                "textContent": "第一段",
                "startSec": 0,
                "endSec": 61,
                "orderNo": 1,
            },
            {
                "segmentKey": "mp4-c2",
                "segmentType": "video_caption",
                "textContent": "第二段",
                "startSec": 60,
                "endSec": 120,
                "orderNo": 2,
            },
        ],
        max_block_duration_sec=60,
    )

    leaves = outline_leaf_items(outline["items"])
    assert len(leaves) == 1
    assert leaves[0]["startSec"] == 0
    assert leaves[0]["endSec"] == 120
    assert leaves[0]["sourceSegmentKeys"] == ["mp4-c1", "mp4-c2"]
    assert outline_timeline_issues(outline["items"]) == []


def test_build_handout_outline_uses_source_max_end_for_nested_asr_overlap():
    outline = build_handout_outline_from_captions(
        [
            {
                "segmentKey": "mp4-c1",
                "segmentType": "video_caption",
                "textContent": "长字幕",
                "startSec": 0,
                "endSec": 100,
                "orderNo": 1,
            },
            {
                "segmentKey": "mp4-c2",
                "segmentType": "video_caption",
                "textContent": "嵌套短字幕",
                "startSec": 10,
                "endSec": 20,
                "orderNo": 2,
            },
        ],
        max_block_duration_sec=60,
    )

    leaves = outline_leaf_items(outline["items"])
    assert len(leaves) == 1
    assert leaves[0]["startSec"] == 0
    assert leaves[0]["endSec"] == 100
    assert leaves[0]["sourceSegmentKeys"] == ["mp4-c1", "mp4-c2"]
    assert outline_source_issues(outline["items"], [
        {
            "segmentKey": "mp4-c1",
            "segmentType": "video_caption",
            "textContent": "长字幕",
            "startSec": 0,
            "endSec": 100,
            "orderNo": 1,
        },
        {
            "segmentKey": "mp4-c2",
            "segmentType": "video_caption",
            "textContent": "嵌套短字幕",
            "startSec": 10,
            "endSec": 20,
            "orderNo": 2,
        },
    ]) == []


def _caption_segments() -> list[dict[str, object]]:
    return [
        {
            "segmentKey": "mp4-c1",
            "segmentType": "video_caption",
            "textContent": "集合是对象组成的整体。",
            "startSec": 0,
            "endSec": 30,
            "orderNo": 1,
        },
        {
            "segmentKey": "mp4-c2",
            "segmentType": "video_caption",
            "textContent": "子集描述集合之间的包含关系。",
            "startSec": 30,
            "endSec": 70,
            "orderNo": 2,
        },
    ]


def _outline_item(
    outline_key: str,
    *,
    start_sec: int,
    end_sec: int,
    sort_no: int,
    generation_status: str = "pending",
) -> dict[str, object]:
    return {
        "outlineKey": outline_key,
        "title": outline_key,
        "summary": "",
        "startSec": start_sec,
        "endSec": end_sec,
        "sortNo": sort_no,
        "generationStatus": generation_status,
        "sourceSegmentKeys": [f"{outline_key}-caption"],
        "topicTags": [],
    }


def _outline_section(
    outline_key: str,
    *,
    start_sec: int,
    end_sec: int,
    sort_no: int,
    children: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "outlineKey": outline_key,
        "title": outline_key,
        "summary": outline_key,
        "startSec": start_sec,
        "endSec": end_sec,
        "sortNo": sort_no,
        "children": children,
    }
