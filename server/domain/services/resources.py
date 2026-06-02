from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import unquote

from server.domain.repositories import CourseRepository, IdempotencyRepository, ResourceRepository
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import result_matches_course, run_fingerprinted_idempotent
from server.infra.db.base import utcnow
from server.infra.storage import ObjectNotFoundError, ObjectStat, ObjectStorage, ObjectStorageError


UPLOAD_EXPIRES_IN = timedelta(minutes=15)
PLAYBACK_EXPIRES_IN = timedelta(hours=1)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
VIDEO_RESOURCE_TYPES = {"mp4"}


class ResourceService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        resources: ResourceRepository,
        idempotency: IdempotencyRepository,
        storage: ObjectStorage | None = None,
    ) -> None:
        self.courses = courses
        self.resources = resources
        self.idempotency = idempotency
        self.storage = storage

    def upload_init(self, *, course_id: int, payload, request_host: str) -> dict[str, object]:
        self._ensure_course(course_id)
        storage = self._require_storage()
        object_key = self._build_object_key(course_id=course_id, payload=payload)
        headers = self._upload_headers(course_id, payload)
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
            self._validate_uploaded_object(course_id=course_id, payload=payload)
            return self.resources.create_resource(
                course_id,
                self._upload_complete_payload(payload),
            )

        return run_fingerprinted_idempotent(
            self.idempotency,
            scope=f"resources.upload_complete:{course_id}",
            key=idempotency_key,
            request_payload=payload.model_dump(by_alias=True),
            factory=factory,
            legacy_action="resources.upload_complete",
            legacy_matches=lambda result: result_matches_course(result, course_id=course_id),
        )

    def _upload_complete_payload(self, payload) -> dict[str, object]:
        data = payload.model_dump(by_alias=True)
        data.setdefault("scopeType", "course")
        data.setdefault("usageRole", "course_material")
        data.setdefault("visibleToCourseQa", True)
        return data

    def list_resources(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return {"items": self.resources.list_resources(course_id)}

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

    def _build_object_key(self, *, course_id: int, payload) -> str:
        filename = payload.filename.replace("\\", "/").rsplit("/", 1)[-1]
        safe_filename = SAFE_FILENAME_RE.sub("_", filename).strip(" .")
        if safe_filename in {"", ".", ".."}:
            safe_filename = f"upload.{payload.resource_type}"
        return f"raw/1/{course_id}/temp/{payload.resource_type}/{safe_filename}"

    def _upload_headers(self, course_id: int, payload) -> dict[str, str]:
        headers = {"x-amz-meta-course-id": str(course_id)}
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
