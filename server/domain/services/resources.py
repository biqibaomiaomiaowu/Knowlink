from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from server.domain.repositories import CourseRepository, IdempotencyRepository, LessonRepository, ResourceRepository
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import result_matches_course, run_fingerprinted_idempotent
from server.infra.db.base import utcnow
from server.infra.storage import ObjectNotFoundError, ObjectStat, ObjectStorage, ObjectStorageError


UPLOAD_EXPIRES_IN = timedelta(minutes=15)
PLAYBACK_EXPIRES_IN = timedelta(hours=1)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
VIDEO_RESOURCE_TYPES = {"mp4"}
NON_VIDEO_RESOURCE_TYPES = {"pdf", "pptx", "docx", "srt"}


class ResourceService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        resources: ResourceRepository,
        idempotency: IdempotencyRepository,
        lessons: LessonRepository | None = None,
        storage: ObjectStorage | None = None,
    ) -> None:
        self.courses = courses
        self.resources = resources
        self.idempotency = idempotency
        self.lessons = lessons
        self.storage = storage

    def upload_init(self, *, course_id: int, payload, request_host: str) -> dict[str, object]:
        self._ensure_course(course_id)
        scope = self._normalize_scope(course_id=course_id, payload=payload, require_non_video_scope=True)
        storage = self._require_storage()
        object_key = self._build_object_key(course_id=course_id, payload=payload)
        headers = self._upload_headers(course_id, payload, scope=scope)
        try:
            upload_url = storage.presigned_put_url(
                object_key,
                expires=UPLOAD_EXPIRES_IN,
                content_type=payload.mime_type,
                metadata=headers,
            )
        except ObjectStorageError as exc:
            raise ServiceError(
                message="Object storage is unavailable.",
                error_code="storage.unavailable",
                status_code=503,
            ) from exc
        return {
            "uploadUrl": upload_url,
            "objectKey": object_key,
            "headers": headers,
            "expiresAt": utcnow() + UPLOAD_EXPIRES_IN,
        }

    def upload_complete(
        self,
        *,
        course_id: int,
        payload,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)

        def factory() -> dict[str, object]:
            scope = self._normalize_scope(course_id=course_id, payload=payload, require_non_video_scope=True)
            self._validate_uploaded_object(course_id=course_id, payload=payload)
            return self._create_completed_resource(course_id=course_id, payload=payload, scope=scope)

        return run_fingerprinted_idempotent(
            self.idempotency,
            scope=f"resources.upload_complete:{course_id}",
            key=idempotency_key,
            request_payload=payload.model_dump(by_alias=True),
            factory=factory,
            legacy_action="resources.upload_complete",
            legacy_matches=lambda result: result_matches_course(result, course_id=course_id),
        )

    def _upload_complete_payload(self, payload, *, scope: dict[str, object]) -> dict[str, object]:
        data = payload.model_dump(by_alias=True)
        data["scopeType"] = scope["scopeType"]
        data["lessonId"] = scope.get("lessonId")
        data["usageRole"] = scope["usageRole"]
        data["sourceType"] = scope.get("sourceType") or "upload"
        if scope.get("visibleToCourseQa") is not None:
            data["visibleToCourseQa"] = scope["visibleToCourseQa"]
        else:
            data.setdefault("visibleToCourseQa", scope["scopeType"] == "course")
        if scope.get("sourcePartId") is not None:
            data["sourcePartId"] = scope["sourcePartId"]
        return data

    def list_resources(
        self,
        *,
        course_id: int,
        scope_type: str | None = None,
        lesson_id: int | None = None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        items = self.resources.list_resources(course_id)
        if scope_type is not None:
            items = [item for item in items if item.get("scopeType") == scope_type]
        if lesson_id is not None:
            items = [item for item in items if item.get("lessonId") == lesson_id]
        return {"items": items}

    def get_playback(self, *, resource_id: int) -> dict[str, object]:
        resource = self.resources.get_resource(resource_id)
        if resource is None:
            raise ServiceError(
                message="Resource was not found.",
                error_code="resource.not_found",
                status_code=404,
            )
        if resource.get("resourceType") not in VIDEO_RESOURCE_TYPES:
            raise ServiceError(
                message="Resource is not a playable video.",
                error_code="resource.not_video",
                status_code=409,
            )

        storage = self._require_playback_storage()
        object_key = str(resource.get("objectKey") or "")
        expires_at = utcnow() + PLAYBACK_EXPIRES_IN
        try:
            playback_url = storage.presigned_get_url(object_key, expires=PLAYBACK_EXPIRES_IN)
        except ObjectStorageError as exc:
            raise ServiceError(
                message="Playback URL is unavailable.",
                error_code="resource.playback_unavailable",
                status_code=503,
            ) from exc
        return {
            "resourceId": resource["resourceId"],
            "resourceType": resource["resourceType"],
            "playbackUrl": playback_url,
            "mimeType": resource["mimeType"],
            "expiresAt": expires_at,
            "durationSec": None,
        }

    def delete_resource(self, *, course_id: int, resource_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        blockers_getter = getattr(self.resources, "get_resource_delete_blockers", None)
        if callable(blockers_getter):
            blockers = blockers_getter(course_id, resource_id)
            if blockers:
                summary = ", ".join(f"{name}={count}" for name, count in sorted(blockers.items()))
                raise ServiceError(
                    message=f"Resource has dependent backend artifacts and cannot be deleted safely: {summary}.",
                    error_code="resource.has_dependents",
                    status_code=409,
                )
        deleted = self.resources.delete_resource(course_id, resource_id)
        if not deleted:
            raise ServiceError(
                message="Resource was not found.",
                error_code="resource.not_found",
                status_code=404,
            )
        return {"deleted": True, "resourceId": resource_id}

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _ensure_lesson(self, *, course_id: int, lesson_id: int | None) -> dict[str, Any]:
        if lesson_id is None or self.lessons is None:
            raise ServiceError(
                message="Resource lesson scope requires a lesson in this course.",
                error_code="resource.lesson_mismatch",
                status_code=400,
            )
        lesson = self.lessons.get_lesson(course_id=course_id, lesson_id=int(lesson_id))
        if lesson is None:
            raise ServiceError(
                message="Resource lesson scope requires a lesson in this course.",
                error_code="resource.lesson_mismatch",
                status_code=400,
            )
        return lesson

    def _normalize_scope(
        self,
        *,
        course_id: int,
        payload,
        require_non_video_scope: bool,
    ) -> dict[str, object]:
        resource_type = str(payload.resource_type)
        if resource_type in VIDEO_RESOURCE_TYPES:
            return self._normalize_video_scope(course_id=course_id, payload=payload)
        return self._normalize_non_video_scope(
            course_id=course_id,
            payload=payload,
            require_scope=require_non_video_scope,
        )

    def _normalize_non_video_scope(
        self,
        *,
        course_id: int,
        payload,
        require_scope: bool,
    ) -> dict[str, object]:
        scope_type = payload.scope_type
        if scope_type is None:
            if require_scope:
                raise ServiceError(
                    message="Resource scope is required for document uploads.",
                    error_code="resource.scope_required",
                    status_code=400,
                )
            scope_type = "course"
        if scope_type == "lesson":
            lesson = self._ensure_lesson(course_id=course_id, lesson_id=payload.lesson_id)
            usage_role = payload.usage_role or ("transcript" if payload.resource_type == "srt" else "lesson_material")
            return {
                "scopeType": "lesson",
                "lessonId": int(lesson["lessonId"]),
                "usageRole": usage_role,
                "visibleToCourseQa": payload.visible_to_course_qa
                if payload.visible_to_course_qa is not None
                else False,
                "sourcePartId": payload.source_part_id,
                "sourceType": "upload",
            }
        return {
            "scopeType": "course",
            "lessonId": None,
            "usageRole": payload.usage_role or "course_material",
            "visibleToCourseQa": payload.visible_to_course_qa
            if payload.visible_to_course_qa is not None
            else True,
            "sourcePartId": payload.source_part_id,
            "sourceType": "upload",
        }

    def _normalize_video_scope(self, *, course_id: int, payload) -> dict[str, object]:
        placement = payload.lesson_placement
        if placement is None:
            if payload.scope_type == "course":
                placement = "course_material"
            elif payload.scope_type == "lesson" and payload.lesson_id is not None:
                placement = "bind_existing"
            else:
                placement = "auto_create"
        if placement == "course_material":
            return {
                "scopeType": "course",
                "lessonId": None,
                "usageRole": payload.usage_role or "course_material",
                "visibleToCourseQa": payload.visible_to_course_qa
                if payload.visible_to_course_qa is not None
                else True,
                "sourcePartId": payload.source_part_id,
                "sourceType": "local_video",
                "lessonPlacement": placement,
            }
        if placement == "bind_existing":
            lesson = self._ensure_lesson(course_id=course_id, lesson_id=payload.lesson_id)
            return {
                "scopeType": "lesson",
                "lessonId": int(lesson["lessonId"]),
                "usageRole": "primary_video",
                "visibleToCourseQa": payload.visible_to_course_qa
                if payload.visible_to_course_qa is not None
                else False,
                "sourcePartId": payload.source_part_id,
                "sourceType": "local_video",
                "lessonPlacement": placement,
            }
        return {
            "scopeType": "lesson",
            "lessonId": None,
            "usageRole": "primary_video",
            "visibleToCourseQa": payload.visible_to_course_qa
            if payload.visible_to_course_qa is not None
            else False,
            "sourcePartId": payload.source_part_id,
            "sourceType": "local_video",
            "lessonPlacement": "auto_create",
        }

    def _create_completed_resource(
        self,
        *,
        course_id: int,
        payload,
        scope: dict[str, object],
    ) -> dict[str, object]:
        if payload.resource_type != "mp4":
            return self.resources.create_resource(course_id, self._upload_complete_payload(payload, scope=scope))
        if scope.get("lessonPlacement") == "auto_create":
            lesson = self._create_video_lesson(course_id=course_id, payload=payload)
            scope = {**scope, "lessonId": lesson["lessonId"]}
            resource = self.resources.create_resource(course_id, self._upload_complete_payload(payload, scope=scope))
            self._set_lesson_primary_video(course_id=course_id, lesson_id=int(lesson["lessonId"]), resource=resource)
            return resource
        resource = self.resources.create_resource(course_id, self._upload_complete_payload(payload, scope=scope))
        if scope.get("lessonPlacement") == "bind_existing" and scope.get("lessonId") is not None:
            self._set_lesson_primary_video(course_id=course_id, lesson_id=int(scope["lessonId"]), resource=resource)
        return resource

    def _create_video_lesson(self, *, course_id: int, payload) -> dict[str, Any]:
        if self.lessons is None:
            raise ServiceError(
                message="Lesson repository is unavailable for video placement.",
                error_code="resource.lesson_mismatch",
                status_code=400,
            )
        title = payload.lesson_title or self._lesson_title_from_upload(payload.original_name)
        return self.lessons.create_lesson(
            course_id=course_id,
            title=title,
            source_type="local_video",
            source_ref_json={
                "objectKey": payload.object_key,
                "originalName": payload.original_name,
            },
        )

    def _set_lesson_primary_video(
        self,
        *,
        course_id: int,
        lesson_id: int,
        resource: dict[str, object],
    ) -> None:
        if self.lessons is None:
            return
        self.lessons.update_lesson(
            course_id=course_id,
            lesson_id=lesson_id,
            changes={
                "primary_video_resource_id": int(resource["resourceId"]),
                "lesson_status": "resource_ready",
            },
        )

    @staticmethod
    def _lesson_title_from_upload(original_name: str) -> str:
        title = Path(original_name.replace("\\", "/").rsplit("/", 1)[-1]).stem.strip()
        return title or "未命名视频"

    def _build_object_key(self, *, course_id: int, payload) -> str:
        filename = payload.filename.replace("\\", "/").rsplit("/", 1)[-1]
        safe_filename = SAFE_FILENAME_RE.sub("_", filename).strip(" .")
        if safe_filename in {"", ".", ".."}:
            safe_filename = f"upload.{payload.resource_type}"
        return f"raw/1/{course_id}/temp/{payload.resource_type}/{safe_filename}"

    def _upload_headers(self, course_id: int, payload, *, scope: dict[str, object]) -> dict[str, str]:
        headers = {"x-amz-meta-course-id": str(course_id)}
        headers["x-amz-meta-scope-type"] = str(scope["scopeType"])
        if scope.get("lessonId") is not None:
            headers["x-amz-meta-lesson-id"] = str(scope["lessonId"])
        checksum = self._normalize_checksum(payload.checksum)
        if checksum is not None:
            headers["x-amz-meta-checksum"] = checksum
            if checksum.startswith("sha256:"):
                headers["x-amz-meta-sha256"] = checksum.split(":", 1)[1]
        return headers

    def _validate_uploaded_object(self, *, course_id: int, payload) -> None:
        object_key = payload.object_key
        if not self._is_allowed_object_key(course_id, object_key):
            raise ServiceError(
                message="Object key is not allowed for this course.",
                error_code="storage.object_key_invalid",
                status_code=400,
            )

        storage = self._require_storage()
        try:
            stat = storage.stat_object(object_key)
        except ObjectNotFoundError as exc:
            raise ServiceError(
                message="Uploaded object was not found in object storage.",
                error_code="storage.object_not_found",
                status_code=400,
            ) from exc
        except ObjectStorageError as exc:
            raise ServiceError(
                message="Object storage is unavailable.",
                error_code="storage.unavailable",
                status_code=503,
            ) from exc

        self._validate_object_stat(stat, payload=payload)

    def _validate_object_stat(self, stat: ObjectStat, *, payload) -> None:
        if stat.size_bytes is not None and stat.size_bytes != payload.size_bytes:
            raise ServiceError(
                message="Uploaded object size does not match upload metadata.",
                error_code="storage.object_size_mismatch",
                status_code=409,
            )

        stat_checksum = self._normalize_checksum(stat.checksum)
        payload_checksum = self._normalize_checksum(payload.checksum)
        if payload_checksum is None and stat.checksum_required:
            raise ServiceError(
                message="Uploaded object checksum is missing.",
                error_code="storage.object_checksum_mismatch",
                status_code=409,
            )
        if payload_checksum is not None and stat_checksum is None and stat.checksum_required:
            raise ServiceError(
                message="Uploaded object checksum metadata is missing.",
                error_code="storage.object_checksum_mismatch",
                status_code=409,
            )
        if stat_checksum is not None and stat_checksum != payload_checksum:
            raise ServiceError(
                message="Uploaded object checksum does not match upload metadata.",
                error_code="storage.object_checksum_mismatch",
                status_code=409,
            )

    def _require_storage(self) -> ObjectStorage:
        if self.storage is None:
            raise ServiceError(
                message="Object storage is not configured.",
                error_code="storage.unavailable",
                status_code=503,
            )
        return self.storage

    def _require_playback_storage(self) -> ObjectStorage:
        if self.storage is None:
            raise ServiceError(
                message="Playback URL is unavailable.",
                error_code="resource.playback_unavailable",
                status_code=503,
            )
        return self.storage

    def _is_allowed_object_key(self, course_id: int, object_key: str) -> bool:
        if not object_key or object_key.startswith("/") or "\\" in object_key:
            return False
        prefix = f"raw/1/{course_id}/"
        if not object_key.startswith(prefix):
            return False
        segments = object_key.split("/")
        if any(segment in {"", ".", ".."} for segment in segments):
            return False
        decoded_segments = [unquote(segment) for segment in segments]
        return not any(segment in {"", ".", ".."} for segment in decoded_segments)

    def _normalize_checksum(self, checksum: str | None) -> str | None:
        if checksum is None:
            return None
        value = checksum.strip()
        if not value:
            return None
        if value.lower().startswith("sha256:"):
            return f"sha256:{value.split(':', 1)[1].lower()}"
        return value
