import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from server.schemas.common import AsyncEntity


ROOT = Path(__file__).resolve().parents[2]


def load_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def build_validator(relative_path: str) -> Draft202012Validator:
    schema = load_json(relative_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_week1_freeze_docs_are_linked_from_readme_and_contract():
    readme = load_text("README.md")
    api_contract = load_text("docs/contracts/api-contract.md")

    assert "docs/contracts/week1-cao-le-freeze.md" in readme
    assert "docs/demo-assets-baseline.md" in readme
    assert "week1-cao-le-freeze.md" in api_contract
    assert "../demo-assets-baseline.md" in api_contract


def test_bilibili_reserved_contract_is_aligned_across_docs():
    architecture = load_text("ARCHITECTURE.md")
    api_contract = load_text("docs/contracts/api-contract.md")
    team_division = load_text("TEAM_DIVISION.md")
    freeze_doc = load_text("docs/contracts/week1-cao-le-freeze.md")
    error_codes = load_text("docs/contracts/error-codes.md")

    for text in (architecture, api_contract, team_division, freeze_doc):
        assert "/api/v1/courses/{courseId}/resources/imports/bilibili" in text
        assert "/api/v1/bilibili-import-runs/{importRunId}/status" in text
        assert "/api/v1/bilibili/auth/qr/sessions" in text

    assert "bilibili.not_implemented" in api_contract
    assert "bilibili.not_implemented" in freeze_doc
    assert "bilibili.not_implemented" in error_codes
    assert "B 站导入预留接口与扫码登录预留接口" in team_division


def test_bilibili_reserved_contract_sections_keep_request_body_and_delete_shape():
    api_contract = load_text("docs/contracts/api-contract.md")

    import_section = api_contract.split(
        "### `POST /api/v1/courses/{courseId}/resources/imports/bilibili`", 1
    )[1].split("### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`", 1)[0]
    delete_session_section = api_contract.split("### `DELETE /api/v1/bilibili/auth/session`", 1)[1].split(
        "当前未实现阶段统一返回：", 1
    )[0]

    assert '"videoUrl"' in import_section
    assert "`requestBody`" in import_section
    assert '"deleted": true' in delete_session_section
    assert '"answerCount"' not in delete_session_section


def test_demo_token_and_statuses_are_consistent_across_docs():
    architecture = load_text("ARCHITECTURE.md")
    api_contract = load_text("docs/contracts/api-contract.md")
    freeze_doc = load_text("docs/contracts/week1-cao-le-freeze.md")
    env_example = load_text(".env.example")

    texts = (architecture, api_contract, freeze_doc, env_example)
    for text in texts:
        assert "KNOWLINK_DEMO_TOKEN" in text

    lifecycle_statuses = (
        "draft",
        "resource_ready",
        "inquiry_ready",
        "learning_ready",
        "archived",
        "failed",
    )
    pipeline_stages = ("idle", "upload", "parse", "inquiry", "handout")
    pipeline_statuses = (
        "idle",
        "queued",
        "running",
        "partial_success",
        "succeeded",
        "failed",
    )
    async_task_statuses = (
        "queued",
        "running",
        "succeeded",
        "failed",
        "retrying",
        "canceled",
        "skipped",
    )

    for status in lifecycle_statuses + pipeline_stages + pipeline_statuses + async_task_statuses:
        assert f"`{status}`" in architecture
        assert f"`{status}`" in api_contract
        assert f"`{status}`" in freeze_doc

    assert "`bilibili_import_run`" in architecture
    assert "`bilibili_import_run`" in api_contract


def test_async_entity_accepts_bilibili_import_run():
    entity = AsyncEntity(type="bilibili_import_run", id=9101)
    assert entity.type == "bilibili_import_run"
    assert entity.id == 9101


def test_freeze_doc_tracks_seed_titles_and_fixed_manual_course_title():
    freeze_doc = load_text("docs/contracts/week1-cao-le-freeze.md")
    catalog = load_json("server/seeds/course_catalog.json")

    for item in catalog:
        assert item["title"] in freeze_doc

    assert "KnowLink 固定联调课" in freeze_doc


@pytest.mark.parametrize(
    ("schema_path", "payload"),
    [
        (
            "schemas/ai/handout_blocks.schema.json",
            {
                "title": "高数讲义",
                "summary": "固定联调版本",
                "blocks": [
                    {
                        "title": "PDF 引用块",
                        "summary": "含页码",
                        "contentMd": "content",
                        "estimatedMinutes": 10,
                        "knowledgePointIds": ["kp-1"],
                        "citations": [{"resourceId": 501, "refLabel": "PDF 第 2 页", "pageNo": 2}],
                    },
                    {
                        "title": "PPTX 引用块",
                        "summary": "含 slide",
                        "contentMd": "content",
                        "estimatedMinutes": 8,
                        "knowledgePointIds": ["kp-2"],
                        "citations": [{"resourceId": 502, "refLabel": "PPT 第 6 页", "slideNo": 6}],
                    },
                    {
                        "title": "DOCX 引用块",
                        "summary": "含 anchor",
                        "contentMd": "content",
                        "estimatedMinutes": 6,
                        "knowledgePointIds": ["kp-3"],
                        "citations": [{"resourceId": 503, "refLabel": "DOCX 积分部分", "anchorKey": "section-integral"}],
                    },
                    {
                        "title": "视频引用块",
                        "summary": "含时间",
                        "contentMd": "content",
                        "estimatedMinutes": 12,
                        "knowledgePointIds": ["kp-4"],
                        "citations": [
                            {
                                "resourceId": 504,
                                "refLabel": "视频 02:00-04:00",
                                "startSec": 120,
                                "endSec": 240,
                            }
                        ],
                    },
                ],
            },
        ),
        (
            "schemas/ai/qa_response.schema.json",
            {
                "answerMd": "回答内容",
                "answerType": "direct_answer",
                "citations": [
                    {"resourceId": 501, "refLabel": "PDF 第 2 页", "pageNo": 2},
                    {"resourceId": 502, "refLabel": "PPT 第 6 页", "slideNo": 6},
                    {"resourceId": 503, "refLabel": "DOCX 积分部分", "anchorKey": "section-integral"},
                    {"resourceId": 504, "refLabel": "视频 02:00-04:00", "startSec": 120, "endSec": 240},
                ],
            },
        ),
    ],
)
def test_citation_schemas_accept_all_reference_types(schema_path: str, payload: dict):
    build_validator(schema_path).validate(payload)


@pytest.mark.parametrize(
    ("schema_path", "payload"),
    [
        (
            "schemas/ai/handout_blocks.schema.json",
            {
                "title": "bad",
                "summary": "bad",
                "blocks": [
                    {
                        "title": "bad",
                        "summary": "bad",
                        "contentMd": "content",
                        "estimatedMinutes": 5,
                        "knowledgePointIds": ["kp-1"],
                        "citations": [{"refLabel": "缺 resourceId"}],
                    }
                ],
            },
        ),
        (
            "schemas/ai/qa_response.schema.json",
            {
                "answerMd": "bad",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 1, "refLabel": "bad", "unknownField": True}],
            },
        ),
    ],
)
def test_citation_schemas_reject_missing_required_or_unknown_fields(schema_path: str, payload: dict):
    with pytest.raises(ValidationError):
        build_validator(schema_path).validate(payload)


