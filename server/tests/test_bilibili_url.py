from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.infra.bilibili.models import BilibiliPart, BilibiliPreview, BilibiliSourceType
from server.infra.bilibili.url import BilibiliUrlKind, parse_bilibili_url
from server.schemas.requests import BilibiliImportRequest, BilibiliPreviewRequest
from server.schemas.responses import (
    BilibiliImportRunStatusData,
    BilibiliPreviewData,
    BilibiliPreviewPart,
)


@pytest.mark.parametrize(
    ("url", "kind", "expected"),
    [
        (
            "https://www.bilibili.com/video/BV1xx411c7mD/",
            BilibiliUrlKind.SINGLE_VIDEO,
            {"bvid": "BV1xx411c7mD", "page_no": None},
        ),
        (
            "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
            BilibiliUrlKind.MULTI_P,
            {"bvid": "BV1xx411c7mD", "page_no": 2},
        ),
        (
            "https://space.bilibili.com/123/channel/collectiondetail?sid=456",
            BilibiliUrlKind.COLLECTION,
            {"collection_id": "456"},
        ),
        (
            "https://www.bilibili.com/bangumi/play/ep123456",
            BilibiliUrlKind.BANGUMI,
            {"episode_id": "ep123456"},
        ),
        (
            "https://b23.tv/BV1xx411c7mD",
            BilibiliUrlKind.SHORT,
            {"bvid": "BV1xx411c7mD"},
        ),
    ],
)
def test_parse_bilibili_url_supported_cases(url: str, kind: BilibiliUrlKind, expected: dict[str, object]):
    parsed = parse_bilibili_url(url)

    assert parsed.original_url == url
    assert parsed.kind == kind
    for key, value in expected.items():
        assert getattr(parsed, key) == value


def test_short_url_kind_is_not_exposed_as_source_type():
    parsed = parse_bilibili_url("https://b23.tv/BV1xx411c7mD")

    assert parsed.kind == BilibiliUrlKind.SHORT
    assert BilibiliUrlKind.SHORT.value not in {item.value for item in BilibiliSourceType}


def test_parse_bilibili_url_rejects_non_bilibili_url():
    with pytest.raises(ValueError, match="unsupported Bilibili URL"):
        parse_bilibili_url("https://example.com/video/BV1xx411c7mD")


def test_bilibili_preview_and_import_requests_accept_camel_aliases_and_clean_selected_parts():
    preview = BilibiliPreviewRequest(sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD/")
    payload = BilibiliImportRequest(
        previewId="preview-1",
        sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD?p=2",
        selectionMode="selected_parts",
        selectedPartIds=[" p1 ", "", "p2"],
        qualityPreference="android_safe",
    )

    assert preview.source_url == "https://www.bilibili.com/video/BV1xx411c7mD/"
    assert payload.preview_id == "preview-1"
    assert payload.source_url == "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
    assert payload.selection_mode == "selected_parts"
    assert payload.selected_part_ids == ["p1", "p2"]
    assert payload.model_dump(by_alias=True)["previewId"] == "preview-1"


def test_bilibili_import_request_requires_preview_id_and_selected_parts_for_selected_mode():
    with pytest.raises(ValidationError):
        BilibiliImportRequest(sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD/")

    with pytest.raises(ValidationError):
        BilibiliImportRequest(
            previewId="preview-1",
            sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD/",
            selectionMode="selected_parts",
            selectedPartIds=[" ", ""],
        )


def test_bilibili_response_dtos_dump_contract_camel_case_without_legacy_fields():
    preview = BilibiliPreviewData(
        previewId="bili_preview_9101",
        sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD?p=2",
        sourceType="single_video",
        title="demo",
        coverUrl=None,
        totalParts=1,
        parts=[
            BilibiliPreviewPart(
                partId="p1",
                title="P1",
                durationSec=120,
                cid=1001,
                pageNo=1,
                selectedByDefault=True,
            )
        ],
        defaultSelectionMode="current_part",
    )
    status = BilibiliImportRunStatusData(
        importRunId=9101,
        courseId=101,
        sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD?p=2",
        sourceType="single_video",
        status="downloading",
        progressPct=42,
        stage="download",
        taskId=7201,
        resourceIds=[301, 302],
        preview=preview,
        nextAction="poll",
        errorCode=None,
        failureReason=None,
        recoverable=False,
    )

    dumped = status.model_dump(by_alias=True)

    assert dumped["sourceType"] == "single_video"
    assert dumped["progressPct"] == 42
    assert dumped["stage"] == "download"
    assert dumped["resourceIds"] == [301, 302]
    assert dumped["preview"]["parts"][0]["cid"] == 1001
    assert dumped["preview"]["parts"][0]["selectedByDefault"] is True
    assert "videoUrl" not in dumped
    assert "resourceId" not in dumped


def test_bilibili_import_run_status_rejects_invalid_and_british_cancelled_statuses():
    base_payload = {
        "importRunId": 9101,
        "courseId": 101,
        "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
        "sourceType": "single_video",
        "progressPct": 42,
        "stage": "download",
    }

    with pytest.raises(ValidationError):
        BilibiliImportRunStatusData(status="queued", **base_payload)

    with pytest.raises(ValidationError):
        BilibiliImportRunStatusData(status="cancelled", **base_payload)


def test_bilibili_runtime_models_emit_contract_camel_case_and_source_type_excludes_short():
    assert {item.value for item in BilibiliSourceType} == {
        "single_video",
        "multi_p",
        "collection",
        "bangumi",
    }
    preview = BilibiliPreview(
        preview_id="preview-1",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD/",
        source_type=BilibiliSourceType.SINGLE_VIDEO,
        title="demo",
        cover_url=None,
        total_parts=1,
        parts=[
            BilibiliPart(
                part_id="p1",
                title="P1",
                duration_sec=120,
                cid=1001,
                page_no=1,
                selected_by_default=True,
            )
        ],
        default_selection_mode="current_part",
    )

    assert preview.to_api() == {
        "previewId": "preview-1",
        "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD/",
        "sourceType": "single_video",
        "title": "demo",
        "coverUrl": None,
        "totalParts": 1,
        "parts": [
            {
                "partId": "p1",
                "title": "P1",
                "durationSec": 120,
                "cid": 1001,
                "pageNo": 1,
                "selectedByDefault": True,
            }
        ],
        "defaultSelectionMode": "current_part",
    }


def test_bilibili_contract_enum_guards_reject_invalid_values():
    with pytest.raises(ValidationError):
        BilibiliImportRequest(
            previewId="preview-1",
            sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD/",
            qualityPreference="dash",
        )

    with pytest.raises(ValidationError):
        BilibiliImportRequest(
            previewId="preview-1",
            sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD/",
            selectionMode="first_part",
        )
