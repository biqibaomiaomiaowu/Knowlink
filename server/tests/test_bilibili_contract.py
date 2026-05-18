from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v2_bilibili_contract_is_linked_from_docs():
    docs_readme = text("docs/README.md")
    api_contract = text("docs/contracts/api-contract.md")

    assert "contracts/v2-bilibili-import-contract.md" in docs_readme
    assert "v2-bilibili-import-contract.md" in api_contract
    assert "phase1-cao-le-handoff.md" in docs_readme


def test_v2_bilibili_contract_freezes_states_and_paths():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")

    for path in (
        "POST /api/v1/bilibili/auth/qr/sessions",
        "GET /api/v1/bilibili/auth/session",
        "POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview",
        "POST /api/v1/courses/{courseId}/resources/imports/bilibili",
        "GET /api/v1/bilibili-import-runs/{importRunId}/status",
        "POST /api/v1/bilibili-import-runs/{importRunId}/cancel",
    ):
        assert path in contract

    for status in (
        "pending",
        "fetching_metadata",
        "waiting_download",
        "downloading",
        "merging",
        "uploading",
        "imported",
        "failed",
        "recoverable",
        "canceled",
    ):
        assert f"`{status}`" in contract

    assert "cancelled" not in contract
    assert "`bilibili_import_run` 和 `async_tasks`" in contract


def test_v2_bilibili_contract_freezes_auth_dtos():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    qr_section = contract.split("### `POST /api/v1/bilibili/auth/qr/sessions`", 1)[1].split(
        "### `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`", 1
    )[0]
    session_section = contract.split("### `GET /api/v1/bilibili/auth/session`", 1)[1].split(
        "### `DELETE /api/v1/bilibili/auth/session`", 1
    )[0]

    assert '"status": "pending_scan"' in qr_section
    for status in ("pending_scan", "scanned", "confirmed", "expired", "failed"):
        assert f"`{status}`" in contract

    assert "loginStatus" not in qr_section
    assert "authenticated" not in session_section
    assert "displayName" not in session_section

    for field in ("loginStatus", "userNickname", "expiresAt"):
        assert f'"{field}"' in session_section


def test_v2_bilibili_contract_freezes_preview_dto_shape():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    preview_section = contract.split(
        "### `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview`", 1
    )[1].split("### `POST /api/v1/courses/{courseId}/resources/imports/bilibili`", 1)[0]

    for field in (
        "previewId",
        "sourceUrl",
        "sourceType",
        "title",
        "coverUrl",
        "totalParts",
        "parts",
        "partId",
        "durationSec",
        "cid",
        "pageNo",
        "selectedByDefault",
        "defaultSelectionMode",
    ):
        assert f'"{field}"' in preview_section

    assert '"sourceType": "multi_p"' in preview_section
    assert '"sourceType": "bilibili"' not in preview_section
    assert "defaultSelected" not in preview_section


def test_v2_bilibili_import_creation_returns_async_task_shape():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    import_section = contract.split(
        "### `POST /api/v1/courses/{courseId}/resources/imports/bilibili`", 1
    )[1].split("### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`", 1)[0]

    for token in (
        '"taskId": 7201',
        '"status": "queued"',
        '"nextAction": "poll"',
        '"entity": {',
        '"type": "bilibili_import_run"',
        '"id": 9101',
    ):
        assert token in import_section

    assert '"status": "pending"' not in import_section
    assert '"importRunId"' not in import_section
    assert '"progressPct"' not in import_section


def test_phase1_handoff_separates_android_dependency_and_complex_layout_acceptance():
    handoff = text("docs/v2/phase1-cao-le-handoff.md")

    assert "## 7. 曹乐独立验收证据" in handoff
    assert "## 8. 小组联调依赖" in handoff
    assert "## 9. 复杂布局最低验收标准" in handoff

    independent_acceptance = handoff.split("## 7. 曹乐独立验收证据", 1)[1].split(
        "## 8. 小组联调依赖", 1
    )[0]
    team_dependency = handoff.split("## 8. 小组联调依赖", 1)[1].split(
        "## 9. 复杂布局最低验收标准", 1
    )[0]
    complex_layout = handoff.split("## 9. 复杂布局最低验收标准", 1)[1].split("## 10. 本地命令", 1)[0]

    assert "Android 截图或录屏" not in independent_acceptance
    assert "Android 截图或录屏" in team_dependency

    for token in (
        "表格",
        "保留行列结构",
        "Markdown 表格",
        "公式",
        "明显乱码",
        "原文或 OCR 文本",
        "issue",
        "图片",
        "caption",
        "位置",
        "来源引用",
        "不丢页",
        "引用断裂",
        "不同页或 slide",
        "citation",
    ):
        assert token in complex_layout


def test_v2_bilibili_error_codes_are_frozen():
    error_codes = text("docs/contracts/error-codes.md")

    for error_code in (
        "bilibili.auth_required",
        "bilibili.auth_expired",
        "bilibili.unsupported_url",
        "bilibili.access_denied",
        "bilibili.metadata_failed",
        "bilibili.playurl_failed",
        "bilibili.download_failed",
        "bilibili.merge_failed",
        "bilibili.upload_failed",
        "bilibili.import_failed",
        "bilibili.cancel_failed",
        "bilibili.run_not_found",
        "bilibili.selection_invalid",
        "bilibili.preview_not_found",
    ):
        assert f"`{error_code}`" in error_codes
