import asyncio
import json
from pathlib import Path

from server.tests.test_api import AUTH_HEADERS, request


ROOT = Path(__file__).resolve().parents[2]


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_recommendation_manifest_includes_pptx_and_docx():
    status, payload = asyncio.run(
        request(
            "POST",
            "/api/v1/recommendations/courses",
            headers=AUTH_HEADERS,
            json_body={
                "goalText": "高等数学期末复习",
                "selfLevel": "intermediate",
                "timeBudgetMinutes": 240,
                "preferredStyle": "exam",
            },
        )
    )
    assert status == 200
    recommendation = payload["data"]["recommendations"][0]
    manifest = recommendation["defaultResourceManifest"]
    resource_types = {item["resourceType"] for item in manifest}
    assert {"mp4", "pdf", "pptx", "docx"} <= resource_types
    assert recommendation["nextAction"]["type"] == "confirm_course"
    assert recommendation["reasonMaterials"]


def test_v2_course_catalog_fields_are_present():
    catalog = load_json("server/seeds/course_catalog.json")
    required = {
        "subject",
        "courseCode",
        "targetAudience",
        "prerequisites",
        "knowledgeTags",
        "outline",
        "importHints",
        "reasonMaterials",
        "coverUrl",
        "highlights",
    }

    for item in catalog:
        assert required <= set(item)
        assert item["knowledgeTags"]
        assert item["outline"]
        assert item["reasonMaterials"]


def test_v2_course_catalog_has_phase1_demo_coverage():
    catalog = load_json("server/seeds/course_catalog.json")

    assert len(catalog) >= 5
    assert {"math", "linear_algebra"} <= {item["subject"] for item in catalog}
    assert any(
        any("B站" in hint or "视频" in hint for hint in item["importHints"])
        for item in catalog
    )

    for item in catalog:
        assert len(item["reasonMaterials"]) >= 3
        manifest_types = {
            resource["resourceType"] for resource in item["defaultResourceManifest"]
        }
        assert {"mp4", "pdf"} <= manifest_types


def test_recommendation_service_uses_provider_boundary_for_rule_based_results():
    from server.domain.services.recommendations import (
        RecommendationService,
        RuleBasedRecommendationProvider,
    )
    from server.schemas.requests import RecommendationRequest

    service = RecommendationService(ROOT / "server/seeds/course_catalog.json")
    payload = RecommendationRequest(
        goalText="高等数学期末复习",
        selfLevel="intermediate",
        timeBudgetMinutes=240,
        preferredStyle="exam",
    )

    recommendations = service.recommend(payload)
    catalog_ids = {item["catalogId"] for item in service.load_catalog()}

    assert isinstance(service.provider, RuleBasedRecommendationProvider)
    assert recommendations
    assert recommendations[0].next_action["type"] == "confirm_course"
    assert recommendations[0].catalog_id in catalog_ids


