import json
import re
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
    assert "docs/demo-assets-first-edition.md" in readme
    assert "week1-cao-le-freeze.md" in api_contract
    assert "../demo-assets-baseline.md" in api_contract


def test_week2_parse_inquiry_contract_is_linked_from_api_contract():
    api_contract = load_text("docs/contracts/api-contract.md")
    week2_contract = load_text("docs/contracts/week2-cao-le-parse-inquiry-contract.md")

    assert "week2-cao-le-parse-inquiry-contract.md" in api_contract
    assert "schemas/ai/knowledge_point_extraction.schema.json" in week2_contract
    assert "schemas/parse/normalized_document.schema.json" in week2_contract

    for token in (
        "`course_segments`",
        "`knowledge_points`",
        "`segment_knowledge_points`",
        "`knowledge_point_evidences`",
        "`vector_documents`",
        "`learning_preferences`",
    ):
        assert token in week2_contract

    for step_code in ("resource_validate", "caption_extract", "document_parse", "knowledge_extract", "vectorize"):
        assert step_code in api_contract
        assert step_code in week2_contract


def test_normalized_document_segment_types_match_week2_contract():
    week2_contract = load_text("docs/contracts/week2-cao-le-parse-inquiry-contract.md")
    schema = load_json("schemas/parse/normalized_document.schema.json")
    expected_segment_types = {
        "video_caption",
        "pdf_page_text",
        "ppt_slide_text",
        "docx_block_text",
        "ocr_text",
        "formula",
        "image_caption",
    }

    schema_segment_types = set(schema["properties"]["segments"]["items"]["properties"]["segmentType"]["enum"])
    assert schema_segment_types == expected_segment_types

    for segment_type in expected_segment_types:
        assert f"`{segment_type}`" in week2_contract


def test_parse_contract_documents_quality_gate_and_vision_env_vars():
    week2_contract = load_text("docs/contracts/week2-cao-le-parse-inquiry-contract.md")

    for token in (
        "U+FFFF",
        "U+FFFD",
        "KNOWLINK_ENABLE_MARKITDOWN_OCR",
        "KNOWLINK_VIVO_APP_KEY",
        "KNOWLINK_VIVO_BASE_URL",
        "KNOWLINK_VIVO_VISION_MODEL",
    ):
        assert token in week2_contract


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


def test_bilibili_stub_owner_is_consistent_across_collaboration_docs():
    freeze_doc = load_text("docs/contracts/week1-cao-le-freeze.md")
    team_division = load_text("TEAM_DIVISION.md")
    weekly_plan = load_text("WEEKLY_PLAN.md")

    assert "由曹乐在第 2 周完成 stub 实现" not in freeze_doc
    assert "杨彩艺" in freeze_doc
    assert "`501` stub" in freeze_doc
    assert "接口主负责人是杨彩艺" in team_division
    assert "第 2 周由杨彩艺按冻结结果补当前 `501` stub" in team_division
    assert "当前阶段统一返回 `501`" in weekly_plan
    assert "由曹乐在第 2 周完成 stub 实现" not in weekly_plan


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


def test_collaboration_docs_expose_change_flow_and_priority_matrices():
    readme = load_text("README.md")
    team_division = load_text("TEAM_DIVISION.md")
    scaffold = load_text("docs/development-scaffold.md")

    assert "文档优先级矩阵" in readme
    assert "api-contract.md" in readme
    assert "ARCHITECTURE.md" in readme
    assert "TEAM_DIVISION.md" in readme

    assert "Schema / Contract 变更流程" in team_division
    assert "文档优先级矩阵" in team_division
    assert "当前完成度矩阵" in scaffold


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


@pytest.mark.parametrize(
    ("schema_path", "payload"),
    [
        (
            "schemas/ai/quiz_generation.schema.json",
            {
                "quizType": "exam_drill",
                "questions": [
                    {
                        "stemMd": "1+1=?",
                        "options": ["1", "2"],
                        "correctAnswer": "2",
                        "explanationMd": "基础算术。",
                        "difficultyLevel": "easy",
                    }
                ],
            },
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {
                "tasks": [
                    {
                        "taskType": "redo_quiz",
                        "priorityScore": 80,
                        "reasonText": "错题集中。",
                        "recommendedMinutes": 15,
                    }
                ],
            },
        ),
    ],
)
def test_quiz_and_review_schemas_accept_valid_payloads(schema_path: str, payload: dict):
    build_validator(schema_path).validate(payload)


