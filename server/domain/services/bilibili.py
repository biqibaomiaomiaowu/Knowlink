from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from server.domain.services.async_tasks import (
    _call_with_supported_kwargs,
    enqueue_or_fail_if_missing_dispatcher,
)
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import run_scoped_idempotent


TERMINAL_NONE_STATUSES = {"imported", "canceled"}
RETRY_STATUSES = {"failed", "recoverable"}


class BilibiliService:
    def __init__(
        self,
        *,
        courses: Any,
        bilibili: Any,
        async_tasks: Any,
        task_dispatcher: Any,
        bili_client: Any,
    ) -> None:
        self.courses = courses
        self.bilibili = bilibili
        self.async_tasks = async_tasks
        self.task_dispatcher = task_dispatcher
        self.bili_client = bili_client

    def preview_import(
        self,
        *,
        course_id: int,
        source_url: str,
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        auth = self._require_auth_session()
        preview = self._normalize_preview(
            self.bili_client.preview(source_url, self._cookies_from_auth(auth))
        )
        preview_id = str(preview["previewId"])
        _call_with_supported_kwargs(
            self.bilibili.save_bilibili_preview_snapshot,
            preview_id=preview_id,
            course_id=course_id,
            source_url=source_url,
            source_type=str(preview["sourceType"]),
            preview=preview,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        return preview

    def create_import(
        self,
        *,
        course_id: int,
        preview_id: str | None,
        source_url: str | None,
        selection_mode: str | None,
        selected_part_ids: list[str],
        quality_preference: str | None,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        self._require_auth_session()
        action = f"bilibili.import_create:{course_id}"
        request_fingerprint = self._request_fingerprint(
            preview_id=preview_id,
            source_url=source_url,
            selection_mode=selection_mode,
            selected_part_ids=selected_part_ids,
            quality_preference=quality_preference,
        )
        existing = self._get_idempotency_result(action=action, key=idempotency_key)
        if existing is not None:
            if not self._idempotent_result_matches_request(
                existing,
                course_id=course_id,
                request_fingerprint=request_fingerprint,
                source_url=source_url,
                preview_id=preview_id,
                selection_mode=selection_mode,
                selected_part_ids=selected_part_ids,
                quality_preference=quality_preference,
            ):
                raise ServiceError(
                    message="Idempotency key was reused with a different Bilibili import request body.",
                    error_code="idempotency.body_mismatch",
                    status_code=409,
                )
            return existing

        preview_entry = self._get_preview_entry(
            course_id=course_id,
            preview_id=preview_id,
            source_url=source_url,
        )
        preview = preview_entry["preview"]
        normalized_selection_mode = selection_mode or preview.get("defaultSelectionMode") or "current_part"
        normalized_quality_preference = quality_preference or "android_safe"
        self._validate_selection(
            preview=preview,
            selection_mode=normalized_selection_mode,
            selected_part_ids=selected_part_ids,
        )
        return run_scoped_idempotent(
            self.bilibili,
            action=action,
            key=idempotency_key,
            factory=lambda: self._create_import_run_task(
                course_id=course_id,
                source_url=str(source_url),
                preview=preview,
                selection_mode=str(normalized_selection_mode),
                selected_part_ids=selected_part_ids,
                quality_preference=str(normalized_quality_preference),
                request_fingerprint=request_fingerprint,
            ),
        )

    def list_imports(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        runs = _call_with_supported_kwargs(
            self.bilibili.list_bilibili_import_runs,
            course_id=course_id,
        )
        return {"items": [self._run_response(run) for run in runs]}

    def get_import_status(self, *, import_run_id: int) -> dict[str, object]:
        run = self._get_import_run(import_run_id)
        return self._run_response(run)

    def cancel_import(
        self,
        *,
        import_run_id: int,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        run = self._get_import_run(import_run_id)
        if run.get("status") == "imported":
            raise ServiceError(
                message="Imported Bilibili import run cannot be canceled.",
                error_code="bilibili.cancel_failed",
                status_code=409,
            )
        action = f"bilibili.import_cancel:{import_run_id}"
        return run_scoped_idempotent(
            self.bilibili,
            action=action,
            key=idempotency_key,
            factory=lambda: self._cancel_import_run(run),
        )

    def create_qr_session(self) -> dict[str, object]:
        payload = self.bili_client.create_qr_session()
        session_id = str(payload.get("sessionId") or payload.get("qrKey"))
        created = _call_with_supported_kwargs(
            self.bilibili.create_bilibili_qr_session,
            qr_key=session_id,
            qr_url=str(payload.get("qrCodeUrl") or payload.get("qrUrl") or ""),
            status=str(payload.get("status") or "pending_scan"),
            poll_payload_json=payload.get("pollPayload") if isinstance(payload.get("pollPayload"), dict) else None,
            expires_at=payload.get("expiresAt"),
        )
        return self._qr_response(created)

    def get_qr_session(self, *, session_id: str) -> dict[str, object]:
        existing = self.bilibili.get_bilibili_qr_session(session_id)
        if existing is None:
            raise ServiceError(
                message="Bilibili QR session was not found.",
                error_code="bilibili.auth_required",
                status_code=401,
            )
        refresh = getattr(self.bili_client, "refresh_qr_session", None)
        if callable(refresh):
            refreshed = refresh(session_id, existing.get("pollPayloadJson"))
            refreshed_status = str(refreshed.get("status") or existing.get("status") or "pending_scan")
            self._persist_confirmed_auth_session(refreshed)
            existing = _call_with_supported_kwargs(
                self.bilibili.update_bilibili_qr_session,
                qr_key=session_id,
                status=refreshed_status,
                poll_payload_json=(
                    refreshed.get("pollPayload")
                    if isinstance(refreshed.get("pollPayload"), dict)
                    else existing.get("pollPayloadJson")
                ),
                expires_at=refreshed.get("expiresAt") or existing.get("expiresAt"),
            )
        return self._qr_response(existing)

    def get_auth_session(self) -> dict[str, object]:
        auth = self._require_auth_session()
        return {
            "loginStatus": "active",
            "userNickname": auth.get("userNickname") or auth.get("user_nickname"),
            "expiresAt": auth.get("expiresAt") or auth.get("expires_at"),
        }

    def delete_auth_session(self) -> dict[str, object]:
        self.bilibili.delete_bilibili_auth_session()
        return {"deleted": True}

    def _create_import_run_task(
        self,
        *,
        course_id: int,
        source_url: str,
        preview: dict[str, Any],
        selection_mode: str,
        selected_part_ids: list[str],
        quality_preference: str,
        request_fingerprint: str,
    ) -> dict[str, object]:
        selection = {
            "selectionMode": selection_mode,
            "selectedPartIds": list(selected_part_ids),
            "qualityPreference": quality_preference,
            "previewId": preview["previewId"],
            "requestFingerprint": request_fingerprint,
        }
        run = _call_with_supported_kwargs(
            self.bilibili.create_bilibili_import_run,
            course_id=course_id,
            source_url=source_url,
            source_type=preview["sourceType"],
            preview=preview,
            selection=selection,
        )
        import_run_id = int(run["importRunId"])
        payload = {
            "courseId": course_id,
            "importRunId": import_run_id,
            "sourceUrl": source_url,
            "qualityPreference": quality_preference,
        }
        task = _call_with_supported_kwargs(
            self.async_tasks.create_async_task,
            course_id=course_id,
            task_type="bilibili_import",
            status="queued",
            progress_pct=0,
            payload_json=payload,
            target_type="bilibili_import_run",
            target_id=import_run_id,
        )
        task_id = int(task["taskId"])
        _call_with_supported_kwargs(
            self.bilibili.update_bilibili_import_run,
            import_run_id=import_run_id,
            task_id=task_id,
        )
        enqueue = getattr(self.task_dispatcher, "enqueue_bilibili_import", None)
        if callable(enqueue):
            enqueue_or_fail_if_missing_dispatcher(
                self.async_tasks,
                task_id=task_id,
                dispatcher=self.task_dispatcher,
                enqueue=lambda: enqueue(task_id=task_id, payload=payload),
            )
        return {
            "taskId": task_id,
            "status": "queued",
            "nextAction": "poll",
            "entity": {"type": "bilibili_import_run", "id": import_run_id},
        }

    def _cancel_import_run(self, run: dict[str, Any]) -> dict[str, object]:
        import_run_id = int(run["importRunId"])
        updated = _call_with_supported_kwargs(
            self.bilibili.update_bilibili_import_run,
            import_run_id=import_run_id,
            status="canceled",
            stage="canceled",
            progress_pct=run.get("progressPct") or 0,
        )
        task_id = updated.get("taskId") if isinstance(updated, dict) else run.get("taskId")
        if task_id is not None:
            _call_with_supported_kwargs(
                self.async_tasks.update_async_task,
                task_id=int(task_id),
                status="canceled",
            )
        return self._run_response(updated or run)

    def _ensure_course(self, course_id: int) -> dict[str, Any]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _require_auth_session(self) -> dict[str, Any]:
        auth = self.bilibili.get_bilibili_auth_session()
        if auth is None:
            raise ServiceError(
                message="Bilibili auth session is required.",
                error_code="bilibili.auth_required",
                status_code=401,
            )
        if not self._auth_is_active(auth) or self._is_expired(auth.get("expiresAt") or auth.get("expires_at")):
            raise ServiceError(
                message="Bilibili auth session is expired.",
                error_code="bilibili.auth_expired",
                status_code=401,
            )
        return auth

    def _get_preview_entry(
        self,
        *,
        course_id: int,
        preview_id: str | None,
        source_url: str | None,
    ) -> dict[str, Any]:
        if not preview_id or not source_url:
            self._raise_preview_not_found()
        preview_entry = self.bilibili.get_bilibili_preview_snapshot(preview_id)
        if (
            preview_entry is None
            or preview_entry.get("courseId") != course_id
            or preview_entry.get("sourceUrl") != source_url
            or self._is_expired(preview_entry.get("expiresAt") or preview_entry.get("expires_at"))
        ):
            self._raise_preview_not_found()
        return preview_entry

    def _get_import_run(self, import_run_id: int) -> dict[str, Any]:
        run = self.bilibili.get_bilibili_import_run(import_run_id)
        if run is None:
            raise ServiceError(
                message="Bilibili import run was not found.",
                error_code="bilibili.run_not_found",
                status_code=404,
            )
        return run

    def _get_idempotency_result(self, *, action: str, key: str | None) -> Any | None:
        if not key:
            return None
        read = getattr(self.bilibili, "get_idempotency_result", None)
        if not callable(read):
            return None
        return read(action, key)

    def _idempotent_result_matches_request(
        self,
        result: Any,
        *,
        course_id: int,
        request_fingerprint: str,
        source_url: str | None,
        preview_id: str | None,
        selection_mode: str | None,
        selected_part_ids: list[str],
        quality_preference: str | None,
    ) -> bool:
        if not isinstance(result, dict):
            return False
        entity = result.get("entity")
        if not isinstance(entity, dict) or entity.get("type") != "bilibili_import_run":
            return False
        import_run_id = entity.get("id")
        if import_run_id is None:
            return False
        run = self.bilibili.get_bilibili_import_run(int(import_run_id))
        if not isinstance(run, dict):
            return False
        selection = run.get("selection")
        if not isinstance(selection, dict):
            return False
        if isinstance(selection.get("requestFingerprint"), str):
            return run.get("courseId") == course_id and selection["requestFingerprint"] == request_fingerprint
        requested_selection_mode = selection_mode or str(selection.get("selectionMode") or "current_part")
        requested_quality_preference = quality_preference or str(selection.get("qualityPreference") or "android_safe")
        return (
            run.get("courseId") == course_id
            and run.get("sourceUrl") == source_url
            and selection.get("previewId") == preview_id
            and selection.get("selectionMode") == requested_selection_mode
            and list(selection.get("selectedPartIds") or []) == list(selected_part_ids)
            and selection.get("qualityPreference") == requested_quality_preference
        )

    @staticmethod
    def _request_fingerprint(
        *,
        preview_id: str | None,
        source_url: str | None,
        selection_mode: str | None,
        selected_part_ids: list[str],
        quality_preference: str | None,
    ) -> str:
        payload = {
            "previewId": preview_id,
            "sourceUrl": source_url,
            "selectionMode": selection_mode,
            "selectedPartIds": list(selected_part_ids),
            "qualityPreference": quality_preference,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _raise_preview_not_found() -> None:
        raise ServiceError(
            message="Bilibili preview snapshot was not found.",
            error_code="bilibili.preview_not_found",
            status_code=404,
        )

    @staticmethod
    def _validate_selection(
        *,
        preview: dict[str, Any],
        selection_mode: str | None,
        selected_part_ids: list[str],
    ) -> None:
        if selection_mode != "selected_parts":
            return
        valid_part_ids = {str(part["partId"]) for part in preview.get("parts", [])}
        if not selected_part_ids or any(part_id not in valid_part_ids for part_id in selected_part_ids):
            raise ServiceError(
                message="Selected Bilibili parts are invalid.",
                error_code="bilibili.selection_invalid",
                status_code=422,
            )

    @staticmethod
    def _normalize_preview(raw_preview: Any) -> dict[str, Any]:
        if hasattr(raw_preview, "to_api"):
            raw_preview = raw_preview.to_api()
        preview = dict(raw_preview)
        preview["parts"] = [
            part.to_api() if hasattr(part, "to_api") else dict(part)
            for part in preview.get("parts", [])
        ]
        return preview

    @staticmethod
    def _run_response(run: dict[str, Any]) -> dict[str, object]:
        response = {
            "importRunId": run["importRunId"],
            "courseId": run["courseId"],
            "sourceUrl": run["sourceUrl"],
            "sourceType": run["sourceType"],
            "status": run["status"],
            "progressPct": run["progressPct"],
            "stage": run["stage"],
            "taskId": run.get("taskId"),
            "resourceIds": run.get("resourceIds") or [],
            "preview": run.get("preview"),
            "nextAction": _next_action(str(run["status"])),
            "errorCode": run.get("errorCode"),
            "failureReason": run.get("failureReason"),
            "recoverable": bool(run.get("recoverable")),
        }
        return response

    @staticmethod
    def _qr_response(session: dict[str, Any]) -> dict[str, object]:
        return {
            "sessionId": session["qrKey"],
            "status": session["status"],
            "qrCodeUrl": session.get("qrUrl"),
            "expiresAt": session.get("expiresAt"),
        }

    @staticmethod
    def _cookies_from_auth(auth: dict[str, Any]) -> dict[str, Any]:
        cookies = auth.get("cookiesJson") or auth.get("cookies_json") or {}
        return dict(cookies) if isinstance(cookies, dict) else {}

    def _persist_confirmed_auth_session(self, refreshed: dict[str, Any]) -> None:
        if str(refreshed.get("status") or "") != "confirmed":
            return
        cookies = refreshed.get("cookies")
        if not isinstance(cookies, dict) or not cookies:
            return
        normalized_cookies = {str(key): str(value) for key, value in cookies.items()}
        _call_with_supported_kwargs(
            self.bilibili.save_bilibili_auth_session,
            cookies_json=normalized_cookies,
            csrf=normalized_cookies.get("bili_jct"),
            expires_at=refreshed.get("authExpiresAt") or datetime.now(timezone.utc) + timedelta(days=30),
            status="active",
        )

    @staticmethod
    def _auth_is_active(auth: dict[str, Any]) -> bool:
        return str(auth.get("status") or "") == "active"

    @staticmethod
    def _is_expired(expires_at: object) -> bool:
        if not isinstance(expires_at, datetime):
            return False
        value = expires_at
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc)


def _next_action(status: str) -> str:
    if status in TERMINAL_NONE_STATUSES:
        return "none"
    if status in RETRY_STATUSES:
        return "retry"
    return "poll"