def test_recommendation_provider_protocol_can_be_implemented_by_future_llm_provider():
    from server.domain.services.recommendations import RecommendationProvider, RecommendationService
    from server.schemas.common import ResourceManifestItem
    from server.schemas.requests import RecommendationRequest
    from server.schemas.responses import RecommendationCard

    class StubLLMRecommendationProvider:
        def recommend(
            self,
            *,
            catalog: list[dict],
            payload: RecommendationRequest,
        ) -> list[RecommendationCard]:
            recommended = catalog[0]
            return [
                RecommendationCard(
                    catalog_id="llm-generated-01",
                    title="LLM 推荐课程",
                    provider="LLM Stub",
                    level="intermediate",
                    estimated_hours=3,
                    fit_score=88,
                    reasons=["由后续 LLM provider 生成"],
                    reason_materials=["保留 provider 注入边界"],
                    next_action={
                        "type": "confirm_course",
                        "label": "确认入课并导入资料",
                    },
                    default_resource_manifest=[
                        ResourceManifestItem(
                            resource_type="mp4",
                            required=True,
                            description="主课程视频",
                        ),
                        ResourceManifestItem(
                            resource_type="pdf",
                            required=True,
                            description="配套讲义 PDF",
                        ),
                    ],
                ),
                RecommendationCard(
                    catalog_id=recommended["catalogId"],
                    title=recommended["title"],
                    provider="LLM Stub",
                    level=recommended["level"],
                    estimated_hours=recommended["estimatedHours"],
                    fit_score=88,
                    reasons=["由后续 LLM provider 选择 catalog 课程"],
                    reason_materials=["保留 provider 注入边界"],
                    next_action={
                        "type": "confirm_course",
                        "label": "确认入课并导入资料",
                    },
                    default_resource_manifest=[
                        ResourceManifestItem(**resource)
                        for resource in recommended["defaultResourceManifest"]
                    ],
                ),
            ]

    provider: RecommendationProvider = StubLLMRecommendationProvider()
    service = RecommendationService(
        ROOT / "server/seeds/course_catalog.json",
        provider=provider,
    )
    payload = RecommendationRequest(
        goalText="线性代数期末复习",
        selfLevel="intermediate",
        timeBudgetMinutes=180,
        preferredStyle="exam",
    )

    recommendations = service.recommend(payload)

    assert recommendations[0].catalog_id in {
        item["catalogId"] for item in service.load_catalog()
    }
    assert service.get_catalog_entry(recommendations[0].catalog_id) is not None
    assert recommendations[0].next_action["type"] == "confirm_course"


def test_dashboard_and_pipeline_status_cover_competition_display_fields():
    create_status, create_body = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "dashboard-course-1"},
            json_body={
                "title": "高数冲刺课",
                "entryType": "manual_import",
                "goalText": "比赛展示联调",
                "preferredStyle": "balanced",
            },
        )
    )
    assert create_status == 201
    course_id = create_body["data"]["course"]["courseId"]

    dashboard_status, dashboard = asyncio.run(
        request("GET", "/api/v1/home/dashboard", headers=AUTH_HEADERS)
    )
    assert dashboard_status == 200
    assert "dailyRecommendedKnowledgePoints" in dashboard["data"]
    assert "learningStats" in dashboard["data"]

    upload_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=AUTH_HEADERS | {"idempotency-key": "dashboard-upload-1"},
            json_body={
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/high-math.pdf",
                "originalName": "high-math.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:dashboard-pdf",
            },
        )
    )
    assert upload_status == 201

    parse_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/parse/start",
            headers=AUTH_HEADERS | {"idempotency-key": "dashboard-parse-1"},
        )
    )
    assert parse_status == 200

    pipeline_status, pipeline = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/pipeline-status",
            headers=AUTH_HEADERS,
        )
    )
    assert pipeline_status == 200
    assert "sourceOverview" in pipeline["data"]
    assert "knowledgeMap" in pipeline["data"]
    assert "highlightSummary" in pipeline["data"]


def test_upload_contract_accepts_pptx_and_docx():
    create_status, create_body = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "contract-course-1"},
            json_body={
                "title": "离散数学资料课",
                "entryType": "manual_import",
                "goalText": "资料解析联调",
                "preferredStyle": "balanced",
            },
        )
    )
    assert create_status == 201
    course_id = create_body["data"]["course"]["courseId"]

    for resource_type in ("pptx", "docx"):
        upload_init_status, upload_init = asyncio.run(
            request(
                "POST",
                f"/api/v1/courses/{course_id}/resources/upload-init",
                headers=AUTH_HEADERS,
                json_body={
                    "resourceType": resource_type,
                    "filename": f"demo.{resource_type}",
                    "mimeType": "application/octet-stream",
                    "sizeBytes": 1024,
                    "checksum": f"sha256:{resource_type}",
                },
            )
        )
        assert upload_init_status == 200
        assert upload_init["data"]["objectKey"].endswith(f"demo.{resource_type}")

        upload_complete_status, upload_complete = asyncio.run(
            request(
                "POST",
                f"/api/v1/courses/{course_id}/resources/upload-complete",
                headers=AUTH_HEADERS | {"idempotency-key": f"upload-{resource_type}-1"},
                json_body={
                    "resourceType": resource_type,
                    "objectKey": upload_init["data"]["objectKey"],
                    "originalName": f"demo.{resource_type}",
                    "mimeType": "application/octet-stream",
                    "sizeBytes": 1024,
                    "checksum": f"sha256:{resource_type}",
                },
            )
        )
        assert upload_complete_status == 201
        assert upload_complete["data"]["resourceType"] == resource_type