@pytest.mark.parametrize(
    ("schema_path", "payload"),
    [
        (
            "schemas/ai/quiz_generation.schema.json",
            {"quizType": "exam_drill"},
        ),
        (
            "schemas/ai/quiz_generation.schema.json",
            {"quizType": "exam_drill", "questions": []},
        ),
        (
            "schemas/ai/quiz_generation.schema.json",
            {
                "quizType": "exam_drill",
                "questions": [
                    {
                        "stemMd": "题干",
                        "options": ["A", "B"],
                        "correctAnswer": "A",
                        "explanationMd": "解释",
                        "difficultyLevel": "expert",
                    }
                ],
            },
        ),
        (
            "schemas/ai/quiz_generation.schema.json",
            {
                "quizType": "exam_drill",
                "questions": [
                    {
                        "stemMd": "题干",
                        "options": ["A", "B"],
                        "correctAnswer": "A",
                        "explanationMd": "解释",
                        "difficultyLevel": "easy",
                        "questionType": "single_choice",
                    }
                ],
            },
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {},
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {"tasks": []},
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {
                "tasks": [
                    {
                        "taskType": "memorize",
                        "priorityScore": 80,
                        "reasonText": "原因",
                        "recommendedMinutes": 15,
                    }
                ]
            },
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {
                "tasks": [
                    {
                        "taskType": "redo_quiz",
                        "priorityScore": 101,
                        "reasonText": "原因",
                        "recommendedMinutes": 15,
                    }
                ]
            },
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {
                "tasks": [
                    {
                        "taskType": "redo_quiz",
                        "priorityScore": 80,
                        "reasonText": "原因",
                        "recommendedMinutes": 0,
                    }
                ]
            },
        ),
        (
            "schemas/ai/review_tasks.schema.json",
            {
                "tasks": [
                    {
                        "taskType": "redo_quiz",
                        "priorityScore": 80,
                        "reasonText": "原因",
                        "recommendedMinutes": 15,
                        "intensity": "high",
                    }
                ]
            },
        ),
    ],
)
def test_quiz_and_review_schemas_reject_invalid_payloads(schema_path: str, payload: dict):
    with pytest.raises(ValidationError):
        build_validator(schema_path).validate(payload)


def assert_knowledge_extraction_references_are_declared(payload: dict, known_segment_keys: set[str]) -> None:
    knowledge_point_keys = {item["knowledgePointKey"] for item in payload["knowledgePoints"]}

    for relation in payload["segmentKnowledgePoints"]:
        assert relation["segmentKey"] in known_segment_keys
        assert relation["knowledgePointKey"] in knowledge_point_keys

    for evidence in payload["knowledgePointEvidences"]:
        assert evidence["segmentKey"] in known_segment_keys
        assert evidence["knowledgePointKey"] in knowledge_point_keys


