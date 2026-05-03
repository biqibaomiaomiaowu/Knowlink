from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse


EXIT_OK = 0
EXIT_MANIFEST_ERROR = 1
EXIT_ASSET_ERROR = 2
EXIT_BLOCKED = 3

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_MANIFEST_PATH = Path("server/seeds/demo_assets_manifest.json")


@dataclass(frozen=True)
class ManifestAsset:
    resource_type: str
    normalized_name: str
    original_name: str
    relative_path: str
    mime_type: str
    size_bytes: int
    checksum: str


@dataclass(frozen=True)
class DemoAssetsManifest:
    asset_set_id: str
    manual_import_course_title: str
    local_base_dir: Path
    assets: tuple[ManifestAsset, ...]


@dataclass(frozen=True)
class Diagnostic:
    level: str
    code: str
    message: str
    hint: str | None = None


@dataclass(frozen=True)
class AssetCheckResult:
    manifest: DemoAssetsManifest | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class RuntimeCheckResult:
    diagnostics: tuple[Diagnostic, ...]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_manifest(manifest_path: Path, *, root: Path) -> AssetCheckResult:
    diagnostics: list[Diagnostic] = []
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AssetCheckResult(
            manifest=None,
            diagnostics=(
                Diagnostic(
                    "error",
                    "manifest.missing",
                    f"manifest not found: {manifest_path}",
                    "Run from the repository root or pass --manifest.",
                ),
            ),
        )
    except json.JSONDecodeError as exc:
        return AssetCheckResult(
            manifest=None,
            diagnostics=(
                Diagnostic(
                    "error",
                    "manifest.invalid_json",
                    f"manifest is not valid JSON: {manifest_path}:{exc.lineno}:{exc.colno}",
                ),
            ),
        )

    if not isinstance(raw, dict):
        return AssetCheckResult(
            manifest=None,
            diagnostics=(Diagnostic("error", "manifest.invalid_shape", "manifest root must be an object"),),
        )

    assets_raw = raw.get("assets")
    if not isinstance(assets_raw, list) or not assets_raw:
        diagnostics.append(Diagnostic("error", "manifest.assets_missing", "manifest assets must be a non-empty list"))
        assets_raw = []

    local_base_dir_value = raw.get("localBaseDir")
    if not isinstance(local_base_dir_value, str) or not local_base_dir_value.strip():
        diagnostics.append(Diagnostic("error", "manifest.local_base_dir_missing", "manifest localBaseDir is required"))
        local_base_dir = root
    else:
        local_base_dir = Path(local_base_dir_value)
        if not local_base_dir.is_absolute():
            local_base_dir = root / local_base_dir

    assets: list[ManifestAsset] = []
    seen_paths: set[str] = set()
    for index, item in enumerate(assets_raw):
        prefix = f"assets[{index}]"
        if not isinstance(item, dict):
            diagnostics.append(Diagnostic("error", "manifest.asset_invalid", f"{prefix} must be an object"))
            continue

        required = {
            "resourceType": str,
            "normalizedName": str,
            "originalName": str,
            "relativePath": str,
            "mimeType": str,
            "sizeBytes": int,
            "checksum": str,
        }
        missing_or_bad = [
            key
            for key, expected_type in required.items()
            if key not in item or not isinstance(item[key], expected_type)
        ]
        if missing_or_bad:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "manifest.asset_field_invalid",
                    f"{prefix} has missing or invalid fields: {', '.join(missing_or_bad)}",
                )
            )
            continue

        relative_path = item["relativePath"]
        if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "manifest.asset_path_unsafe",
                    f"{prefix}.relativePath must stay under localBaseDir: {relative_path}",
                )
            )
            continue
        if relative_path in seen_paths:
            diagnostics.append(
                Diagnostic("error", "manifest.asset_duplicate_path", f"duplicate relativePath: {relative_path}")
            )
            continue
        seen_paths.add(relative_path)

        checksum = item["checksum"]
        if not _valid_sha256_checksum(checksum):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "manifest.asset_checksum_invalid",
                    f"{prefix}.checksum must use sha256:<64 hex>: {checksum}",
                )
            )
            continue

        if item["sizeBytes"] < 0:
            diagnostics.append(
                Diagnostic("error", "manifest.asset_size_invalid", f"{prefix}.sizeBytes must not be negative")
            )
            continue

        assets.append(
            ManifestAsset(
                resource_type=item["resourceType"],
                normalized_name=item["normalizedName"],
                original_name=item["originalName"],
                relative_path=relative_path,
                mime_type=item["mimeType"],
                size_bytes=item["sizeBytes"],
                checksum=checksum,
            )
        )

    manifest = DemoAssetsManifest(
        asset_set_id=str(raw.get("assetSetId", "")),
        manual_import_course_title=str(raw.get("manualImportCourseTitle", "")),
        local_base_dir=local_base_dir,
        assets=tuple(assets),
    )
    return AssetCheckResult(manifest=manifest, diagnostics=tuple(diagnostics))


