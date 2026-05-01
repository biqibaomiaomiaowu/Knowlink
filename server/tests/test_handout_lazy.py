import json

from server.ai.handout_lazy import (
    VivoHandoutOutlineClient,
    build_handout_outline_from_captions,
    current_outline_item,
    generate_handout_outline,
    get_configured_handout_outline_client,
    jump_target_for_outline_item,
    next_prefetch_outline_item,
    outline_timeline_issues,
)


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

    assert [item["startSec"] for item in outline["items"]] == [0, 80]
    assert [item["endSec"] for item in outline["items"]] == [45, 120]
    assert [item["generationStatus"] for item in outline["items"]] == ["pending", "pending"]
    assert outline["items"][0]["sourceSegmentKeys"] == ["caption-1", "caption-2"]
    assert outline["items"][1]["sourceSegmentKeys"] == ["caption-3"]


def test_outline_timeline_issues_detects_invalid_timeline_and_accepts_valid_outline():
    valid_items = [
        _outline_item("outline-1", start_sec=0, end_sec=30, sort_no=1),
        _outline_item("outline-2", start_sec=30, end_sec=60, sort_no=2),
    ]
    invalid_items = [
        _outline_item("outline-1", start_sec=0, end_sec=40, sort_no=1),
        _outline_item("outline-1", start_sec=35, end_sec=70, sort_no=1),
    ]

    assert outline_timeline_issues(valid_items) == []
    assert outline_timeline_issues(invalid_items) == [
        "outline.key_duplicate",
        "outline.sort_not_increasing",
        "outline.time_overlap",
    ]


def test_outline_timeline_issues_detects_nested_overlaps():
    items = [
        _outline_item("outline-1", start_sec=0, end_sec=100, sort_no=1),
        _outline_item("outline-2", start_sec=10, end_sec=20, sort_no=2),
        _outline_item("outline-3", start_sec=30, end_sec=40, sort_no=3),
    ]

    assert outline_timeline_issues(items) == [
        "outline.time_overlap",
        "outline.time_overlap",
    ]


def test_current_outline_item_returns_active_item_and_includes_last_end_boundary():
    items = [
        _outline_item("outline-1", start_sec=0, end_sec=30, sort_no=1),
        _outline_item("outline-2", start_sec=30, end_sec=60, sort_no=2),
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
        _outline_item("outline-1", start_sec=0, end_sec=60, sort_no=1, generation_status="ready"),
        _outline_item("outline-2", start_sec=60, end_sec=120, sort_no=2),
        _outline_item("outline-3", start_sec=120, end_sec=180, sort_no=3, generation_status="ready"),
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


def test_vivo_handout_outline_client_uses_chat_completions_and_normalizes_model_output(monkeypatch):
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
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "```json\n"
                                        + json.dumps(
                                            {
                                                "title": "集合论目录",
                                                "summary": "按时间线学习集合概念。",
                                                "items": [
                                                    {
                                                        "outlineKey": "intro",
                                                        "title": "集合基础",
                                                        "summary": "认识集合。",
                                                        "startSec": 99,
                                                        "endSec": 100,
                                                        "sortNo": 9,
                                                        "generationStatus": "ready",
                                                        "sourceSegmentKeys": ["mp4-c1", "unknown"],
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
                                            },
                                            ensure_ascii=False,
                                        )
                                        + "\n```",
                                    }
                                ],
                            }
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = VivoHandoutOutlineClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="Doubao-Seed-2.0-mini",
        timeout_sec=7,
    )

    outline = client.generate_outline(_caption_segments(), title="集合论")

    body = json.loads(captured["body"])
    assert captured["url"].startswith("https://example.invalid/v1/chat/completions?request_id=")
    assert captured["headers"]["Authorization"] == "Bearer fake-key"
    assert captured["headers"]["Content-type"] == "application/json; charset=utf-8"
    assert captured["timeout"] == 7
    assert body["model"] == "Doubao-Seed-2.0-mini"
    assert body["temperature"] == 0.1
    assert body["stream"] is False
    assert "sourceSegmentKeys" in body["messages"][0]["content"]
    assert "video_caption segments" in body["messages"][1]["content"]
    assert outline == {
        "title": "集合论目录",
        "summary": "按时间线学习集合概念。",
        "items": [
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
    }


def test_generate_handout_outline_falls_back_when_llm_fails():
    class FailingClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            raise RuntimeError("boom")

    result = generate_handout_outline(_caption_segments(), client=FailingClient(), title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.llm_failed"]
    assert result.outline["title"] == "集合论"
    assert result.outline["items"][0]["sourceSegmentKeys"] == ["mp4-c1", "mp4-c2"]


def test_generate_handout_outline_falls_back_when_llm_timeline_is_invalid():
    class InvalidTimelineClient:
        def generate_outline(self, caption_segments, *, title, summary, document_context=None):
            return {
                "title": "bad",
                "summary": "bad",
                "items": [
                    _outline_item("outline-1", start_sec=0, end_sec=40, sort_no=1),
                    _outline_item("outline-2", start_sec=35, end_sec=70, sort_no=2),
                ],
            }

    result = generate_handout_outline(_caption_segments(), client=InvalidTimelineClient(), title="集合论")

    assert result.used_fallback is True
    assert result.issues == ["outline.time_overlap"]
    assert result.outline["items"][0]["generationStatus"] == "pending"


def test_build_handout_outline_normalizes_small_asr_overlaps_between_blocks():
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

    assert outline["items"][0]["endSec"] == 61
    assert outline["items"][1]["startSec"] == 61
    assert outline_timeline_issues(outline["items"]) == []


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