def test_knowledge_point_extraction_schema_accepts_valid_payload():
    payload = {
        "knowledgePoints": [
            {
                "knowledgePointKey": "kp-limit",
                "displayName": "函数极限",
                "canonicalName": "function_limit",
                "description": "函数在自变量趋近某点时的稳定趋势。",
                "difficultyLevel": "intermediate",
                "importanceScore": 92,
                "aliases": ["极限", "limit"],
                "sortNo": 1,
            }
        ],
        "segmentKnowledgePoints": [
            {
                "segmentKey": "seg-pdf-1",
                "knowledgePointKey": "kp-limit",
                "relevanceScore": 0.92,
                "sortNo": 1,
            }
        ],
        "knowledgePointEvidences": [
            {
                "segmentKey": "seg-pdf-1",
                "knowledgePointKey": "kp-limit",
                "evidenceType": "definition",
                "pageNo": 2,
                "sortNo": 1,
            }
        ],
    }

    build_validator("schemas/ai/knowledge_point_extraction.schema.json").validate(payload)
    assert_knowledge_extraction_references_are_declared(payload, {"seg-pdf-1"})


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "knowledgePoints": [],
            "segmentKnowledgePoints": [],
            "knowledgePointEvidences": [],
        },
        {
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "canonicalName": "function_limit",
                    "description": "函数在自变量趋近某点时的稳定趋势。",
                    "difficultyLevel": "medium",
                    "importanceScore": 92,
                    "aliases": [],
                    "sortNo": 1,
                }
            ],
            "segmentKnowledgePoints": [],
            "knowledgePointEvidences": [],
        },
        {
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "canonicalName": "function_limit",
                    "description": "函数在自变量趋近某点时的稳定趋势。",
                    "difficultyLevel": "intermediate",
                    "importanceScore": 92,
                    "aliases": [],
                    "sortNo": 1,
                    "unexpected": True,
                }
            ],
            "segmentKnowledgePoints": [],
            "knowledgePointEvidences": [],
        },
        {
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "canonicalName": "function_limit",
                    "description": "函数在自变量趋近某点时的稳定趋势。",
                    "difficultyLevel": "intermediate",
                    "importanceScore": 92,
                    "aliases": [],
                    "sortNo": 1,
                }
            ],
            "segmentKnowledgePoints": [
                {
                    "segmentKey": "seg-pdf-1",
                    "knowledgePointKey": "kp-limit",
                    "relevanceScore": 1.1,
                    "sortNo": 1,
                }
            ],
            "knowledgePointEvidences": [],
        },
        {
            "knowledgePoints": [
                {
                    "knowledgePointKey": "kp-limit",
                    "displayName": "函数极限",
                    "canonicalName": "function_limit",
                    "description": "函数在自变量趋近某点时的稳定趋势。",
                    "difficultyLevel": "intermediate",
                    "importanceScore": 92,
                    "aliases": [],
                    "sortNo": 1,
                }
            ],
            "segmentKnowledgePoints": [],
            "knowledgePointEvidences": [
                {
                    "segmentKey": "seg-pdf-1",
                    "knowledgePointKey": "kp-limit",
                    "evidenceType": "definition",
                    "pageNo": 2,
                    "slideNo": 3,
                    "sortNo": 1,
                }
            ],
        },
    ],
)
def test_knowledge_point_extraction_schema_rejects_invalid_payloads(payload: dict):
    with pytest.raises(ValidationError):
        build_validator("schemas/ai/knowledge_point_extraction.schema.json").validate(payload)


def test_knowledge_point_extraction_references_must_be_declared():
    payload = {
        "knowledgePoints": [
            {
                "knowledgePointKey": "kp-limit",
                "displayName": "函数极限",
                "canonicalName": "function_limit",
                "description": "函数在自变量趋近某点时的稳定趋势。",
                "difficultyLevel": "intermediate",
                "importanceScore": 92,
                "aliases": [],
                "sortNo": 1,
            }
        ],
        "segmentKnowledgePoints": [
            {
                "segmentKey": "seg-missing",
                "knowledgePointKey": "kp-missing",
                "relevanceScore": 0.9,
                "sortNo": 1,
            }
        ],
        "knowledgePointEvidences": [
            {
                "segmentKey": "seg-missing",
                "knowledgePointKey": "kp-limit",
                "evidenceType": "definition",
                "pageNo": 2,
                "sortNo": 1,
            }
        ],
    }

    build_validator("schemas/ai/knowledge_point_extraction.schema.json").validate(payload)
    with pytest.raises(AssertionError):
        assert_knowledge_extraction_references_are_declared(payload, {"seg-pdf-1"})