def check_assets(manifest: DemoAssetsManifest) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for asset in manifest.assets:
        path = manifest.local_base_dir / asset.relative_path
        if not path.is_file():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "asset.missing",
                    f"missing asset: {path}",
                    f"Place {asset.normalized_name} under {manifest.local_base_dir}.",
                )
            )
            continue

        actual_size = path.stat().st_size
        if actual_size != asset.size_bytes:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "asset.size_mismatch",
                    f"{path} size mismatch: expected {asset.size_bytes}, got {actual_size}",
                    "Refresh server/seeds/demo_assets_manifest.json and docs/demo-assets-first-edition.md if the file changed.",
                )
            )

        actual_checksum = f"sha256:{sha256_file(path)}"
        if actual_checksum != asset.checksum:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "asset.checksum_mismatch",
                    f"{path} checksum mismatch: expected {asset.checksum}, got {actual_checksum}",
                    "Replace the local asset or update the manifest and first-edition docs together.",
                )
            )

    if not diagnostics:
        diagnostics.append(
            Diagnostic(
                "pass",
                "assets.ok",
                f"{len(manifest.assets)} assets match manifest under {manifest.local_base_dir}",
            )
        )
    return tuple(diagnostics)


def check_runtime_prerequisites(
    *,
    env: Mapping[str, str],
    api_base_url: str,
    timeout_sec: float,
    check_services: bool,
    http_get: Callable[[str, float], tuple[bool, str]] | None = None,
    tcp_connect: Callable[[str, int, float], tuple[bool, str]] | None = None,
) -> RuntimeCheckResult:
    diagnostics: list[Diagnostic] = []

    if check_services:
        http_get = http_get or _http_get_ok
        health_url = f"{api_base_url.rstrip('/')}/health"
        api_ok, api_message = http_get(health_url, timeout_sec)
        diagnostics.append(
            Diagnostic(
                "pass" if api_ok else "blocked",
                "api.health_ok" if api_ok else "api.unreachable",
                api_message,
                None if api_ok else "Start the API with: python -m uvicorn server.app:app --reload",
            )
        )

        minio_endpoint = env.get("KNOWLINK_MINIO_ENDPOINT", "").strip()
        minio_access_key = env.get("KNOWLINK_MINIO_ACCESS_KEY", "").strip()
        minio_secret_key = env.get("KNOWLINK_MINIO_SECRET_KEY", "").strip()
        if not minio_endpoint or not minio_access_key or not minio_secret_key:
            diagnostics.append(
                Diagnostic(
                    "blocked",
                    "minio.env_missing",
                    "MinIO env is incomplete: KNOWLINK_MINIO_ENDPOINT, KNOWLINK_MINIO_ACCESS_KEY, KNOWLINK_MINIO_SECRET_KEY are required",
                    "Copy .env.example values for local Docker smoke or export the real MinIO values.",
                )
            )
        else:
            host, port = _parse_endpoint(minio_endpoint, default_port=9000)
            tcp_connect = tcp_connect or _tcp_connect_ok
            minio_ok, minio_message = tcp_connect(host, port, timeout_sec)
            diagnostics.append(
                Diagnostic(
                    "pass" if minio_ok else "blocked",
                    "minio.tcp_ok" if minio_ok else "minio.unreachable",
                    minio_message,
                    None if minio_ok else "Start MinIO through docker compose or point KNOWLINK_MINIO_ENDPOINT at a reachable service.",
                )
            )

    diagnostics.extend(check_vivo_env(env))
    return RuntimeCheckResult(diagnostics=tuple(diagnostics))


