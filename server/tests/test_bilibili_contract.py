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
    ):
        assert f"`{error_code}`" in error_codes