def test_handout_qa_and_jump_target_keep_single_locator_per_citation():
    def locator_group_count(citation: dict[str, object]) -> int:
        groups = 0
        if citation.get("pageNo") is not None:
            groups += 1
        if citation.get("slideNo") is not None:
            groups += 1
        if citation.get("anchorKey") is not None:
            groups += 1
        if citation.get("startSec") is not None or citation.get("endSec") is not None:
            assert citation.get("startSec") is not None
            assert citation.get("endSec") is not None
            groups += 1
        return groups

    create_status, create_body = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "mixed-citation-course"},
            json_body={
                "title": "高保真讲义课",
                "entryType": "manual_import",
                "goalText": "验证多来源引用",
                "preferredStyle": "detailed",
            },
        )
    )
    assert create_status == 201
    course_id = create_body["data"]["course"]["courseId"]

    upload_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=AUTH_HEADERS | {"idempotency-key": "mixed-citation-upload"},
            json_body={
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/demo.pdf",
                "originalName": "demo.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:pdf",
            },
        )
    )
    assert upload_status == 201

    parse_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/parse/start",
            headers=AUTH_HEADERS | {"idempotency-key": "mixed-citation-parse"},
        )
    )
    assert parse_status == 200

    handout_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/handouts/generate",
            headers=AUTH_HEADERS | {"idempotency-key": "mixed-citation-handout"},
        )
    )
    assert handout_status == 200

    blocks_status, blocks_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/handouts/latest/blocks",
            headers=AUTH_HEADERS,
        )
    )
    assert blocks_status == 200
    blocks = blocks_body["data"]["items"]
    assert any(block["citations"][0].get("pageNo") for block in blocks)
    assert any(block["citations"][0].get("slideNo") for block in blocks)
    assert any(block["citations"][0].get("anchorKey") for block in blocks)
    assert all(locator_group_count(block["citations"][0]) == 1 for block in blocks)

    first_block_id = blocks[0]["blockId"]
    second_block_id = blocks[1]["blockId"]
    third_block_id = blocks[2]["blockId"]

    qa_status, qa_body = asyncio.run(
        request(
            "POST",
            "/api/v1/qa/messages",
            headers=AUTH_HEADERS,
            json_body={
                "courseId": course_id,
                "handoutBlockId": first_block_id,
                "question": "这个定义和题型有什么联系？",
            },
        )
    )
    assert qa_status == 200
    assert locator_group_count(qa_body["data"]["citations"][0]) == 1

    jump_pdf_status, jump_pdf_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/handout-blocks/{first_block_id}/jump-target",
            headers=AUTH_HEADERS,
        )
    )
    assert jump_pdf_status == 200
    assert jump_pdf_body["data"]["pageNo"] == 2
    assert jump_pdf_body["data"]["startSec"] == 120
    assert jump_pdf_body["data"]["endSec"] == 300

    jump_slide_status, jump_slide_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/handout-blocks/{second_block_id}/jump-target",
            headers=AUTH_HEADERS,
        )
    )
    assert jump_slide_status == 200
    assert jump_slide_body["data"]["slideNo"] == 6

    jump_anchor_status, jump_anchor_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/handout-blocks/{third_block_id}/jump-target",
            headers=AUTH_HEADERS,
        )
    )
    assert jump_anchor_status == 200
    assert jump_anchor_body["data"]["anchorKey"] == "section-integral"


