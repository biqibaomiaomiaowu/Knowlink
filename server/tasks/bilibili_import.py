from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from server.domain.repositories.interfaces import (
    AsyncTaskRepository,
    BilibiliImportRepository,
    ResourceRepository,
)
from server.domain.services.errors import ServiceError
from server.infra.bilibili import BiliClient, BiliDownloader, FfmpegMerger
from server.infra.bilibili.models import BilibiliPart, BilibiliPreview
from server.infra.bilibili.url import parse_bilibili_url
from server.infra.storage import ObjectStorage


class BilibiliImportCanceled(Exception):
    pass


@dataclass
class BilibiliImportFailure(Exception):
    error_code: str
    message: str
    recoverable: bool = False


class BilibiliImportRunner:
    def __init__(
        self,
        *,
        bilibili: BilibiliImportRepository,
        resources: ResourceRepository,
        async_tasks: AsyncTaskRepository,
        storage: ObjectStorage,
        bili_client: Any | None = None,
        downloader: Any | None = None,
        merger: Any | None = None,
        runtime_dir: str | Path = "/tmp/knowlink-bilibili-imports",
    ) -> None:
        self.bilibili = bilibili
        self.resources = resources
        self.async_tasks = async_tasks
        self.storage = storage
        self.bili_client = bili_client or BiliClient()
        self.downloader = downloader or BiliDownloader()
        self.merger = merger or FfmpegMerger()
        self.runtime_dir = Path(runtime_dir)

    def run(self, message: dict[str, Any]) -> dict[str, Any] | None:
        import_run_id = _int_required(message, "importRunId", "import_run_id")
        course_id = _int_required(message, "courseId", "course_id")
        task_id = _optional_int(message, "taskId", "task_id")
        run = self.bilibili.get_bilibili_import_run(import_run_id)
        if run is None:
            raise RuntimeError(f"Bilibili import run was not found: {import_run_id}")
        if task_id is None:
            task_id = _optional_int(run, "taskId", "task_id")
        if str(run.get("status")) == "canceled":
            self._mark_canceled(import_run_id=import_run_id, task_id=task_id)
            return run

        work_dir = self.runtime_dir / str(import_run_id)
        cancel_token = _CancelToken(lambda: self._is_canceled(import_run_id))
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
            self._advance(
                import_run_id=import_run_id,
                task_id=task_id,
                status="fetching_metadata",
                stage="metadata",
                progress_pct=5,
                temp_dir=str(work_dir),
            )
            cookies = self._auth_cookies()
            preview = self._load_preview(run, cookies=cookies)
            parts = self._selected_parts(preview, run.get("selection") or {})
            if not parts:
                raise BilibiliImportFailure(
                    error_code="bilibili.selection_invalid",
                    message="No Bilibili parts were selected for import.",
                )

            resource_ids: list[int] = []
            for index, part in enumerate(parts, start=1):
                self._raise_if_canceled(import_run_id)
                resource = self._import_part(
                    course_id=course_id,
                    import_run_id=import_run_id,
                    source_url=str(run.get("sourceUrl") or message.get("sourceUrl") or ""),
                    selection=run.get("selection") or {},
                    preview=preview,
                    part=part,
                    part_index=index,
                    total_parts=len(parts),
                    cookies=cookies,
                    work_dir=work_dir,
                    cancel_token=cancel_token,
                    task_id=task_id,
                )
                resource_ids.append(int(resource["resourceId"]))

            self._raise_if_canceled(import_run_id)
            self._advance(
                import_run_id=import_run_id,
                task_id=task_id,
                status="imported",
                stage="done",
                progress_pct=100,
                resource_ids=resource_ids,
            )
            return self.bilibili.get_bilibili_import_run(import_run_id)
        except BilibiliImportCanceled:
            self._mark_canceled(import_run_id=import_run_id, task_id=task_id)
            return self.bilibili.get_bilibili_import_run(import_run_id)
        except BilibiliImportFailure as exc:
            self._mark_failed(
                import_run_id=import_run_id,
                task_id=task_id,
                error_code=exc.error_code,
                failure_reason=exc.message,
                recoverable=exc.recoverable,
            )
            return self.bilibili.get_bilibili_import_run(import_run_id)
        except ServiceError as exc:
            self._mark_failed(
                import_run_id=import_run_id,
                task_id=task_id,
                error_code=exc.error_code,
                failure_reason=exc.message,
                recoverable=exc.status_code in {401, 403, 429, 502, 503},
            )
            return self.bilibili.get_bilibili_import_run(import_run_id)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _import_part(
        self,
        *,
        course_id: int,
        import_run_id: int,
        source_url: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        part: dict[str, Any],
        part_index: int,
        total_parts: int,
        cookies: dict[str, Any],
        work_dir: Path,
        cancel_token: _CancelToken,
        task_id: int | None,
    ) -> dict[str, Any]:
        progress_base = 10 + int((part_index - 1) * 80 / max(total_parts, 1))
        progress_span = max(int(80 / max(total_parts, 1)), 1)
        try:
            playurl = self._playurl(
                source_url=source_url,
                part=part,
                cookies=cookies,
                quality_preference=str(selection.get("qualityPreference") or "android_safe"),
            )
        except Exception as exc:
            raise _failure_from_exception(exc, default_error_code="bilibili.playurl_failed") from exc

        self._advance(
            import_run_id=import_run_id,
            task_id=task_id,
            status="downloading",
            stage="download",
            progress_pct=progress_base,
        )
        video_path = work_dir / f"p{part_index}.video.m4s"
        audio_path = work_dir / f"p{part_index}.audio.m4s"
        try:
            self.downloader.download(
                playurl["videoUrl"],
                video_path,
                cookies=cookies,
                cancel_token=cancel_token,
                progress_callback=lambda _progress: self._advance(
                    import_run_id=import_run_id,
                    task_id=task_id,
                    status="downloading",
                    stage="download",
                    progress_pct=min(progress_base + max(progress_span // 3, 1), 85),
                ),
            )
            self.downloader.download(
                playurl["audioUrl"],
                audio_path,
                cookies=cookies,
                cancel_token=cancel_token,
            )
        except Exception as exc:
            if _is_canceled_exception(exc):
                raise BilibiliImportCanceled() from exc
            raise _failure_from_exception(exc, default_error_code="bilibili.download_failed") from exc

        self._advance(
            import_run_id=import_run_id,
            task_id=task_id,
            status="merging",
            stage="ffmpeg",
            progress_pct=min(progress_base + int(progress_span * 0.55), 90),
        )
        merged_path = work_dir / f"p{part_index}.mp4"
        try:
            self.merger.merge(video_path, audio_path, merged_path, cancel_token=cancel_token)
        except Exception as exc:
            if _is_canceled_exception(exc):
                raise BilibiliImportCanceled() from exc
            raise _failure_from_exception(exc, default_error_code="bilibili.merge_failed") from exc

        self._raise_if_canceled(import_run_id)
        self._advance(
            import_run_id=import_run_id,
            task_id=task_id,
            status="uploading",
            stage="object_storage",
            progress_pct=min(progress_base + int(progress_span * 0.75), 95),
        )
        object_key = _object_key(
            course_id=course_id,
            import_run_id=import_run_id,
            part=part,
            part_index=part_index,
        )
        self._raise_if_canceled(import_run_id)
        try:
            stat = self.storage.upload_file(
                object_key,
                merged_path,
                content_type="video/mp4",
                metadata={
                    "course-id": str(course_id),
                    "source": "bilibili",
                    "import-run-id": str(import_run_id),
                },
            )
        except Exception as exc:
            raise _failure_from_exception(exc, default_error_code="bilibili.upload_failed") from exc

        self._raise_if_canceled(import_run_id)
        self._advance(
            import_run_id=import_run_id,
            task_id=task_id,
            status="uploading",
            stage="resource_import",
            progress_pct=min(progress_base + int(progress_span * 0.9), 98),
        )
        self._raise_if_canceled(import_run_id)
        try:
            return self.resources.create_resource(
                course_id,
                {
                    "resourceType": "mp4",
                    "sourceType": "bilibili",
                    "originUrl": source_url,
                    "objectKey": object_key,
                    "originalName": _resource_name(preview, part, part_index=part_index),
                    "mimeType": "video/mp4",
                    "sizeBytes": getattr(stat, "size_bytes", None),
                    "checksum": getattr(stat, "checksum", None),
                    "parsePolicyJson": {"source": "bilibili", "importRunId": import_run_id},
                },
            )
        except Exception as exc:
            raise _failure_from_exception(exc, default_error_code="bilibili.import_failed") from exc

    def _load_preview(self, run: dict[str, Any], *, cookies: dict[str, Any]) -> dict[str, Any]:
        preview = run.get("preview")
        if isinstance(preview, dict) and isinstance(preview.get("parts"), list):
            return preview
        result = self.bili_client.preview(str(run["sourceUrl"]), cookies)
        if isinstance(result, BilibiliPreview):
            return result.to_api()
        if isinstance(result, dict):
            return result
        raise BilibiliImportFailure(
            error_code="bilibili.metadata_failed",
            message="Bilibili preview adapter returned an invalid payload.",
        )

    def _selected_parts(self, preview: dict[str, Any], selection: dict[str, Any]) -> list[dict[str, Any]]:
        parts = [_part_to_api(part) for part in preview.get("parts") or []]
        selected_ids = {str(part_id) for part_id in selection.get("selectedPartIds") or []}
        selection_mode = str(selection.get("selectionMode") or preview.get("defaultSelectionMode") or "all_parts")
        if selection_mode == "selected_parts" and selected_ids:
            return [part for part in parts if str(part.get("partId")) in selected_ids]
        if selection_mode == "current_part" and selected_ids:
            return [part for part in parts if str(part.get("partId")) in selected_ids][:1]
        if selection_mode == "current_part":
            defaults = [part for part in parts if part.get("selectedByDefault")]
            return defaults[:1] if defaults else parts[:1]
        return parts

    def _playurl(
        self,
        *,
        source_url: str,
        part: dict[str, Any],
        cookies: dict[str, Any],
        quality_preference: str,
    ) -> dict[str, Any]:
        try:
            payload = self.bili_client.playurl(
                source_url=source_url,
                part=part,
                cookies=cookies,
                quality_preference=quality_preference,
            )
        except TypeError:
            parsed = parse_bilibili_url(source_url)
            payload = self.bili_client.playurl(
                bvid=parsed.bvid or "",
                cid=int(part["cid"]),
                cookies=cookies,
                qn=_quality_qn(quality_preference),
            )
        return _extract_media_urls(payload)

    def _auth_cookies(self) -> dict[str, Any]:
        auth = self.bilibili.get_bilibili_auth_session()
        if not isinstance(auth, dict):
            return {}
        cookies = auth.get("cookiesJson") or auth.get("cookies_json") or {}
        return dict(cookies) if isinstance(cookies, dict) else {}

    def _advance(
        self,
        *,
        import_run_id: int,
        task_id: int | None,
        status: str,
        stage: str,
        progress_pct: int,
        **changes: Any,
    ) -> None:
        if status != "canceled":
            self._raise_if_canceled(import_run_id)
        update = {
            "status": status,
            "stage": stage,
            "progress_pct": progress_pct,
            "error_code": None,
            "failure_reason": None,
            **changes,
        }
        self.bilibili.update_bilibili_import_run(import_run_id, **update)
        if task_id is not None:
            self.async_tasks.update_async_task(
                task_id,
                status="succeeded" if status == "imported" else "running",
                progress_pct=progress_pct,
                clear_error=True,
            )

    def _mark_failed(
        self,
        *,
        import_run_id: int,
        task_id: int | None,
        error_code: str,
        failure_reason: str,
        recoverable: bool,
    ) -> None:
        status = "recoverable" if recoverable else "failed"
        self.bilibili.update_bilibili_import_run(
            import_run_id,
            status=status,
            stage="error",
            error_code=error_code,
            failure_reason=failure_reason,
            recoverable=recoverable,
        )
        if task_id is not None:
            self.async_tasks.update_async_task(
                task_id,
                status="failed",
                error_code=error_code,
                error_message=failure_reason,
            )

    def _mark_canceled(self, *, import_run_id: int, task_id: int | None) -> None:
        self.bilibili.update_bilibili_import_run(
            import_run_id,
            status="canceled",
            stage="canceled",
        )
        if task_id is not None:
            self.async_tasks.update_async_task(task_id, status="canceled")

    def _is_canceled(self, import_run_id: int) -> bool:
        run = self.bilibili.get_bilibili_import_run(import_run_id)
        return isinstance(run, dict) and str(run.get("status")) == "canceled"

    def _raise_if_canceled(self, import_run_id: int) -> None:
        if self._is_canceled(import_run_id):
            raise BilibiliImportCanceled()


class _CancelToken:
    def __init__(self, canceled_factory: Callable[[], bool]) -> None:
        self._canceled_factory = canceled_factory

    @property
    def canceled(self) -> bool:
        return self._canceled_factory()


def run_bilibili_import(
    message: dict[str, Any],
    *,
    bilibili: BilibiliImportRepository | None = None,
    resources: ResourceRepository | None = None,
    async_tasks: AsyncTaskRepository | None = None,
    storage: ObjectStorage | None = None,
    bili_client: Any | None = None,
    downloader: Any | None = None,
    merger: Any | None = None,
    runtime_dir: str | Path = "/tmp/knowlink-bilibili-imports",
) -> dict[str, Any] | None:
    if bilibili is None or resources is None or async_tasks is None or storage is None:
        raise RuntimeError("Bilibili import worker runtime wiring is not configured.")
    return BilibiliImportRunner(
        bilibili=bilibili,
        resources=resources,
        async_tasks=async_tasks,
        storage=storage,
        bili_client=bili_client,
        downloader=downloader,
        merger=merger,
        runtime_dir=runtime_dir,
    ).run(message)


def _int_required(message: dict[str, Any], *keys: str) -> int:
    value = _optional_int(message, *keys)
    if value is None:
        raise ValueError(f"Missing integer value for one of: {', '.join(keys)}")
    return value


def _optional_int(message: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = message.get(key)
        if value is None:
            continue
        return int(value)
    return None


def _part_to_api(part: Any) -> dict[str, Any]:
    if isinstance(part, BilibiliPart):
        return part.to_api()
    if isinstance(part, dict):
        return dict(part)
    return {}


def _extract_media_urls(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("videoUrl") and payload.get("audioUrl"):
        return dict(payload)
    dash = payload.get("dash")
    if isinstance(dash, dict):
        video = _first_media_url(dash.get("video"))
        audio = _first_media_url(dash.get("audio"))
        if video and audio:
            return {"videoUrl": video, "audioUrl": audio, "headers": payload.get("headers") or {}}
    raise BilibiliImportFailure(
        error_code="bilibili.playurl_failed",
        message="Bilibili playurl response did not include video and audio streams.",
    )


def _first_media_url(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("baseUrl") or item.get("base_url")
        if url:
            return str(url)
    return None


def _failure_from_exception(exc: Exception, *, default_error_code: str) -> BilibiliImportFailure:
    if isinstance(exc, BilibiliImportFailure):
        return exc
    error_code = getattr(exc, "error_code", None) or default_error_code
    message = getattr(exc, "message", None) or str(exc) or error_code
    status_code = getattr(exc, "status_code", None)
    recoverable = status_code in {401, 403, 429, 502, 503}
    return BilibiliImportFailure(error_code=str(error_code), message=str(message), recoverable=bool(recoverable))


def _is_canceled_exception(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    return "cancel" in name


def _quality_qn(quality_preference: str) -> int | None:
    return 80 if quality_preference == "android_safe" else None


def _object_key(*, course_id: int, import_run_id: int, part: dict[str, Any], part_index: int) -> str:
    name = _safe_filename(str(part.get("title") or f"part-{part_index}"))
    return f"raw/1/{course_id}/bilibili/{import_run_id}/{part_index:03d}-{name}.mp4"


def _resource_name(preview: dict[str, Any], part: dict[str, Any], *, part_index: int) -> str:
    title = str(preview.get("title") or "bilibili")
    part_title = str(part.get("title") or f"P{part_index}")
    if int(preview.get("totalParts") or 1) > 1:
        return f"{title} - {part_title}.mp4"
    return f"{title}.mp4"


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe or "bilibili"
