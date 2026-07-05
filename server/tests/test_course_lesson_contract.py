from pathlib import Path

from server.schemas.responses import QuizData


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = "docs/contracts/v2-course-lesson-workbench-contract.md"
HANDOFF_PATH = "docs/v2/phase2-course-lesson-workbench-handoff.md"


def text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def section_between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


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
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}",
        "PATCH /api/v1/courses/{courseId}/lessons/{lessonId}",
        "DELETE /api/v1/courses/{courseId}/lessons/{lessonId}",
        "POST /api/v1/courses/{courseId}/lessons/reorder",
        "POST /api/v1/courses/{courseId}/lessons/{lessonId}/primary-video",
        "POST /api/v1/courses/{courseId}/lessons/merge",
        "POST /api/v1/courses/{courseId}/lessons/{lessonId}/split",
        "POST /api/v1/courses/{courseId}/resources/upload-init",
        "GET /api/v1/courses/{courseId}/qa/sessions",
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}/qa/sessions",
        "GET /api/v1/courses/{courseId}/graph",
        "POST /api/v1/courses/{courseId}/exports",
        "GET /api/v1/home/dashboard",
    ):
        assert path in contract

    for token in (
        "Merge side effects:",
        "非 target lesson 的 lesson-scoped resources 必须迁移到 target lesson",
        "Split side effects:",
        "共享同一个 `primaryVideoResourceId`",
        "提升为 course scope",
        "不创建重复视频 resource row",
        "`SetPrimaryVideoRequest.startSec` / `endSec` 用于设置可选视频片段",
        "只提交 `resourceId` 时表示绑定完整视频或未知区间",
    ):
        assert token in contract


def test_v2_contract_freezes_frontend_prototype_parity() -> None:
    contract = text(CONTRACT_PATH)
    for token in (
        "recreateUI/index-soft-ui-neumorphism.html",
        "frontend prototype parity",
        "LessonStudyPage",
        "/courses/:courseId/lessons/:lessonId/handout",
        "本节资料",
        "进入测试",
        "left outline drawer",
    ):
        assert token in contract
    assert "加入复习" in contract
    assert "top primary action" in contract


def test_v2_contract_freezes_lesson_handout_real_routes() -> None:
    contract = text(CONTRACT_PATH)
    for route in (
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}/handout",
        "POST /api/v1/courses/{courseId}/lessons/{lessonId}/handout/generate",
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}/handout/outline",
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}/handout/blocks",
        "GET /api/v1/courses/{courseId}/lessons/{lessonId}/handout/current-block",
    ):
        assert route in contract
    for token in (
        "scopeType=lesson",
        "artifactKind=lesson_handout",
        "reuse course-level handout generation",
        "two-level outline",
        "handout_blocks",
    ):
        assert token in contract

def test_v2_course_lesson_contract_freezes_scope_and_no_resource_qa() -> None:
    contract = text(CONTRACT_PATH)

    for token in (
        "`scopeType`",
        "`course`",
        "`lesson`",
        "`lessonId`",
        "`usageRole`",
        "`course_material`",
        "`primary_video`",
        "`lesson_material`",
        "`handoutBlockId`",
        "`questionType`",
        "`knowledgePointKey`",
        "`knowledgePointName`",
        "`sourceBlockKey`",
        "`sourceSegmentKeys`",
        "`correctAnswer`",
        "`recommendedReviewActions`",
            "`qa.block_not_found`",
            "embedded lesson-study QA",
            "latest current lesson handout blocks first",
            "falls back only to parsed `scopeType=lesson` resources",
            "falls back only to parsed `scopeType=course` resources",
            "must not mix course materials and lesson materials",
        ):
        assert token in contract

    assert "不做单资料 QA" in contract
    assert "No single-resource QA" in contract
    assert "/resources/{resourceId}/qa" not in contract


def test_public_quiz_read_schema_and_contract_include_explicit_scope_fields() -> None:
    dumped = QuizData.model_validate(
        {
            "quizId": 8001,
            "courseId": 101,
            "scopeType": "lesson",
            "lessonId": 201,
            "startLessonId": None,
            "endLessonId": None,
            "quizMode": "objective",
            "status": "ready",
            "questionCount": 0,
            "questions": [],
        }
    ).model_dump(by_alias=True)

    for key in ("scopeType", "lessonId", "startLessonId", "endLessonId", "quizMode"):
        assert key in dumped

    section = section_between(
        text("docs/contracts/api-contract.md"),
        '### `GET /api/v1/quizzes/{quizId}`',
        '### `POST /api/v1/quizzes/{quizId}/attempts`',
    )
    for token in (
        '"scopeType": "lesson"',
        '"lessonId": 201',
        '"startLessonId": null',
        '"endLessonId": null',
        '"quizMode": "objective"',
    ):
        assert token in section


def test_v2_course_lesson_contract_freezes_error_codes() -> None:
    contract = text(CONTRACT_PATH)
    error_codes = text("docs/contracts/error-codes.md")
    required_error_codes_section = section_between(
        contract,
        "Required error codes:",
        "Deletion blocker DTO:",
    )
    required_codes = {
        "lesson.not_found",
        "lesson.scope_required",
        "lesson.order_conflict",
        "lesson.has_dependents",
        "resource.scope_required",
        "resource.lesson_mismatch",
        "course.delete_blocked",
        "artifact.scope_invalid",
        "qa.block_not_found",
        "qa.scope_invalid",
    }

    for code in required_codes:
        assert f"`{code}`" in contract
        assert f"`{code}`" in error_codes

    assert "`qa.block_not_found`" in required_error_codes_section


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
