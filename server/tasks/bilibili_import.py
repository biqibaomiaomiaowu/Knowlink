from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from server.domain.repositories.interfaces import (
    AsyncTaskRepository,
    BilibiliImportRepository,
    LessonRepository,
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


_PART_BVID_RE = re.compile(r"(?:^|-)bv-(BV[0-9A-Za-z]{10})(?:-|$)")


class BilibiliImportRunner:
    def __init__(
        self,
        *,
        bilibili: BilibiliImportRepository,
        resources: ResourceRepository,
        async_tasks: AsyncTaskRepository,
        storage: ObjectStorage,
        lessons: LessonRepository | None = None,
        bili_client: Any | None = None,
        downloader: Any | None = None,
        merger: Any | None = None,
        runtime_dir: str | Path = "/tmp/knowlink-bilibili-imports",
    ) -> None:
        self.bilibili = bilibili
        self.resources = resources
        self.lessons = lessons or getattr(resources, "store", resources)
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
            parts = self._selected_parts(
                preview,
                self._latest_selection(import_run_id, fallback=run.get("selection") or {}),
            )
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
                    selection=self._latest_selection(import_run_id, fallback=run.get("selection") or {}),
                    preview=preview,
                    part=part,
                    part_index=index,
                    total_parts=len(parts),
                    cookies=cookies,
                    work_dir=work_dir,
                    cancel_token=cancel_token,
                    task_id=task_id,
                )
                resource_id = int(resource["resourceId"])
                if resource_id not in resource_ids:
                    resource_ids.append(resource_id)

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
        part_id = _part_id(part, part_index=part_index)
        selection = self._latest_selection(import_run_id, fallback=selection)
        existing_resource = self._existing_part_resource(
            course_id=course_id,
            import_run_id=import_run_id,
            selection=selection,
            part_id=part_id,
        )
        if existing_resource is None:
            existing_resource = self._existing_import_resource(
                course_id=course_id,
                import_run_id=import_run_id,
                selection=selection,
                part_id=part_id,
            )
        if existing_resource is not None:
            return self._reuse_existing_part_resource(
                import_run_id=import_run_id,
                course_id=course_id,
                source_url=source_url,
                selection=selection,
                preview=preview,
                part=part,
                part_id=part_id,
                part_index=part_index,
                resource=existing_resource,
            )

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
        binding = self._prepare_part_binding(
            course_id=course_id,
            import_run_id=import_run_id,
            source_url=source_url,
            selection=selection,
            preview=preview,
            part=part,
            part_id=part_id,
            part_index=part_index,
        )
        selection = binding["selection"]
        self._upsert_import_item(
            import_run_id=import_run_id,
            course_id=course_id,
            source_url=source_url,
            preview=preview,
            part=part,
            part_id=part_id,
            part_index=part_index,
            status="binding_ready",
            progress_pct=progress_base,
            lesson_id=binding.get("lessonId"),
            resource_id=None,
            metadata={
                "sourcePartId": part_id,
                "scopeType": binding["scopeType"],
                "usageRole": binding["usageRole"],
                "cid": part.get("cid"),
                "pageNo": part.get("pageNo"),
                "durationSec": part.get("durationSec"),
            },
        )
        self._raise_if_canceled(import_run_id)
        try:
            stat = self.storage.upload_file(
                object_key,
                merged_path,
                content_type="video/mp4",
                metadata=self._upload_metadata(
                    course_id=course_id,
                    import_run_id=import_run_id,
                    binding=binding,
                ),
            )
        except Exception as exc:
            raise _failure_from_exception(exc, default_error_code="bilibili.upload_failed") from exc

        try:
            self._raise_if_canceled(import_run_id)
        except BilibiliImportCanceled:
            self._delete_uploaded_object(object_key)
            raise
        self._advance(
            import_run_id=import_run_id,
            task_id=task_id,
            status="uploading",
            stage="resource_import",
            progress_pct=min(progress_base + int(progress_span * 0.9), 98),
        )
        self._raise_if_canceled(import_run_id)
        try:
            resource = self.resources.create_resource(
                course_id,
                {
                    "resourceType": "mp4",
                    "scopeType": binding["scopeType"],
                    "lessonId": binding.get("lessonId"),
                    "usageRole": binding["usageRole"],
                    "sourceType": self._resource_source_type(preview=preview, selection=selection),
                    "sourcePartId": part_id,
                    "originUrl": source_url,
                    "objectKey": object_key,
                    "originalName": _resource_name(preview, part, part_index=part_index),
                    "mimeType": "video/mp4",
                    "sizeBytes": getattr(stat, "size_bytes", None),
                    "checksum": getattr(stat, "checksum", None),
                    "durationSec": part.get("durationSec"),
                    "parsePolicyJson": {"source": "bilibili", "importRunId": import_run_id},
                    "visibleToCourseQa": binding["scopeType"] == "course",
                },
            )
            lesson_id = binding.get("lessonId")
            if lesson_id is not None and binding.get("usageRole") == "primary_video":
                self._set_lesson_primary_video(
                    course_id=course_id,
                    lesson_id=int(lesson_id),
                    resource_id=int(resource["resourceId"]),
                )
            self._persist_part_mapping(
                import_run_id=import_run_id,
                selection=selection,
                part_id=part_id,
                values={
                    "lessonId": lesson_id,
                    "resourceId": int(resource["resourceId"]),
                    "sourcePartId": part_id,
                },
            )
            self._upsert_import_item(
                import_run_id=import_run_id,
                course_id=course_id,
                source_url=source_url,
                preview=preview,
                part=part,
                part_id=part_id,
                part_index=part_index,
                status="imported",
                progress_pct=100,
                lesson_id=lesson_id,
                resource_id=int(resource["resourceId"]),
                metadata={
                    "sourcePartId": part_id,
                    "scopeType": binding["scopeType"],
                    "usageRole": binding["usageRole"],
                    "resourceId": int(resource["resourceId"]),
                    "cid": part.get("cid"),
                    "pageNo": part.get("pageNo"),
                    "durationSec": part.get("durationSec"),
                },
            )
            return resource
        except Exception as exc:
            raise _failure_from_exception(exc, default_error_code="bilibili.import_failed") from exc

    def _existing_part_resource(
        self,
        *,
        course_id: int,
        import_run_id: int,
        selection: dict[str, Any],
        part_id: str,
    ) -> dict[str, Any] | None:
        mapping = _part_lesson_map(selection).get(part_id)
        if not isinstance(mapping, dict):
            return None
        resource_id = mapping.get("resourceId")
        if resource_id is None:
            return None
        try:
            resource = self.resources.get_resource(int(resource_id))
        except (TypeError, ValueError):
            return None
        if not isinstance(resource, dict):
            return None
        return (
            resource
            if self._resource_matches_import(
                resource=resource,
                course_id=course_id,
                import_run_id=import_run_id,
                selection=selection,
                part_id=part_id,
            )
            else None
        )

    def _existing_import_resource(
        self,
        *,
        course_id: int,
        import_run_id: int,
        selection: dict[str, Any],
        part_id: str,
    ) -> dict[str, Any] | None:
        list_resources = getattr(self.resources, "list_resources", None)
        if not callable(list_resources):
            return None
        for resource in list_resources(course_id):
            if self._resource_matches_import(
                resource=resource,
                course_id=course_id,
                import_run_id=import_run_id,
                selection=selection,
                part_id=part_id,
            ):
                return resource
        return None

    def _resource_matches_import(
        self,
        *,
        resource: dict[str, Any],
        course_id: int,
        import_run_id: int,
        selection: dict[str, Any],
        part_id: str,
    ) -> bool:
        if int(resource.get("courseId") or 0) != int(course_id):
            return False
        if str(resource.get("sourcePartId") or "") != part_id:
            return False
        parse_policy = resource.get("parsePolicyJson")
        if not isinstance(parse_policy, dict):
            return False
        try:
            if int(parse_policy.get("importRunId")) != int(import_run_id):
                return False
        except (TypeError, ValueError):
            return False
        mapping = _part_lesson_map(selection).get(part_id)
        if isinstance(mapping, dict):
            mapped_source_part_id = mapping.get("sourcePartId")
            if mapped_source_part_id is not None and str(mapped_source_part_id) != part_id:
                return False
            mapped_lesson_id = mapping.get("lessonId")
            if mapped_lesson_id is not None:
                try:
                    if int(resource.get("lessonId") or 0) != int(mapped_lesson_id):
                        return False
                except (TypeError, ValueError):
                    return False
        return True

    def _reuse_existing_part_resource(
        self,
        *,
        import_run_id: int,
        course_id: int,
        source_url: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        part: dict[str, Any],
        part_id: str,
        part_index: int,
        resource: dict[str, Any],
    ) -> dict[str, Any]:
        lesson_id = resource.get("lessonId")
        if lesson_id is not None and resource.get("usageRole") == "primary_video":
            self._set_lesson_primary_video(
                course_id=course_id,
                lesson_id=int(lesson_id),
                resource_id=int(resource["resourceId"]),
            )
        self._persist_part_mapping(
            import_run_id=import_run_id,
            selection=selection,
            part_id=part_id,
            values={
                "lessonId": lesson_id,
                "resourceId": int(resource["resourceId"]),
                "sourcePartId": part_id,
            },
        )
        self._upsert_import_item(
            import_run_id=import_run_id,
            course_id=course_id,
            source_url=source_url,
            preview=preview,
            part=part,
            part_id=part_id,
            part_index=part_index,
            status="imported",
            progress_pct=100,
            lesson_id=lesson_id,
            resource_id=int(resource["resourceId"]),
            metadata={
                "sourcePartId": part_id,
                "scopeType": resource.get("scopeType"),
                "usageRole": resource.get("usageRole"),
                "resourceId": int(resource["resourceId"]),
            },
        )
        return resource

    def _prepare_part_binding(
        self,
        *,
        course_id: int,
        import_run_id: int,
        source_url: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        part: dict[str, Any],
        part_id: str,
        part_index: int,
    ) -> dict[str, Any]:
        lesson_mode = selection.get("lessonMode")
        if lesson_mode is None:
            return {
                "scopeType": "course",
                "lessonId": None,
                "usageRole": "course_material",
                "selection": selection,
            }
        if lesson_mode == "course_material":
            return {
                "scopeType": "course",
                "lessonId": None,
                "usageRole": "course_material",
                "selection": self._persist_part_mapping(
                    import_run_id=import_run_id,
                    selection=selection,
                    part_id=part_id,
                    values={"lessonId": None, "sourcePartId": part_id},
                ),
            }
        if lesson_mode == "bind_existing":
            lesson_id = _optional_int(selection, "targetLessonId", "target_lesson_id")
            self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
            return {
                "scopeType": "lesson",
                "lessonId": lesson_id,
                "usageRole": "primary_video",
                "selection": self._persist_part_mapping(
                    import_run_id=import_run_id,
                    selection=selection,
                    part_id=part_id,
                    values={"lessonId": lesson_id, "sourcePartId": part_id},
                ),
            }
        lesson = self._ensure_or_create_part_lesson(
            course_id=course_id,
            import_run_id=import_run_id,
            source_url=source_url,
            selection=selection,
            preview=preview,
            part=part,
            part_id=part_id,
            part_index=part_index,
        )
        return {
            "scopeType": "lesson",
            "lessonId": int(lesson["lessonId"]),
            "usageRole": "primary_video",
            "selection": self._persist_part_mapping(
                import_run_id=import_run_id,
                selection=selection,
                part_id=part_id,
                values={"lessonId": int(lesson["lessonId"]), "sourcePartId": part_id},
            ),
        }

    def _ensure_or_create_part_lesson(
        self,
        *,
        course_id: int,
        import_run_id: int,
        source_url: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        part: dict[str, Any],
        part_id: str,
        part_index: int,
    ) -> dict[str, Any]:
        mapping = _part_lesson_map(selection).get(part_id)
        if isinstance(mapping, dict):
            lesson_id = mapping.get("lessonId")
            lesson = self._get_lesson(course_id=course_id, lesson_id=lesson_id)
            if lesson is not None:
                return lesson
        if selection.get("createLessonIfMissing") is False:
            raise BilibiliImportFailure(
                error_code="resource.lesson_mismatch",
                message="Bilibili import item is missing a target lesson.",
            )
        creator = getattr(self.lessons, "create_lesson", None)
        if not callable(creator):
            raise BilibiliImportFailure(
                error_code="resource.lesson_mismatch",
                message="Lesson repository is unavailable for Bilibili import.",
            )
        return creator(
            course_id=course_id,
            title=_lesson_title(selection=selection, preview=preview, part=part, part_index=part_index),
            source_type=self._resource_source_type(preview=preview, selection=selection),
            source_ref_json={
                "sourceUrl": source_url,
                "importRunId": import_run_id,
                "sourcePartId": part_id,
                "cid": part.get("cid"),
                "pageNo": part.get("pageNo"),
            },
        )

    def _get_lesson(self, *, course_id: int, lesson_id: Any) -> dict[str, Any] | None:
        if lesson_id is None:
            return None
        getter = getattr(self.lessons, "get_lesson", None)
        if not callable(getter):
            return None
        try:
            return getter(course_id=course_id, lesson_id=int(lesson_id))
        except (TypeError, ValueError):
            return None

    def _ensure_lesson(self, *, course_id: int, lesson_id: int | None) -> dict[str, Any]:
        lesson = self._get_lesson(course_id=course_id, lesson_id=lesson_id)
        if lesson is None:
            raise BilibiliImportFailure(
                error_code="resource.lesson_mismatch",
                message="Bilibili import target lesson does not belong to this course.",
            )
        return lesson

    def _set_lesson_primary_video(self, *, course_id: int, lesson_id: int, resource_id: int) -> None:
        updater = getattr(self.lessons, "update_lesson", None)
        if callable(updater):
            updater(
                course_id=course_id,
                lesson_id=lesson_id,
                changes={
                    "primary_video_resource_id": resource_id,
                    "lesson_status": "resource_ready",
                },
            )

    def _persist_part_mapping(
        self,
        *,
        import_run_id: int,
        selection: dict[str, Any],
        part_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        updated_selection = self._latest_selection(import_run_id, fallback=selection)
        part_lesson_map = dict(updated_selection.get("partLessonMap") or {})
        existing = dict(part_lesson_map.get(part_id) or {})
        existing.update(values)
        part_lesson_map[part_id] = existing
        updated_selection["partLessonMap"] = part_lesson_map
        self.bilibili.update_bilibili_import_run(import_run_id, selection=updated_selection)
        return updated_selection

    def _latest_selection(self, import_run_id: int, *, fallback: dict[str, Any]) -> dict[str, Any]:
        run = self.bilibili.get_bilibili_import_run(import_run_id)
        selection = run.get("selection") if isinstance(run, dict) else None
        if isinstance(selection, dict):
            return dict(selection)
        return dict(fallback)

    def _upsert_import_item(
        self,
        *,
        import_run_id: int,
        course_id: int,
        source_url: str,
        preview: dict[str, Any],
        part: dict[str, Any],
        part_id: str,
        part_index: int,
        status: str,
        progress_pct: int,
        lesson_id: Any,
        resource_id: int | None,
        metadata: dict[str, Any],
    ) -> None:
        upsert = getattr(self.bilibili, "upsert_bilibili_import_item", None)
        if not callable(upsert):
            return
        normalized_lesson_id = int(lesson_id) if lesson_id is not None else None
        upsert(
            import_run_id=import_run_id,
            course_id=course_id,
            source_url=source_url,
            item_key=part_id,
            title=_resource_name(preview, part, part_index=part_index),
            part_no=_optional_positive_int(part.get("pageNo")) or part_index,
            status=status,
            progress_pct=progress_pct,
            lesson_id=normalized_lesson_id,
            resource_id=resource_id,
            metadata_json={key: value for key, value in metadata.items() if value is not None},
            error_code=None,
            failure_reason=None,
        )

    @staticmethod
    def _upload_metadata(
        *,
        course_id: int,
        import_run_id: int,
        binding: dict[str, Any],
    ) -> dict[str, str]:
        metadata = {
            "x-amz-meta-course-id": str(course_id),
            "x-amz-meta-source": "bilibili",
            "x-amz-meta-import-run-id": str(import_run_id),
            "x-amz-meta-scope-type": str(binding["scopeType"]),
        }
        if binding.get("lessonId") is not None:
            metadata["x-amz-meta-lesson-id"] = str(binding["lessonId"])
        return metadata

    @staticmethod
    def _resource_source_type(*, preview: dict[str, Any], selection: dict[str, Any]) -> str:
        if selection.get("lessonMode") is None:
            return "bilibili"
        source_type = str(preview.get("sourceType") or "")
        if source_type == "collection":
            return "bilibili_collection_item"
        if source_type == "bangumi":
            return "bilibili_bangumi_item"
        return "bilibili_part"

    def _delete_uploaded_object(self, object_key: str) -> None:
        delete_object = getattr(self.storage, "delete_object", None)
        if not callable(delete_object):
            raise BilibiliImportFailure(
                error_code="bilibili.cancel_failed",
                message=f"Canceled after upload but storage cannot delete object: {object_key}",
            )
        try:
            delete_object(object_key)
        except Exception as exc:
            raise BilibiliImportFailure(
                error_code="bilibili.cancel_failed",
                message=f"Canceled after upload but failed to delete object: {object_key}",
            ) from exc

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
            payload = self.bili_client.playurl(
                bvid=_bvid_for_playurl(source_url, part),
                cid=int(part["cid"]),
                cookies=cookies,
                qn=_quality_qn(quality_preference),
            )
        return _extract_media_urls(payload)

    def _auth_cookies(self) -> dict[str, Any]:
        auth = self.bilibili.get_bilibili_auth_session()
        if not isinstance(auth, dict):
            return {}
        if str(auth.get("status") or "") != "active":
            return {}
        expires_at = auth.get("expiresAt") or auth.get("expires_at")
        if isinstance(expires_at, datetime):
            if expires_at.tzinfo is None or expires_at.utcoffset() is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
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
    lessons: LessonRepository | None = None,
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
        lessons=lessons,
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


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _part_to_api(part: Any) -> dict[str, Any]:
    if isinstance(part, BilibiliPart):
        return part.to_api()
    if isinstance(part, dict):
        return dict(part)
    return {}


def _part_id(part: dict[str, Any], *, part_index: int) -> str:
    return str(part.get("partId") or f"part-{part_index}")


def _part_lesson_map(selection: dict[str, Any]) -> dict[str, Any]:
    mapping = selection.get("partLessonMap")
    return dict(mapping) if isinstance(mapping, dict) else {}


def _lesson_title(
    *,
    selection: dict[str, Any],
    preview: dict[str, Any],
    part: dict[str, Any],
    part_index: int,
) -> str:
    part_id = _part_id(part, part_index=part_index)
    title_overrides = selection.get("partLessonTitles")
    if isinstance(title_overrides, dict):
        override = str(title_overrides.get(part_id) or "").strip()
        if override:
            return override
    title = str(part.get("title") or "").strip()
    if title:
        return title
    preview_title = str(preview.get("title") or "").strip()
    return f"{preview_title} P{part_index}".strip() or f"P{part_index}"


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


def _bvid_for_playurl(source_url: str, part: dict[str, Any]) -> str:
    direct = part.get("bvid") or part.get("bvidUpper")
    if direct:
        return str(direct)
    part_id = str(part.get("partId") or "")
    match = _PART_BVID_RE.search(part_id)
    if match:
        return match.group(1)
    parsed = parse_bilibili_url(source_url)
    if parsed.bvid:
        return parsed.bvid
    raise BilibiliImportFailure(
        error_code="bilibili.playurl_failed",
        message="Bilibili import part did not include a playable bvid.",
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
