from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = "docs/contracts/v2-course-lesson-workbench-contract.md"
HANDOFF_PATH = "docs/v2/phase2-course-lesson-workbench-handoff.md"


def text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_v2_course_lesson_contract_is_linked_from_docs() -> None:
    docs_readme = text("docs/README.md")
    api_contract = text("docs/contracts/api-contract.md")

    assert "contracts/v2-course-lesson-workbench-contract.md" in docs_readme
    assert "v2/phase2-course-lesson-workbench-handoff.md" in docs_readme
    assert "v2-course-lesson-workbench-contract.md" in api_contract
    assert "课程库、节课、工作台、分层资料和分层学习产物" in api_contract


def test_v2_course_lesson_contract_freezes_required_sections() -> None:
    contract = text(CONTRACT_PATH)

    for token in (
        "## 1. Scope And Non-goals",
        "## 2. Course Library And Workbench APIs",
        "## 3. Lesson APIs And State",
        "## 4. Resource Scope And Import Placement",
        "## 5. Handout Scope",
        "## 6. Course QA And Lesson QA",
        "## 7. Quiz Scope And Subjective Grading Placeholder",
        "## 8. Review Scope And Evidence Chain",
        "## 9. Graph Report Export And Streaming Placeholders",
        "## 10. Home Continue Learning And Progress APIs",
        "## 11. Error Codes And Deletion Blockers",
        "## 12. Response Examples",
    ):
        assert token in contract

    for path in (
        "GET /api/v1/courses",
        "GET /api/v1/courses/{courseId}/workbench",
        "GET /api/v1/courses/{courseId}/lessons",
        "POST /api/v1/courses/{courseId}/lessons",
        "POST /api/v1/courses/{courseId}/resources/upload-init",
        "GET /api/v1/courses/{courseId}/qa/sessions",
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}/qa/sessions",
        "POST /api/v1/courses/{courseId}/quizzes/stage/generate",
        "GET /api/v1/courses/{courseId}/graph",
        "POST /api/v1/courses/{courseId}/exports",
        "GET /api/v1/home/dashboard",
    ):
        assert path in contract


def test_v2_course_lesson_contract_freezes_scope_and_no_resource_qa() -> None:
    contract = text(CONTRACT_PATH)

    for token in (
        "`scopeType`",
        "`course`",
        "`lesson`",
        "`lesson_range`",
        "`lessonId`",
        "`usageRole`",
        "`course_material`",
        "`primary_video`",
        "`lesson_material`",
    ):
        assert token in contract

    assert "不做单资料 QA" in contract
    assert "No single-resource QA" in contract
    assert "/resources/{resourceId}/qa" not in contract


def test_v2_course_lesson_contract_freezes_error_codes() -> None:
    contract = text(CONTRACT_PATH)
    error_codes = text("docs/contracts/error-codes.md")
    required_codes = {
        "lesson.not_found",
        "lesson.scope_required",
        "lesson.order_conflict",
        "lesson.has_dependents",
        "resource.scope_required",
        "resource.lesson_mismatch",
        "course.delete_blocked",
        "artifact.scope_invalid",
        "qa.scope_invalid",
    }

    for code in required_codes:
        assert f"`{code}`" in contract
        assert f"`{code}`" in error_codes


def test_v2_course_lesson_handoff_skeleton_exists() -> None:
    handoff = text(HANDOFF_PATH)

    for token in (
        "## Implemented Scope",
        "## Non-goals And Placeholders",
        "## Backend Contract Table",
        "## Flutter Contract Table",
        "## Migration And Rollback Notes",
        "## Fixed Demo Data And Acceptance Evidence",
        "## Known Risks",
    ):
        assert token in handoff
