import json
from pathlib import Path

from scripts.demo_assets_smoke import (
    EXIT_ASSET_ERROR,
    EXIT_BLOCKED,
    EXIT_OK,
    AssetCheckResult,
    check_assets,
    check_runtime_prerequisites,
    choose_exit_code,
    load_manifest,
    sha256_file,
)


def test_demo_assets_manifest_loader_and_asset_check_pass(tmp_path: Path):
    asset_path = tmp_path / "assets" / "demo.pdf"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"fixed-demo-pdf")
    manifest_path = _write_manifest(tmp_path, asset_path)

    result = load_manifest(manifest_path, root=tmp_path)

    assert result.manifest is not None
    assert result.manifest.local_base_dir == tmp_path / "assets"
    assert result.manifest.assets[0].normalized_name == "demo.pdf"
    assert result.diagnostics == ()
    diagnostics = check_assets(result.manifest)
    assert [diagnostic.code for diagnostic in diagnostics] == ["assets.ok"]
    assert choose_exit_code(result, None) == EXIT_OK


def test_demo_assets_asset_check_reports_missing_file(tmp_path: Path):
    asset_path = tmp_path / "assets" / "missing.pdf"
    manifest_path = _write_manifest(tmp_path, asset_path, content_for_checksum=b"expected")
    result = load_manifest(manifest_path, root=tmp_path)

    assert result.manifest is not None
    diagnostics = check_assets(result.manifest)

    assert [diagnostic.code for diagnostic in diagnostics] == ["asset.missing"]
    assert choose_exit_code(result, None) == EXIT_ASSET_ERROR


def test_demo_assets_asset_check_reports_size_and_checksum_mismatch(tmp_path: Path):
    asset_path = tmp_path / "assets" / "demo.pdf"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"actual")
    manifest_path = _write_manifest(tmp_path, asset_path, content_for_checksum=b"expected", size_bytes=123)
    result = load_manifest(manifest_path, root=tmp_path)

    assert result.manifest is not None
    diagnostics = check_assets(result.manifest)
    codes = {diagnostic.code for diagnostic in diagnostics}

    assert codes == {"asset.size_mismatch", "asset.checksum_mismatch"}
    assert choose_exit_code(result, None) == EXIT_ASSET_ERROR


def test_demo_assets_runtime_check_reports_missing_vivo_env_without_services(tmp_path: Path):
    asset_result = _valid_asset_result(tmp_path)

    runtime = check_runtime_prerequisites(
        env={},
        api_base_url="http://127.0.0.1:8000",
        timeout_sec=0.01,
        check_services=False,
    )
    codes = {diagnostic.code for diagnostic in runtime.diagnostics}

    assert "knowlink_enable_vivo_ocr.disabled" in codes
    assert "knowlink_enable_vivo_vision.disabled" in codes
    assert "knowlink_enable_vivo_asr.disabled" in codes
    assert "vivo.app_key_missing" in codes
    assert "vivo.app_id_missing" in codes
    assert choose_exit_code(asset_result, runtime) == EXIT_BLOCKED


def test_demo_assets_runtime_check_uses_injected_service_checks(tmp_path: Path):
    asset_result = _valid_asset_result(tmp_path)
    env = {
        "KNOWLINK_MINIO_ENDPOINT": "localhost:9000",
        "KNOWLINK_MINIO_ACCESS_KEY": "minioadmin",
        "KNOWLINK_MINIO_SECRET_KEY": "minioadmin",
        "KNOWLINK_ENABLE_VIVO_OCR": "true",
        "KNOWLINK_ENABLE_VIVO_VISION": "true",
        "KNOWLINK_ENABLE_VIVO_ASR": "true",
        "KNOWLINK_VIVO_APP_ID": "app-id",
        "KNOWLINK_VIVO_APP_KEY": "app-key",
    }

    runtime = check_runtime_prerequisites(
        env=env,
        api_base_url="http://127.0.0.1:8000",
        timeout_sec=0.01,
        check_services=True,
        http_get=lambda _url, _timeout: (False, "api down"),
        tcp_connect=lambda _host, _port, _timeout: (False, "minio down"),
    )
    codes = {diagnostic.code for diagnostic in runtime.diagnostics}

    assert "api.unreachable" in codes
    assert "minio.unreachable" in codes
    assert "vivo.app_key_present" in codes
    assert choose_exit_code(asset_result, runtime) == EXIT_BLOCKED


def _valid_asset_result(tmp_path: Path) -> AssetCheckResult:
    asset_path = tmp_path / "assets" / "demo.pdf"
    asset_path.parent.mkdir(exist_ok=True)
    asset_path.write_bytes(b"fixed-demo-pdf")
    return load_manifest(_write_manifest(tmp_path, asset_path), root=tmp_path)


def _write_manifest(
    tmp_path: Path,
    asset_path: Path,
    *,
    content_for_checksum: bytes | None = None,
    size_bytes: int | None = None,
) -> Path:
    if content_for_checksum is None:
        content_for_checksum = asset_path.read_bytes()
    checksum_path = tmp_path / "checksum.bin"
    checksum_path.write_bytes(content_for_checksum)
    relative_path = asset_path.relative_to(tmp_path / "assets")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "assetSetId": "test-assets",
                "manualImportCourseTitle": "Smoke Test Course",
                "localBaseDir": "assets",
                "assets": [
                    {
                        "resourceType": "pdf",
                        "normalizedName": asset_path.name,
                        "originalName": asset_path.name,
                        "relativePath": str(relative_path),
                        "mimeType": "application/pdf",
                        "sizeBytes": len(content_for_checksum) if size_bytes is None else size_bytes,
                        "checksum": f"sha256:{sha256_file(checksum_path)}",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path