def test_normalized_document_schema_enforces_resource_specific_locations():
    validator = build_validator("schemas/parse/normalized_document.schema.json")

    valid_payloads = [
        {
            "resourceType": "pdf",
            "segments": [
                {
                    "segmentKey": "seg-pdf-1",
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "limit",
                    "pageNo": 2,
                }
            ],
        },
        {
            "resourceType": "pptx",
            "segments": [
                {
                    "segmentKey": "seg-pptx-1",
                    "segmentType": "ppt_slide_text",
                    "orderNo": 1,
                    "textContent": "matrix",
                    "slideNo": 6,
                }
            ],
        },
        {
            "resourceType": "docx",
            "segments": [
                {
                    "segmentKey": "seg-docx-1",
                    "segmentType": "docx_block_text",
                    "orderNo": 1,
                    "textContent": "integral",
                    "sectionPath": ["第 1 章", "积分"],
                    "anchorKey": "section-integral",
                }
            ],
        },
        {
            "resourceType": "mp4",
            "segments": [
                {
                    "segmentKey": "seg-video-1",
                    "segmentType": "video_caption",
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
                    "segmentKey": "seg-srt-1",
                    "segmentType": "video_caption",
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
            "segments": [
                {
                    "segmentKey": "seg-pdf-bad-1",
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "limit",
                    "anchorKey": "bad",
                }
            ],
        },
        {
            "resourceType": "pdf",
            "segments": [
                {
                    "segmentKey": "seg-pdf-bad-2",
                    "segmentType": "pdf_page_text",
                    "orderNo": 1,
                    "textContent": "limit",
                    "startSec": 10,
                }
            ],
        },
        {
            "resourceType": "pptx",
            "segments": [
                {
                    "segmentKey": "seg-pptx-bad-1",
                    "segmentType": "ppt_slide_text",
                    "orderNo": 1,
                    "textContent": "matrix",
                    "pageNo": 2,
                }
            ],
        },
        {
            "resourceType": "docx",
            "segments": [
                {
                    "segmentKey": "seg-docx-bad-1",
                    "segmentType": "docx_block_text",
                    "orderNo": 1,
                    "textContent": "integral",
                    "slideNo": 6,
                }
            ],
        },
        {
            "resourceType": "mp4",
            "segments": [
                {
                    "segmentKey": "seg-video-bad-1",
                    "segmentType": "video_caption",
                    "orderNo": 1,
                    "textContent": "video",
                    "pageNo": 2,
                }
            ],
        },
        {
            "resourceType": "mp4",
            "segments": [
                {
                    "segmentKey": "seg-video-bad-2",
                    "segmentType": "video_caption",
                    "orderNo": 1,
                    "textContent": "video",
                    "startSec": 0,
                }
            ],
        },
        {
            "resourceType": "srt",
            "segments": [
                {
                    "segmentKey": "seg-srt-bad-1",
                    "segmentType": "video_caption",
                    "orderNo": 1,
                    "textContent": "subtitle",
                    "endSec": 45,
                }
            ],
        },
        {
            "resourceType": "pdf",
            "segments": [{"segmentType": "pdf_page_text", "orderNo": 1, "textContent": "missing key", "pageNo": 2}],
        },
        {
            "resourceType": "pdf",
            "segments": [
                {
                    "segmentKey": "seg-pdf-old-type",
                    "segmentType": "pdf_text",
                    "orderNo": 1,
                    "textContent": "old type",
                    "pageNo": 2,
                }
            ],
        },
        {
            "resourceType": "pptx",
            "segments": [
                {
                    "segmentKey": "seg-pptx-old-type",
                    "segmentType": "slide_text",
                    "orderNo": 1,
                    "textContent": "old type",
                    "slideNo": 1,
                }
            ],
        },
        {
            "resourceType": "docx",
            "segments": [
                {
                    "segmentKey": "seg-docx-old-type",
                    "segmentType": "doc_paragraph",
                    "orderNo": 1,
                    "textContent": "old type",
                    "sectionPath": ["第 1 章"],
                }
            ],
        },
        {
            "resourceType": "mp4",
            "segments": [
                {
                    "segmentKey": "seg-video-old-type",
                    "segmentType": "video_transcript",
                    "orderNo": 1,
                    "textContent": "old type",
                    "startSec": 0,
                    "endSec": 1,
                }
            ],
        },
    ]

    for payload in valid_payloads:
        validator.validate(payload)

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            validator.validate(payload)


@pytest.mark.parametrize("segment_type", ["docx_block_text", "ocr_text", "formula", "image_caption"])
def test_normalized_document_schema_accepts_docx_visual_segments_with_section_path(segment_type: str):
    validator = build_validator("schemas/parse/normalized_document.schema.json")

    validator.validate(
        {
            "resourceType": "docx",
            "segments": [
                {
                    "segmentKey": f"seg-docx-{segment_type.replace('_', '-')}",
                    "segmentType": segment_type,
                    "orderNo": 1,
                    "textContent": "clean text",
                    "sectionPath": ["第 1 章"],
                }
            ],
        }
    )


@pytest.mark.parametrize("bad_location", ["pageNo", "slideNo", "startSec", "endSec"])
def test_normalized_document_schema_rejects_docx_non_section_locations(bad_location: str):
    validator = build_validator("schemas/parse/normalized_document.schema.json")
    payload = {
        "resourceType": "docx",
        "segments": [
            {
                "segmentKey": f"seg-docx-bad-{bad_location}",
                "segmentType": "image_caption",
                "orderNo": 1,
                "textContent": "clean text",
                "sectionPath": ["第 1 章"],
                bad_location: 1,
            }
        ],
    }

    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize("bad_text", ["bad\ufffftext", "bad\ufffdtext", "bad\x00text", "bad\x01text", "bad\x19text"])
def test_normalized_document_schema_rejects_garbled_text_content(bad_text: str):
    validator = build_validator("schemas/parse/normalized_document.schema.json")
    payload = {
        "resourceType": "pdf",
        "segments": [
            {
                "segmentKey": "seg-pdf-garbled",
                "segmentType": "pdf_page_text",
                "orderNo": 1,
                "textContent": bad_text,
                "pageNo": 1,
            }
        ],
    }

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_demo_asset_baseline_covers_fixed_joint_test_set():
    baseline_doc = load_text("docs/demo-assets-baseline.md")

    for token in ("knowlink-demo-main.mp4", "knowlink-demo-handout.pdf", "knowlink-demo-slides.pptx", "knowlink-demo-notes.docx"):
        assert token in baseline_doc

    assert "sha256:<hex>" in baseline_doc
    assert "不在仓库中提交任何演示二进制文件" in baseline_doc


def test_first_edition_manifest_matches_first_edition_doc():
    first_edition_doc = load_text("docs/demo-assets-first-edition.md")
    manifest = load_json("server/seeds/demo_assets_manifest.json")

    assert manifest["assetSetId"] == "first-edition-what-is-set"
    assert manifest["manualImportCourseTitle"] == "KnowLink 固定联调课"
    assert manifest["localBaseDir"] == "local_assets/first-edition/what-is-set"
    assert "local_assets/first-edition/what-is-set/" in first_edition_doc

    expected_assets = {
        "mp4": ("knowlink-demo-main.mp4", "集合的初见.mp4", "video/mp4", 38985139),
        "pdf": ("knowlink-demo-handout.pdf", "1_1_what_is_set.pdf", "application/pdf", 135310),
        "pptx": (
            "knowlink-demo-slides.pptx",
            "1_1_what_is_set.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            88576,
        ),
        "docx": (
            "knowlink-demo-notes.docx",
            "集合的初见.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            40485,
        ),
    }

    assert len(manifest["assets"]) == len(expected_assets)
    assert {asset["resourceType"] for asset in manifest["assets"]} == set(expected_assets)
    for asset in manifest["assets"]:
        normalized_name, original_name, mime_type, size_bytes = expected_assets[asset["resourceType"]]
        assert asset["normalizedName"] == normalized_name
        assert asset["originalName"] == original_name
        assert asset["relativePath"] == normalized_name
        assert asset["mimeType"] == mime_type
        assert asset["sizeBytes"] == size_bytes
        assert asset["trackedInGit"] is False
        assert asset["sourceKind"] == "original"
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", asset["checksum"])
        expected_row = (
            f"| `{asset['resourceType']}` | `{original_name}` | `{normalized_name}` | `{mime_type}` | "
            f"{size_bytes} | `{asset['checksum']}` |"
        )
        assert expected_row in first_edition_doc