def check_vivo_env(env: Mapping[str, str]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    app_key = env.get("KNOWLINK_VIVO_APP_KEY", "").strip()
    app_id = env.get("KNOWLINK_VIVO_APP_ID", "").strip()

    for flag in ("KNOWLINK_ENABLE_VIVO_OCR", "KNOWLINK_ENABLE_VIVO_VISION", "KNOWLINK_ENABLE_VIVO_ASR"):
        enabled = _env_true(env.get(flag, ""))
        diagnostics.append(
            Diagnostic(
                "pass" if enabled else "blocked",
                f"{flag.lower()}.enabled" if enabled else f"{flag.lower()}.disabled",
                f"{flag}={'true' if enabled else env.get(flag, '') or '<unset>'}",
                f"Set {flag}=true for the networked fixed-asset smoke." if not enabled else None,
            )
        )

    diagnostics.append(
        Diagnostic(
            "pass" if app_key else "blocked",
            "vivo.app_key_present" if app_key else "vivo.app_key_missing",
            "KNOWLINK_VIVO_APP_KEY is set" if app_key else "KNOWLINK_VIVO_APP_KEY is missing",
            "Export the competition Vivo app key before running networked OCR/Vision/ASR smoke." if not app_key else None,
        )
    )
    diagnostics.append(
        Diagnostic(
            "pass" if app_id else "blocked",
            "vivo.app_id_present" if app_id else "vivo.app_id_missing",
            "KNOWLINK_VIVO_APP_ID is set" if app_id else "KNOWLINK_VIVO_APP_ID is missing",
            "OCR derives businessId from KNOWLINK_VIVO_APP_ID when KNOWLINK_VIVO_OCR_BUSINESS_ID is not set."
            if not app_id
            else None,
        )
    )
    return tuple(diagnostics)


def render_report(
    *,
    manifest_path: Path,
    asset_result: AssetCheckResult,
    runtime_result: RuntimeCheckResult | None,
    api_base_url: str,
    asset_only: bool,
) -> str:
    lines: list[str] = []
    lines.append("KnowLink fixed demo assets smoke")
    lines.append(f"manifest: {manifest_path}")

    if asset_result.manifest is not None:
        manifest = asset_result.manifest
        lines.append(f"assetSetId: {manifest.asset_set_id}")
        lines.append(f"assetDir: {manifest.local_base_dir}")
        lines.append(f"manualImportCourseTitle: {manifest.manual_import_course_title}")

    lines.append("")
    lines.append("Diagnostics:")
    for diagnostic in asset_result.diagnostics:
        lines.extend(_format_diagnostic(diagnostic))
    if asset_result.manifest is not None and not _has_level(asset_result.diagnostics, "error"):
        for diagnostic in check_assets(asset_result.manifest):
            lines.extend(_format_diagnostic(diagnostic))
    if runtime_result is not None:
        for diagnostic in runtime_result.diagnostics:
            lines.extend(_format_diagnostic(diagnostic))

    exit_code = choose_exit_code(asset_result, runtime_result)
    lines.append("")
    lines.append(f"Result: {exit_label(exit_code)}")
    if asset_only:
        lines.append("Runtime prerequisites were skipped because --asset-check-only was used.")
    elif exit_code == EXIT_OK and asset_result.manifest is not None:
        lines.append("")
        lines.extend(render_manual_run_path(asset_result.manifest, api_base_url=api_base_url))
    elif exit_code == EXIT_BLOCKED:
        lines.append("Local assets are usable, but full smoke is blocked by missing service/env prerequisites.")
    return "\n".join(lines)


def render_manual_run_path(manifest: DemoAssetsManifest, *, api_base_url: str) -> list[str]:
    lines = [
        "Manual run path:",
        "1. Keep API, DB, Redis and MinIO running, then keep these env vars exported in the API process:",
        "   KNOWLINK_ENABLE_VIVO_OCR=true",
        "   KNOWLINK_ENABLE_VIVO_VISION=true",
        "   KNOWLINK_ENABLE_VIVO_ASR=true",
        "   KNOWLINK_VIVO_APP_ID=<app-id>",
        "   KNOWLINK_VIVO_APP_KEY=<app-key>",
        "2. Create the manual import course:",
        "   curl -sS -X POST "
        f"{api_base_url.rstrip('/')}/api/v1/courses "
        "-H 'Authorization: Bearer ${KNOWLINK_DEMO_TOKEN:-knowlink-demo-token}' "
        "-H 'Content-Type: application/json' "
        "-H 'Idempotency-Key: smoke-first-edition-course' "
        f"-d '{{\"title\":\"{manifest.manual_import_course_title}\",\"entryType\":\"manual_import\",\"goalText\":\"固定资料 smoke\",\"preferredStyle\":\"balanced\"}}'",
        "3. For each manifest asset, call upload-init, PUT the local file to uploadUrl, then call upload-complete with objectKey.",
        "   Asset payloads:",
    ]
    for asset in manifest.assets:
        lines.append(
            "   "
            + json.dumps(
                {
                    "resourceType": asset.resource_type,
                    "filename": asset.normalized_name,
                    "originalName": asset.original_name,
                    "mimeType": asset.mime_type,
                    "sizeBytes": asset.size_bytes,
                    "checksum": asset.checksum,
                    "localPath": str(manifest.local_base_dir / asset.relative_path),
                },
                ensure_ascii=False,
            )
        )
    lines.extend(
        [
            "4. Start parsing:",
            "   curl -sS -X POST "
            f"{api_base_url.rstrip('/')}/api/v1/courses/<courseId>/parse/start "
            "-H 'Authorization: Bearer ${KNOWLINK_DEMO_TOKEN:-knowlink-demo-token}' "
            "-H 'Idempotency-Key: smoke-first-edition-parse'",
            "5. Poll pipeline status until ready/partial_success/failed:",
            "   curl -sS "
            f"{api_base_url.rstrip('/')}/api/v1/courses/<courseId>/pipeline-status "
            "-H 'Authorization: Bearer ${KNOWLINK_DEMO_TOKEN:-knowlink-demo-token}'",
        ]
    )
    return lines


def choose_exit_code(asset_result: AssetCheckResult, runtime_result: RuntimeCheckResult | None) -> int:
    if asset_result.manifest is None or _has_level(asset_result.diagnostics, "error"):
        return EXIT_MANIFEST_ERROR
    asset_diagnostics = check_assets(asset_result.manifest)
    if _has_level(asset_diagnostics, "error"):
        return EXIT_ASSET_ERROR
    if runtime_result is not None and _has_level(runtime_result.diagnostics, "blocked"):
        return EXIT_BLOCKED
    return EXIT_OK


def exit_label(exit_code: int) -> str:
    labels = {
        EXIT_OK: "OK",
        EXIT_MANIFEST_ERROR: f"MANIFEST_ERROR ({EXIT_MANIFEST_ERROR})",
        EXIT_ASSET_ERROR: f"ASSET_ERROR ({EXIT_ASSET_ERROR})",
        EXIT_BLOCKED: f"BLOCKED ({EXIT_BLOCKED})",
    }
    return labels.get(exit_code, f"UNKNOWN ({exit_code})")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight the fixed first-edition demo asset smoke run.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--asset-dir", type=Path, help="Override manifest localBaseDir.")
    parser.add_argument("--api-base-url", default=os.getenv("KNOWLINK_SMOKE_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--timeout-sec", type=float, default=2.0)
    parser.add_argument(
        "--asset-check-only",
        action="store_true",
        help="Only validate manifest, size and checksum; skip API/MinIO/Vivo prerequisites.",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    asset_result = load_manifest(manifest_path, root=root)
    if asset_result.manifest is not None and args.asset_dir is not None:
        asset_dir = args.asset_dir if args.asset_dir.is_absolute() else root / args.asset_dir
        asset_result = AssetCheckResult(
            manifest=DemoAssetsManifest(
                asset_set_id=asset_result.manifest.asset_set_id,
                manual_import_course_title=asset_result.manifest.manual_import_course_title,
                local_base_dir=asset_dir,
                assets=asset_result.manifest.assets,
            ),
            diagnostics=asset_result.diagnostics,
        )

    runtime_result = None
    if not args.asset_check_only and asset_result.manifest is not None and not _has_level(asset_result.diagnostics, "error"):
        runtime_result = check_runtime_prerequisites(
            env=os.environ,
            api_base_url=args.api_base_url,
            timeout_sec=args.timeout_sec,
            check_services=True,
        )

    print(
        render_report(
            manifest_path=manifest_path,
            asset_result=asset_result,
            runtime_result=runtime_result,
            api_base_url=args.api_base_url,
            asset_only=args.asset_check_only,
        )
    )
    return choose_exit_code(asset_result, runtime_result)


def _valid_sha256_checksum(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    hex_part = value.split(":", 1)[1]
    return len(hex_part) == 64 and all(char in "0123456789abcdefABCDEF" for char in hex_part)


def _env_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_level(diagnostics: Sequence[Diagnostic], level: str) -> bool:
    return any(diagnostic.level == level for diagnostic in diagnostics)


def _format_diagnostic(diagnostic: Diagnostic) -> list[str]:
    marker = {"pass": "PASS", "blocked": "BLOCKED", "error": "ERROR"}.get(diagnostic.level, diagnostic.level.upper())
    lines = [f"- [{marker}] {diagnostic.code}: {diagnostic.message}"]
    if diagnostic.hint:
        lines.append(f"  hint: {diagnostic.hint}")
    return lines


def _parse_endpoint(endpoint: str, *, default_port: int) -> tuple[str, int]:
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    host = parsed.hostname or endpoint.split(":", 1)[0]
    port = parsed.port or default_port
    return host, port


def _http_get_ok(url: str, timeout_sec: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:
            if 200 <= response.status < 300:
                return True, f"API health reachable: {url}"
            return False, f"API health returned HTTP {response.status}: {url}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"API health unreachable: {url} ({exc})"


def _tcp_connect_ok(host: str, port: int, timeout_sec: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True, f"MinIO TCP reachable: {host}:{port}"
    except OSError as exc:
        return False, f"MinIO TCP unreachable: {host}:{port} ({exc})"


if __name__ == "__main__":
    raise SystemExit(main())