def test_inquiry_and_quiz_generate_cover_planning_display_fields():
    create_status, create_body = asyncio.run(
        request(
            "POST",
            "/api/v1/courses",
            headers=AUTH_HEADERS | {"idempotency-key": "planning-display-course"},
            json_body={
                "title": "考研数学展示课",
                "entryType": "manual_import",
                "goalText": "验证问询与复习展示",
                "preferredStyle": "detailed",
            },
        )
    )
    assert create_status == 201
    course_id = create_body["data"]["course"]["courseId"]

    upload_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=AUTH_HEADERS | {"idempotency-key": "planning-display-upload"},
            json_body={
                "resourceType": "pdf",
                "objectKey": f"raw/1/{course_id}/planning-display.pdf",
                "originalName": "planning-display.pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1024,
                "checksum": "sha256:planning-display",
            },
        )
    )
    assert upload_status == 201

    parse_status, _ = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/parse/start",
            headers=AUTH_HEADERS | {"idempotency-key": "planning-display-parse"},
        )
    )
    assert parse_status == 200

    inquiry_status, inquiry = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/inquiry/questions",
            headers=AUTH_HEADERS,
        )
    )
    assert inquiry_status == 200
    question_keys = {item["key"] for item in inquiry["data"]["questions"]}
    assert {
        "goal_type",
        "mastery_level",
        "time_budget_minutes",
        "handout_style",
        "explanation_granularity",
    } <= question_keys

    quiz_generate_status, quiz_generate = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/quizzes/generate",
            headers=AUTH_HEADERS | {"idempotency-key": "planning-display-quiz"},
        )
    )
    assert quiz_generate_status == 200
    quiz_id = quiz_generate["data"]["entity"]["id"]
    assert quiz_generate["data"]["entity"]["type"] == "quiz"

    quiz_status, quiz_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/quizzes/{quiz_id}/status",
            headers=AUTH_HEADERS,
        )
    )
    assert quiz_status == 200
    assert quiz_body["data"]["status"] == "queued"
    assert quiz_body["data"]["questionCount"] == 0

    submit_status, submit_body = asyncio.run(
        request(
            "POST",
            f"/api/v1/quizzes/{quiz_id}/attempts",
            headers=AUTH_HEADERS,
            json_body={"answers": [{"questionId": 8101, "selectedOption": "A"}]},
        )
    )
    assert submit_status == 409
    assert submit_body["errorCode"] == "quiz.not_ready"


