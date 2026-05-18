from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from server.domain.services import BilibiliService
from server.domain.services.errors import ServiceError
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.tasks.repositories import InMemoryAsyncTaskRepository


class FakeBiliClient:
    def __init__(self) -> None:
        self.preview_calls: list[dict[str, Any]] = []

    def create_qr_session(self) -> dict[str, Any]:
        return {
            "sessionId": "qr-demo-1",
            "qrCodeUrl": "https://passport.bilibili.com/qrcode/demo",
            "status": "pending_scan",
            "expiresAt": datetime(2026, 5, 19, 12, 5, tzinfo=timezone.utc),
            "pollPayload": {"qrcode_key": "qr-demo-1"},
        }

    def refresh_qr_session(self, session_id: str, poll_payload: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "sessionId": session_id,
            "qrCodeUrl": "https://passport.bilibili.com/qrcode/demo",
            "status": "pending_scan",
            "expiresAt": datetime(2026, 5, 19, 12, 5, tzinfo=timezone.utc),
            "pollPayload": poll_payload or {"qrcode_key": session_id},
        }

    def preview(self, source_url: str, cookies: dict[str, Any]) -> dict[str, Any]:
        self.preview_calls.append({"sourceUrl": source_url, "cookies": dict(cookies)})
        return {
            "previewId": "bili_preview_demo",
            "sourceUrl": source_url,
            "sourceType": "multi_p",
            "title": "线性代数公开课",
            "coverUrl": "https://i0.hdslb.com/demo.jpg",
            "totalParts": 2,
            "defaultSelectionMode": "all_parts",
            "parts": [
                {
                    "partId": "p1",
                    "title": "第一讲",
                    "durationSec": 600,
                    "cid": 101,
                    "pageNo": 1,
                    "selectedByDefault": True,
                },
                {
                    "partId": "p2",
                    "title": "第二讲",
                    "durationSec": 720,
                    "cid": 102,
                    "pageNo": 2,
                    "selectedByDefault": True,
                },
            ],
        }


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[dict[str, Any]] = []

    def enqueue_bilibili_import(self, *, task_id: int, payload: dict[str, Any]) -> None:
        self.enqueued.append({"taskId": task_id, "payload": dict(payload)})


def build_service() -> tuple[BilibiliService, MemoryScaffoldRepository, InMemoryAsyncTaskRepository, RecordingDispatcher, FakeBiliClient]:
    store = RuntimeStore()
    repo = MemoryScaffoldRepository(store)
    async_tasks = InMemoryAsyncTaskRepository(task_id_factory=lambda: store.next_id("task"))
    dispatcher = RecordingDispatcher()
    client = FakeBiliClient()
    service = BilibiliService(
        courses=repo,
        bilibili=repo,
        async_tasks=async_tasks,
        task_dispatcher=dispatcher,
        bili_client=client,
    )
    return service, repo, async_tasks, dispatcher, client


def create_course(repo: MemoryScaffoldRepository) -> int:
    return repo.create_course(
        title="B站导入课",
        entry_type="manual_import",
        goal_text="导入 B站视频",
        preferred_style="balanced",
    )["courseId"]


def save_auth(repo: MemoryScaffoldRepository) -> None:
    repo.save_bilibili_auth_session(
        cookies_json={"SESSDATA": "secret-cookie", "bili_jct": "secret-csrf"},
        csrf="secret-csrf",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        status="valid",
    )


def test_auth_session_response_hides_cookie_values() -> None:
    service, repo, *_ = build_service()
    save_auth(repo)

    response = service.get_auth_session()

    assert response == {
        "loginStatus": "valid",
        "userNickname": None,
        "expiresAt": repo.get_bilibili_auth_session()["expiresAt"],
    }
    assert "secret-cookie" not in repr(response)
    assert "cookiesJson" not in response


def test_preview_requires_course_and_auth_then_returns_parts() -> None:
    service, repo, _, _, client = build_service()
    course_id = create_course(repo)

    with pytest.raises(ServiceError) as missing_auth:
        service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    assert missing_auth.value.error_code == "bilibili.auth_required"
    assert missing_auth.value.status_code == 401

    save_auth(repo)
    with pytest.raises(ServiceError) as missing_course:
        service.preview_import(course_id=99999, source_url="https://www.bilibili.com/video/BVdemo/")
    assert missing_course.value.error_code == "course.not_found"
    assert missing_course.value.status_code == 404

    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")

    assert preview["previewId"] == "bili_preview_demo"
    assert preview["sourceType"] == "multi_p"
    assert [part["partId"] for part in preview["parts"]] == ["p1", "p2"]
    assert client.preview_calls[0]["cookies"]["SESSDATA"] == "secret-cookie"