@pytest.mark.parametrize(
    ("schema_path", "payload"),
    [
        (
            "schemas/ai/handout_blocks.schema.json",
            {
                "title": "bad",
                "summary": "bad",
                "blocks": [
                    {
                        "title": "bad",
                        "summary": "bad",
                        "contentMd": "content",
                        "estimatedMinutes": 5,
                        "knowledgePointIds": ["kp-1"],
                        "citations": [{"resourceId": 1, "refLabel": "缺定位"}],
                    }
                ],
            },
        ),
        (
            "schemas/ai/handout_blocks.schema.json",
            {
                "title": "bad",
                "summary": "bad",
                "blocks": [
                    {
                        "title": "bad",
                        "summary": "bad",
                        "contentMd": "content",
                        "estimatedMinutes": 5,
                        "knowledgePointIds": ["kp-1"],
                        "citations": [{"resourceId": 1, "refLabel": "混合定位", "pageNo": 2, "slideNo": 6}],
                    }
                ],
            },
        ),
        (
            "schemas/ai/handout_blocks.schema.json",
            {
                "title": "bad",
                "summary": "bad",
                "blocks": [
                    {
                        "title": "bad",
                        "summary": "bad",
                        "contentMd": "content",
                        "estimatedMinutes": 5,
                        "knowledgePointIds": ["kp-1"],
                        "citations": [{"resourceId": 1, "refLabel": "文档混入视频", "anchorKey": "sec-1", "startSec": 30}],
                    }
                ],
            },
        ),
        (
            "schemas/ai/handout_blocks.schema.json",
            {
                "title": "bad",
                "summary": "bad",
                "blocks": [
                    {
                        "title": "bad",
                        "summary": "bad",
                        "contentMd": "content",
                        "estimatedMinutes": 5,
                        "knowledgePointIds": ["kp-1"],
                        "citations": [{"resourceId": 1, "refLabel": "视频缺结束时间", "startSec": 30}],
                    }
                ],
            },
        ),
        (
            "schemas/ai/qa_response.schema.json",
            {
                "answerMd": "bad",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 1, "refLabel": "缺定位"}],
            },
        ),
        (
            "schemas/ai/qa_response.schema.json",
            {
                "answerMd": "bad",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 1, "refLabel": "混合定位", "pageNo": 2, "slideNo": 6}],
            },
        ),
        (
            "schemas/ai/qa_response.schema.json",
            {
                "answerMd": "bad",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 1, "refLabel": "文档混入视频", "anchorKey": "sec-1", "startSec": 30}],
            },
        ),
        (
            "schemas/ai/qa_response.schema.json",
            {
                "answerMd": "bad",
                "answerType": "direct_answer",
                "citations": [{"resourceId": 1, "refLabel": "视频缺开始时间", "endSec": 30}],
            },
        ),
    ],
)
def test_citation_schemas_reject_missing_or_mixed_locator_fields(schema_path: str, payload: dict):
    with pytest.raises(ValidationError):
        build_validator(schema_path).validate(payload)