def test_scaffold_structure_and_docs_are_aligned():
    required_paths = [
        ROOT / "server/domain/repositories/interfaces.py",
        ROOT / "server/infra/repositories/memory.py",
        ROOT / "server/ai/pipelines/qa.py",
        ROOT / "server/parsers/pptx.py",
        ROOT / "server/parsers/docx.py",
        ROOT / "server/tasks/payloads.py",
        ROOT / "server/infra/db/base.py",
        ROOT / "server/infra/db/session.py",
        ROOT / "server/infra/db/models/course.py",
        ROOT / "server/infra/db/models/resource.py",
        ROOT / "server/infra/db/models/parse_run.py",
        ROOT / "server/infra/db/models/async_task.py",
        ROOT / "alembic/versions/1b319cfadeb3_init_tables.py",
        ROOT / "client_flutter/lib/features/qa/qa_page.dart",
        ROOT / "client_flutter/test/shared/course_flow_providers_test.dart",
        ROOT / "docs/engineering/development-scaffold.md",
    ]
    for path in required_paths:
        assert path.exists(), f"missing scaffold path: {path}"

    removed_paths = [
        ROOT / "server/schemas/api.py",
        ROOT / "server/domain/services/runtime.py",
        ROOT / "server/infra/queue/broker.py",
        ROOT / "server/infra/storage/client.py",
        ROOT / "client_flutter/lib/shared/providers/session_provider.dart",
    ]
    for path in removed_paths:
        assert not path.exists(), f"obsolete compatibility file still exists: {path}"

    for router_path in (ROOT / "server/api/routers").glob("*.py"):
        source = router_path.read_text(encoding="utf-8")
        assert "runtime_store" not in source, f"router still depends on runtime store: {router_path}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/v1/architecture.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs/contracts/api-contract.md").read_text(encoding="utf-8")
    scaffold = (ROOT / "docs/engineering/development-scaffold.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pubspec = (ROOT / "client_flutter/pubspec.yaml").read_text(encoding="utf-8")
    architecture_scaffold = architecture.split("### 7.1 后端", 1)[1].split("---", 1)[0]
    assert "MP4 + PDF + PPTX + DOCX" in readme
    assert "MP4 + PDF + PPTX + DOCX" in architecture
    assert "resourceType\": \"pptx\"" in contract
    assert "resourceType\": \"docx\"" in contract
    assert "/courses/:courseId/qa/:sessionId" in architecture
    assert "courseFlowProvider" in architecture
    assert "activeBlockProvider" in architecture
    assert "playerStateProvider" in architecture
    assert "dailyRecommendedKnowledgePoints" in contract
    assert "learningStats" in contract
    assert "masteryDelta" in contract
    assert "recommendedSegment" in contract
    assert "快应用工程实现" in architecture
    assert "文档优先级矩阵" in readme
    assert "当前完成度矩阵" in scaffold
    assert "SQLAlchemy model 与 Alembic 迁移" in scaffold
    assert "第一版业务表已覆盖" in scaffold
    assert "第一版已接通" in scaffold
    assert "内存态 demo 适配器仍保留" in scaffold
    assert "server/schemas/api.py" not in architecture_scaffold
    assert "app_factory.py" in architecture_scaffold
    assert "router.py" in architecture_scaffold
    assert "response.py" in architecture_scaffold
    assert "memory_runtime.py" in architecture_scaffold
    assert "client_flutter/test/" in architecture_scaffold
    assert "week1-cao-le-freeze.md" in architecture_scaffold
    assert "demo-assets-baseline.md" in architecture_scaffold
    assert "demo-assets-first-edition.md" in architecture_scaffold
    assert "starlette" not in pyproject
    assert "httpx" not in pyproject
    assert "cupertino_icons" not in pubspec


def test_basic_database_four_table_scaffold_is_accepted():
    import server.infra.db.models  # noqa: F401
    from server.infra.db.base import Base

    sources = {
        "courses": (ROOT / "server/infra/db/models/course.py").read_text(encoding="utf-8"),
        "course_resources": (ROOT / "server/infra/db/models/resource.py").read_text(encoding="utf-8"),
        "parse_runs": (ROOT / "server/infra/db/models/parse_run.py").read_text(encoding="utf-8"),
        "async_tasks": (ROOT / "server/infra/db/models/async_task.py").read_text(encoding="utf-8"),
    }
    migration = (ROOT / "alembic/versions/1b319cfadeb3_init_tables.py").read_text(encoding="utf-8")
    session = (ROOT / "server/infra/db/session.py").read_text(encoding="utf-8")

    expected_fields = {
        "courses": [
            "active_parse_run_id",
            "created_at",
            "updated_at",
        ],
        "course_resources": [
            "resource_type",
            "object_key",
            "ingest_status",
            "validation_status",
            "processing_status",
            "created_at",
        ],
        "parse_runs": [
            "progress_pct",
            "started_at",
            "finished_at",
            "created_at",
        ],
        "async_tasks": [
            "parse_run_id",
            "task_type",
            "payload_json",
            "result_json",
            "error_message",
            "created_at",
        ],
    }

    for table_name, fields in expected_fields.items():
        model_columns = set(Base.metadata.tables[table_name].c.keys())
        assert f'__tablename__ = "{table_name}"' in sources[table_name]
        assert f"'{table_name}'" in migration or f'"{table_name}"' in migration
        for field in fields:
            assert (
                field in sources[table_name] or field in model_columns
            ), f"{field} missing in {table_name} model"
            assert f"'{field}'" in migration or f'"{field}"' in migration, f"{field} missing in migration"

    assert "create_engine" in session
    assert "create_async_engine" not in session
    assert "target_metadata = Base.metadata" in (ROOT / "alembic/env.py").read_text(encoding="utf-8")