def test_create_import_requires_preview_snapshot_creates_run_task_and_dispatch_payload() -> None:
    service, repo, async_tasks, dispatcher, _ = build_service()
    course_id = create_course(repo)
    save_auth(repo)

    with pytest.raises(ServiceError) as missing_preview:
        service.create_import(
            course_id=course_id,
            preview_id="missing",
            source_url="https://www.bilibili.com/video/BVdemo/",
            selection_mode="all_parts",
            selected_part_ids=[],
            quality_preference="android_safe",
            idempotency_key="bili-create-1",
        )
    assert missing_preview.value.error_code == "bilibili.preview_not_found"
    assert missing_preview.value.status_code == 404

    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    response = service.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode="selected_parts",
        selected_part_ids=["p1"],
        quality_preference="android_safe",
        idempotency_key="bili-create-2",
    )

    assert response["status"] == "queued"
    assert response["nextAction"] == "poll"
    assert response["entity"] == {"type": "bilibili_import_run", "id": response["entity"]["id"]}
    run = repo.get_bilibili_import_run(response["entity"]["id"])
    assert run["taskId"] == response["taskId"]
    assert run["preview"]["previewId"] == preview["previewId"]
    assert run["selection"] == {
        "selectionMode": "selected_parts",
        "selectedPartIds": ["p1"],
        "qualityPreference": "android_safe",
        "previewId": preview["previewId"],
    }
    task = async_tasks.get_async_task(response["taskId"])
    assert task["taskType"] == "bilibili_import"
    assert task["targetType"] == "bilibili_import_run"
    assert task["targetId"] == run["importRunId"]
    assert task["payloadJson"] == {
        "courseId": course_id,
        "importRunId": run["importRunId"],
        "sourceUrl": preview["sourceUrl"],
        "qualityPreference": "android_safe",
    }
    assert dispatcher.enqueued == [{"taskId": response["taskId"], "payload": task["payloadJson"]}]


def test_create_import_rejects_invalid_selected_part_ids() -> None:
    service, repo, *_ = build_service()
    course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")

    with pytest.raises(ServiceError) as exc:
        service.create_import(
            course_id=course_id,
            preview_id=preview["previewId"],
            source_url=preview["sourceUrl"],
            selection_mode="selected_parts",
            selected_part_ids=["p3"],
            quality_preference="android_safe",
            idempotency_key="bili-create-invalid-selection",
        )

    assert exc.value.error_code == "bilibili.selection_invalid"
    assert exc.value.status_code == 422


def test_status_and_list_return_next_action_and_current_run_fields() -> None:
    service, repo, *_ = build_service()
    course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    created = service.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode="all_parts",
        selected_part_ids=[],
        quality_preference="android_safe",
        idempotency_key="bili-create-status",
    )

    status = service.get_import_status(import_run_id=created["entity"]["id"])
    items = service.list_imports(course_id=course_id)["items"]

    assert status["importRunId"] == created["entity"]["id"]
    assert status["status"] == "pending"
    assert status["stage"] == "queued"
    assert status["nextAction"] == "poll"
    assert items[0]["importRunId"] == created["entity"]["id"]
    assert items[0]["nextAction"] == "poll"


def test_cancel_marks_run_and_task_canceled_but_imported_run_fails() -> None:
    service, repo, async_tasks, *_ = build_service()
    course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    created = service.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode="all_parts",
        selected_part_ids=[],
        quality_preference="android_safe",
        idempotency_key="bili-create-cancel",
    )

    canceled = service.cancel_import(import_run_id=created["entity"]["id"], idempotency_key="cancel-1")

    assert canceled["status"] == "canceled"
    assert canceled["stage"] == "canceled"
    assert canceled["nextAction"] == "none"
    assert async_tasks.get_async_task(created["taskId"])["status"] == "canceled"

    imported = repo.create_bilibili_import_run(
        course_id=course_id,
        source_url="https://www.bilibili.com/video/BVimported/",
        source_type="single_video",
        preview=preview,
        selection={"selectionMode": "all_parts"},
    )
    repo.update_bilibili_import_run(imported["importRunId"], status="imported", stage="done")
    with pytest.raises(ServiceError) as exc:
        service.cancel_import(import_run_id=imported["importRunId"], idempotency_key="cancel-imported")
    assert exc.value.error_code == "bilibili.cancel_failed"
    assert exc.value.status_code == 409


def test_qr_session_create_and_get_persists_pending_scan() -> None:
    service, repo, *_ = build_service()

    created = service.create_qr_session()
    fetched = service.get_qr_session(session_id=created["sessionId"])

    assert created["sessionId"] == "qr-demo-1"
    assert created["status"] == "pending_scan"
    assert created["qrCodeUrl"] == "https://passport.bilibili.com/qrcode/demo"
    assert fetched["sessionId"] == created["sessionId"]
    assert fetched["status"] == "pending_scan"
    assert repo.get_bilibili_qr_session("qr-demo-1")["status"] == "pending_scan"
