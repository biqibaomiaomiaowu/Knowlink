import asyncio
from pathlib import Path

from server.tests.test_api import AUTH_HEADERS, request


ROOT = Path(__file__).resolve().parents[2]


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
    manifest = payload["data"]["recommendations"][0]["defaultResourceManifest"]
    resource_types = {item["resourceType"] for item in manifest}
    assert {"mp4", "pdf", "pptx", "docx"} <= resource_types


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
                "objectKey": "raw/1/high-math.pdf",
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


def test_handout_and_jump_target_support_mixed_citation_types():
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
                "objectKey": "raw/1/demo.pdf",
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

    second_block_id = blocks[1]["blockId"]
    third_block_id = blocks[2]["blockId"]

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


def test_inquiry_quiz_and_review_cover_planning_display_fields():
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
                "objectKey": "raw/1/planning-display.pdf",
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

    submit_status, submit_body = asyncio.run(
        request(
            "POST",
            f"/api/v1/quizzes/{quiz_id}/attempts",
            headers=AUTH_HEADERS,
            json_body={"answers": [{"questionId": 8101, "selectedOption": "A"}]},
        )
    )
    assert submit_status == 200
    assert "masteryDelta" in submit_body["data"]
    assert "recommendedReviewAction" in submit_body["data"]

    review_status, review_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/review-tasks",
            headers=AUTH_HEADERS,
        )
    )
    assert review_status == 200
    first_task = review_body["data"]["items"][0]
    assert "recommendedSegment" in first_task
    assert "practiceEntry" in first_task
    assert "reviewOrder" in first_task
    assert "intensity" in first_task


def test_scaffold_structure_and_docs_are_aligned():
    required_paths = [
        ROOT / "server/domain/repositories/interfaces.py",
        ROOT / "server/infra/repositories/memory.py",
        ROOT / "server/ai/pipelines/qa.py",
        ROOT / "server/parsers/pptx.py",
        ROOT / "server/parsers/docx.py",
        ROOT / "server/tasks/payloads.py",
        ROOT / "client_flutter/lib/features/qa/qa_page.dart",
        ROOT / "docs/development-scaffold.md",
    ]
    for path in required_paths:
        assert path.exists(), f"missing scaffold path: {path}"

    removed_paths = [
        ROOT / "server/schemas/api.py",
        ROOT / "server/domain/services/runtime.py",
        ROOT / "server/infra/db/session.py",
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
    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs/contracts/api-contract.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pubspec = (ROOT / "client_flutter/pubspec.yaml").read_text(encoding="utf-8")
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
    assert "starlette" not in pyproject
    assert "httpx" not in pyproject
    assert "cupertino_icons" not in pubspec