def test_normalized_document_schema_enforces_resource_specific_locations():
    validator = build_validator("schemas/parse/normalized_document.schema.json")

    valid_payloads = [
        {
            "resourceType": "pdf",
            "segments": [{"segmentType": "pdf_text", "orderNo": 1, "textContent": "limit", "pageNo": 2}],
        },
        {
            "resourceType": "pptx",
            "segments": [{"segmentType": "slide_text", "orderNo": 1, "textContent": "matrix", "slideNo": 6}],
        },
        {
            "resourceType": "docx",
            "segments": [
                {
                    "segmentType": "doc_paragraph",
                    "orderNo": 1,
                    "textContent": "integral",
                    "anchorKey": "section-integral",
                }
            ],
        },
        {
            "resourceType": "mp4",
            "segments": [
                {
                    "segmentType": "video_transcript",
                    "orderNo": 1,
                    "textContent": "video",
                    "startSec": 0,
                    "endSec": 30,
                }
            ],
        },
        {
            "resourceType": "srt",
            "segments": [
                {
                    "segmentType": "video_transcript",
                    "orderNo": 1,
                    "textContent": "subtitle",
                    "startSec": 30,
                    "endSec": 45,
                }
            ],
        },
    ]

    invalid_payloads = [
        {
            "resourceType": "pdf",
            "segments": [{"segmentType": "pdf_text", "orderNo": 1, "textContent": "limit", "anchorKey": "bad"}],
        },
        {
            "resourceType": "pdf",
            "segments": [{"segmentType": "pdf_text", "orderNo": 1, "textContent": "limit", "startSec": 10}],
        },
        {
            "resourceType": "pptx",
            "segments": [{"segmentType": "slide_text", "orderNo": 1, "textContent": "matrix", "pageNo": 2}],
        },
        {
            "resourceType": "docx",
            "segments": [{"segmentType": "doc_paragraph", "orderNo": 1, "textContent": "integral", "slideNo": 6}],
        },
        {
            "resourceType": "mp4",
            "segments": [{"segmentType": "video_transcript", "orderNo": 1, "textContent": "video", "pageNo": 2}],
        },
        {
            "resourceType": "mp4",
            "segments": [{"segmentType": "video_transcript", "orderNo": 1, "textContent": "video", "startSec": 0}],
        },
        {
            "resourceType": "srt",
            "segments": [{"segmentType": "video_transcript", "orderNo": 1, "textContent": "subtitle", "endSec": 45}],
        },
    ]

    for payload in valid_payloads:
        validator.validate(payload)

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            validator.validate(payload)


def test_demo_asset_baseline_covers_fixed_joint_test_set():
    baseline_doc = load_text("docs/demo-assets-baseline.md")

    for token in ("knowlink-demo-main.mp4", "knowlink-demo-handout.pdf", "knowlink-demo-slides.pptx", "knowlink-demo-notes.docx"):
        assert token in baseline_doc

    assert "sha256:<hex>" in baseline_doc
    assert "不在仓库中提交任何演示二进制文件" in baseline_doc
