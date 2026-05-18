import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FROZEN_STAGE_VALUES = (
    "queued",
    "metadata",
    "download",
    "ffmpeg",
    "object_storage",
    "resource_import",
    "done",
    "error",
    "canceling",
    "canceled",
)
FROZEN_SOURCE_TYPE_VALUES = (
    "single_video",
    "multi_p",
    "collection",
    "bangumi",
)
FROZEN_QUALITY_PREFERENCE_VALUES = ("android_safe",)
FROZEN_DEFAULT_SELECTION_MODE_VALUES = (
    "current_part",
    "all_parts",
    "selected_parts",
)
FROZEN_RUNTIME_ERROR_PHASES = {
    "bilibili.metadata_failed": "metadata",
    "bilibili.playurl_failed": "playurl",
    "bilibili.download_failed": "download",
    "bilibili.merge_failed": "ffmpeg",
    "bilibili.upload_failed": "object_storage",
    "bilibili.import_failed": "resource_import",
}


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def markdown_table_values(section: str, header: str) -> tuple[str, ...]:
    values: list[str] = []
    in_table = False

    for line in section.splitlines():
        if line.startswith(f"| `{header}` |"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            match = re.match(r"\| `([^`]+)` \|", line)
            if match:
                values.append(match.group(1))
                continue
            break
        if in_table and not line.strip() and values:
            break
        if in_table and line.strip():
            break

    return tuple(values)


def registered_error_codes(error_codes: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)`", error_codes))


def backticked_error_codes(markdown: str) -> set[str]:
    return set(re.findall(r"`([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)`", markdown))


def returned_error_codes(contract: str) -> set[str]:
    return set(re.findall(r"(?:^|[\s`])(?:4\d\d|5\d\d)\s+([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)", contract))


def test_v2_bilibili_contract_is_linked_from_docs():
    docs_readme = text("docs/README.md")
    api_contract = text("docs/contracts/api-contract.md")

    assert "contracts/v2-bilibili-import-contract.md" in docs_readme
    assert "v2-bilibili-import-contract.md" in api_contract
    assert "phase1-cao-le-handoff.md" in docs_readme


def test_api_contract_bilibili_section_does_not_label_v1_stub_examples_as_v2():
    api_contract = text("docs/contracts/api-contract.md")
    bilibili_section = api_contract.split("### B 站导入预留接口（V1/MVP）", 1)[1].split(
        "## 7. 异步任务",
        1,
    )[0]

    assert "V2 接通后的响应" not in bilibili_section
    assert "V2 B站真实导入 contract" in bilibili_section
    assert "v2-bilibili-import-contract.md" in bilibili_section
    assert "videoUrl" in bilibili_section
    assert "V1 历史" in bilibili_section


def test_v2_bilibili_import_create_requires_idempotency_key():
    api_contract = text("docs/contracts/api-contract.md")
    idempotency_section = api_contract.split("以下写接口必须支持 `Idempotency-Key`：", 1)[1].split(
        "- 带路径参数的课程接口一律以 path 中的 `courseId` 为准",
        1,
    )[0]

    assert "POST /api/v1/courses/{courseId}/resources/imports/bilibili" in idempotency_section


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


def test_v2_bilibili_contract_freezes_source_and_selection_enums():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    dto_section = contract.split("## 4. DTO 字段冻结", 1)[1].split("## 5. 状态机", 1)[0]

    assert markdown_table_values(dto_section, "sourceType") == FROZEN_SOURCE_TYPE_VALUES
    assert markdown_table_values(dto_section, "qualityPreference") == FROZEN_QUALITY_PREFERENCE_VALUES
    assert markdown_table_values(dto_section, "defaultSelectionMode") == FROZEN_DEFAULT_SELECTION_MODE_VALUES

    assert "`android_safe` 是 phase 1 唯一允许值" in dto_section
    assert "未来 contract 扩展" in dto_section

    assert '"sourceType": "multi_p"' in contract
    for source_type in FROZEN_SOURCE_TYPE_VALUES:
        assert f"`{source_type}`" in dto_section


def test_v2_bilibili_import_creation_returns_async_task_shape():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    import_section = contract.split(
        "### `POST /api/v1/courses/{courseId}/resources/imports/bilibili`", 1
    )[1].split("### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`", 1)[0]

    for token in (
        '"previewId": "bili_preview_9101"',
        '"sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2"',
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
    assert "`previewId`" in import_section
    assert "`sourceUrl`" in import_section
    assert "404 bilibili.preview_not_found" in import_section
    assert "过期、不存在或不属于当前用户/课程" in import_section


def test_v2_bilibili_import_creation_freezes_idempotency_semantics():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    idempotency_section = contract.split("#### Idempotency-Key", 1)[1].split("\n### ", 1)[0]

    for token in (
        "`userId`",
        "`courseId`",
        "`POST /api/v1/courses/{courseId}/resources/imports/bilibili`",
        "`Idempotency-Key`",
        "相同响应",
        "`taskId`",
        "`entity.id`",
        "请求体不一致",
        "`409 idempotency.body_mismatch`",
        "`503 async_task.enqueue_failed`",
        "不创建重复 run",
        "可通过列表或状态接口查询",
    ):
        assert token in idempotency_section


def test_v2_bilibili_stage_values_are_frozen_for_ui_mapping():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    stage_section = contract.split("## 6. Stage 展示字段", 1)[1].split("## 7. `async_tasks` 映射", 1)[0]

    assert "技术子阶段" in stage_section
    assert "UI" in stage_section
    assert "不要和 `status` 混用" in stage_section
    assert "`stage` 只允许以下值" in stage_section
    assert "建议覆盖以下冻结值" not in stage_section

    assert markdown_table_values(stage_section, "stage") == FROZEN_STAGE_VALUES
    assert "playurl" not in stage_section


def test_v2_bilibili_list_and_status_examples_match_frozen_run_fields():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    list_section = contract.split(
        "### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`",
        1,
    )[1].split("### `GET /api/v1/bilibili-import-runs/{importRunId}/status`", 1)[0]
    status_section = contract.split("### `GET /api/v1/bilibili-import-runs/{importRunId}/status`", 1)[1].split(
        "### `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`",
        1,
    )[0]

    for section in (list_section, status_section):
        for field in (
            "importRunId",
            "courseId",
            "sourceUrl",
            "sourceType",
            "status",
            "progressPct",
            "stage",
            "taskId",
            "resourceIds",
            "preview",
            "errorCode",
            "failureReason",
            "recoverable",
            "nextAction",
        ):
            assert f'"{field}"' in section

    example_stage_values = set(re.findall(r'"stage": "([^"]+)"', list_section + status_section))
    assert example_stage_values
    assert example_stage_values <= set(FROZEN_STAGE_VALUES)
    assert all(stage in FROZEN_STAGE_VALUES for stage in example_stage_values)
    assert "download" in example_stage_values
    assert "ffmpeg" in example_stage_values
    assert "downloading" not in example_stage_values
    assert "playurl" not in example_stage_values


def test_v2_bilibili_error_code_scope_allows_shared_infrastructure_errors():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    error_section = contract.split("## 8. 错误码", 1)[1].split("## 9. 取消与清理", 1)[0]

    assert "Bilibili 领域错误码" in error_section
    assert "共享基础设施错误码" in error_section
    assert "`async_task.enqueue_failed`" in error_section


def test_v2_bilibili_runtime_error_phases_are_frozen_separately_from_response_stage():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    error_section = contract.split("## 8. 错误码", 1)[1].split("## 9. 取消与清理", 1)[0]

    assert "`failurePhase`" in error_section
    assert "内部 runner phase" in error_section
    assert "不是响应 `stage`" in error_section
    assert "允许包含不对前端暴露的 `playurl`" in error_section
    assert "运行阶段" not in error_section

    for error_code, failure_phase in FROZEN_RUNTIME_ERROR_PHASES.items():
        assert re.search(rf"\| `{re.escape(error_code)}` \| `{re.escape(failure_phase)}` \|", error_section)

    assert "bilibili.playurl_failed" in error_section
    assert "`playurl`" in error_section
    assert "playurl" not in FROZEN_STAGE_VALUES


def test_v2_bilibili_returned_error_codes_are_registered():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    error_codes = text("docs/contracts/error-codes.md")

    referenced_codes = returned_error_codes(contract)
    registered_codes = registered_error_codes(error_codes)

    assert {"idempotency.body_mismatch", "async_task.enqueue_failed"} <= referenced_codes
    assert referenced_codes <= registered_codes


def test_v2_bilibili_backticked_bilibili_error_codes_are_registered():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")
    error_codes = text("docs/contracts/error-codes.md")

    referenced_bilibili_codes = {
        code for code in backticked_error_codes(contract) if code.startswith("bilibili.")
    }
    registered_codes = registered_error_codes(error_codes)

    assert referenced_bilibili_codes
    assert referenced_bilibili_codes <= registered_codes


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


def test_phase1_handoff_points_to_current_async_task_mapping_section():
    handoff = text("docs/v2/phase1-cao-le-handoff.md")
    status_pointer = handoff.split("## 6. 状态与错误码指针", 1)[1].split("## 7. 曹乐独立验收证据", 1)[0]

    assert "`bilibili_import_run.status` 到 `async_tasks.status`" in status_pointer
    assert "第 7 节" in status_pointer
    assert "`async_tasks` 映射" in status_pointer


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
