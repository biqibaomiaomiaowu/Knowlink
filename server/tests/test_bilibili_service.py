from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from server.domain.services import BilibiliService
from server.domain.services.errors import ServiceError
from server.infra.bilibili import (
    BiliClient,
    BiliDownloader,
    DownloadCanceled,
    FfmpegMergeError,
    FfmpegMerger,
    MergeCanceled,
)
from server.infra.bilibili.client import COLLECTION_API_URL, VIEW_API_URL
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
        status="active",
    )


def test_auth_session_response_hides_cookie_values() -> None:
    service, repo, *_ = build_service()
    save_auth(repo)

    response = service.get_auth_session()

    assert response == {
        "loginStatus": "active",
        "userNickname": None,
        "expiresAt": repo.get_bilibili_auth_session()["expiresAt"],
    }
    assert "secret-cookie" not in repr(response)
    assert "cookiesJson" not in response


def test_auth_session_contract_distinguishes_missing_and_expired_sessions() -> None:
    service, repo, *_ = build_service()

    with pytest.raises(ServiceError) as missing:
        service.get_auth_session()
    assert missing.value.error_code == "bilibili.auth_required"
    assert missing.value.status_code == 401

    repo.save_bilibili_auth_session(
        cookies_json={"SESSDATA": "expired-cookie"},
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        status="active",
    )
    with pytest.raises(ServiceError) as expired:
        service.get_auth_session()
    assert expired.value.error_code == "bilibili.auth_expired"
    assert expired.value.status_code == 401

    repo.save_bilibili_auth_session(
        cookies_json={"SESSDATA": "inactive-cookie"},
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        status="expired",
    )
    with pytest.raises(ServiceError) as inactive:
        service.preview_import(course_id=create_course(repo), source_url="https://www.bilibili.com/video/BVdemo/")
    assert inactive.value.error_code == "bilibili.auth_expired"
    assert inactive.value.status_code == 401


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
    assert {
        key: run["selection"][key]
        for key in ("selectionMode", "selectedPartIds", "qualityPreference", "previewId")
    } == {
        "selectionMode": "selected_parts",
        "selectedPartIds": ["p1"],
        "qualityPreference": "android_safe",
        "previewId": preview["previewId"],
    }
    assert isinstance(run["selection"]["requestFingerprint"], str)
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


def test_create_import_uses_persisted_preview_snapshot_across_service_instances() -> None:
    service, repo, async_tasks, dispatcher, client = build_service()
    course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    restarted = BilibiliService(
        courses=repo,
        bilibili=repo,
        async_tasks=async_tasks,
        task_dispatcher=dispatcher,
        bili_client=client,
    )

    response = restarted.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode="all_parts",
        selected_part_ids=[],
        quality_preference="android_safe",
        idempotency_key="bili-create-persisted-preview",
    )

    run = repo.get_bilibili_import_run(response["entity"]["id"])
    assert run["preview"]["previewId"] == preview["previewId"]


def test_create_import_same_idempotency_key_rejects_different_request_body() -> None:
    service, repo, *_ = build_service()
    course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    service.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode="selected_parts",
        selected_part_ids=["p1"],
        quality_preference="android_safe",
        idempotency_key="bili-create-mismatch",
    )

    with pytest.raises(ServiceError) as exc:
        service.create_import(
            course_id=course_id,
            preview_id=preview["previewId"],
            source_url=preview["sourceUrl"],
            selection_mode="selected_parts",
            selected_part_ids=["p2"],
            quality_preference="android_safe",
            idempotency_key="bili-create-mismatch",
        )

    assert exc.value.error_code == "idempotency.body_mismatch"
    assert exc.value.status_code == 409

    with pytest.raises(ServiceError) as changed_url:
        service.create_import(
            course_id=course_id,
            preview_id=preview["previewId"],
            source_url=f"{preview['sourceUrl']}?changed=1",
            selection_mode="selected_parts",
            selected_part_ids=["p1"],
            quality_preference="android_safe",
            idempotency_key="bili-create-mismatch",
        )
    assert changed_url.value.error_code == "idempotency.body_mismatch"
    assert changed_url.value.status_code == 409

    with pytest.raises(ServiceError) as changed_preview:
        service.create_import(
            course_id=course_id,
            preview_id="bili_preview_other",
            source_url=preview["sourceUrl"],
            selection_mode="selected_parts",
            selected_part_ids=["p1"],
            quality_preference="android_safe",
            idempotency_key="bili-create-mismatch",
        )
    assert changed_preview.value.error_code == "idempotency.body_mismatch"
    assert changed_preview.value.status_code == 409
    assert len(repo.list_bilibili_import_runs(course_id)) == 1


def test_create_import_idempotency_compares_original_request_fingerprint() -> None:
    service, repo, *_ = build_service()
    course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")
    first = service.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode=None,
        selected_part_ids=[],
        quality_preference=None,
        idempotency_key="bili-create-fingerprint",
    )

    replay = service.create_import(
        course_id=course_id,
        preview_id=preview["previewId"],
        source_url=preview["sourceUrl"],
        selection_mode=None,
        selected_part_ids=[],
        quality_preference=None,
        idempotency_key="bili-create-fingerprint",
    )
    with pytest.raises(ServiceError) as explicit_default:
        service.create_import(
            course_id=course_id,
            preview_id=preview["previewId"],
            source_url=preview["sourceUrl"],
            selection_mode="all_parts",
            selected_part_ids=[],
            quality_preference="android_safe",
            idempotency_key="bili-create-fingerprint",
        )

    run = repo.get_bilibili_import_run(first["entity"]["id"])
    assert replay == first
    assert run["selection"]["selectionMode"] == "all_parts"
    assert run["selection"]["qualityPreference"] == "android_safe"
    assert isinstance(run["selection"]["requestFingerprint"], str)
    assert explicit_default.value.error_code == "idempotency.body_mismatch"
    assert explicit_default.value.status_code == 409


def test_create_import_rejects_preview_snapshot_course_source_and_expiry_mismatch() -> None:
    service, repo, *_ = build_service()
    course_id = create_course(repo)
    other_course_id = create_course(repo)
    save_auth(repo)
    preview = service.preview_import(course_id=course_id, source_url="https://www.bilibili.com/video/BVdemo/")

    with pytest.raises(ServiceError) as wrong_course:
        service.create_import(
            course_id=other_course_id,
            preview_id=preview["previewId"],
            source_url=preview["sourceUrl"],
            selection_mode="all_parts",
            selected_part_ids=[],
            quality_preference="android_safe",
            idempotency_key="bili-create-wrong-course",
        )
    assert wrong_course.value.error_code == "bilibili.preview_not_found"
    assert wrong_course.value.status_code == 404

    with pytest.raises(ServiceError) as wrong_source:
        service.create_import(
            course_id=course_id,
            preview_id=preview["previewId"],
            source_url=f"{preview['sourceUrl']}?wrong=1",
            selection_mode="all_parts",
            selected_part_ids=[],
            quality_preference="android_safe",
            idempotency_key="bili-create-wrong-source",
        )
    assert wrong_source.value.error_code == "bilibili.preview_not_found"
    assert wrong_source.value.status_code == 404

    snapshot = repo.get_bilibili_preview_snapshot(preview["previewId"])
    assert snapshot is not None
    snapshot["expiresAt"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(ServiceError) as expired:
        service.create_import(
            course_id=course_id,
            preview_id=preview["previewId"],
            source_url=preview["sourceUrl"],
            selection_mode="all_parts",
            selected_part_ids=[],
            quality_preference="android_safe",
            idempotency_key="bili-create-expired-preview",
        )
    assert expired.value.error_code == "bilibili.preview_not_found"
    assert expired.value.status_code == 404


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


def test_missing_import_run_uses_v2_contract_error_code() -> None:
    service, *_ = build_service()

    with pytest.raises(ServiceError) as exc:
        service.get_import_status(import_run_id=99999)

    assert exc.value.error_code == "bilibili.run_not_found"
    assert exc.value.status_code == 404


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


def test_qr_session_confirmation_persists_auth_session() -> None:
    class ConfirmingBiliClient(FakeBiliClient):
        def refresh_qr_session(self, session_id: str, poll_payload: dict[str, Any] | None) -> dict[str, Any]:
            return {
                "sessionId": session_id,
                "qrCodeUrl": "https://passport.bilibili.com/qrcode/demo",
                "status": "confirmed",
                "expiresAt": datetime(2026, 5, 19, 12, 5, tzinfo=timezone.utc),
                "pollPayload": poll_payload or {"qrcode_key": session_id},
                "cookies": {
                    "SESSDATA": "confirmed-cookie",
                    "bili_jct": "confirmed-csrf",
                    "DedeUserID": "12345",
                },
            }

    service, repo, *_ = build_service()
    service.bili_client = ConfirmingBiliClient()

    created = service.create_qr_session()
    fetched = service.get_qr_session(session_id=created["sessionId"])

    auth = repo.get_bilibili_auth_session()
    assert fetched["status"] == "confirmed"
    assert auth is not None
    assert auth["status"] == "active"
    assert auth["cookiesJson"]["SESSDATA"] == "confirmed-cookie"
    assert auth["csrf"] == "confirmed-csrf"
    assert service.get_auth_session()["loginStatus"] == "active"


def test_api_bilibili_dependency_wires_real_client_by_default() -> None:
    from server.api.deps import get_bilibili_service

    _, repo, async_tasks, dispatcher, _ = build_service()

    wired = asyncio.run(
        get_bilibili_service(
            repo=repo,
            async_tasks=async_tasks,
            task_dispatcher=dispatcher,
        )
    )

    assert isinstance(wired.bili_client, BiliClient)


def test_bili_client_preview_normalizes_video_metadata() -> None:
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def get_json(
            self,
            url: str,
            *,
            params: dict[str, Any] | None = None,
            cookies: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            return {
                "code": 0,
                "data": {
                    "bvid": "BV1xx411c7mD",
                    "title": "线性代数公开课",
                    "pic": "https://i0.hdslb.com/demo.jpg",
                    "pages": [
                        {"cid": 101, "page": 1, "part": "第一讲", "duration": 600},
                        {"cid": 102, "page": 2, "part": "第二讲", "duration": 720},
                    ],
                },
            }

    transport = FakeTransport()
    client = BiliClient(transport=transport, preview_id_factory=lambda: "bili_preview_fixed")

    preview = client.preview("https://www.bilibili.com/video/BV1xx411c7mD/?p=2", cookies={"SESSDATA": "secret"})

    assert transport.calls == [
        {
            "url": "https://api.bilibili.com/x/web-interface/view",
            "params": {"bvid": "BV1xx411c7mD"},
            "cookies": {"SESSDATA": "secret"},
        }
    ]
    assert preview.to_api() == {
        "previewId": "bili_preview_fixed",
        "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD/?p=2",
        "sourceType": "multi_p",
        "title": "线性代数公开课",
        "coverUrl": "https://i0.hdslb.com/demo.jpg",
        "totalParts": 2,
        "defaultSelectionMode": "current_part",
        "parts": [
            {
                "partId": "p1",
                "title": "第一讲",
                "durationSec": 600,
                "cid": 101,
                "pageNo": 1,
                "selectedByDefault": False,
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


def test_bili_client_preview_maps_malformed_url_to_unsupported_url():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            raise AssertionError(url)

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "unused")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("not a bilibili url", cookies={})

    assert exc_info.value.error_code == "bilibili.unsupported_url"
    assert exc_info.value.status_code == 422


def test_bili_client_preview_video_rejects_non_numeric_cid_as_metadata_failed():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            assert url == VIEW_API_URL
            return {
                "code": 0,
                "data": {
                    "bvid": "BV1xx411c7mD",
                    "title": "坏数据视频",
                    "pages": [{"cid": "bad", "page": 1, "part": "坏数据", "duration": 600}],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_fixed")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://www.bilibili.com/video/BV1xx411c7mD/", cookies={})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_video_rejects_non_numeric_duration_as_metadata_failed():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            assert url == VIEW_API_URL
            return {
                "code": 0,
                "data": {
                    "bvid": "BV1xx411c7mD",
                    "title": "坏数据视频",
                    "pages": [{"cid": 101, "page": 1, "part": "坏数据", "duration": ""}],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_fixed")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://www.bilibili.com/video/BV1xx411c7mD/", cookies={})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_collection_expands_archives_to_parts():
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def get_json(self, url: str, *, params=None, cookies=None):
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "线代合集", "cover": "https://i0.hdslb.com/cover.jpg"},
                    "archives": [
                        {
                            "bvid": "BV1xx411c7mD",
                            "cid": 101,
                            "title": "P1 行列式",
                            "duration": 600,
                            "pic": "https://i0.hdslb.com/p1.jpg",
                        },
                        {"bvid": "BV1yy411c7mD", "cid": 102, "title": "P2 矩阵", "duration": 720},
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_collection")
    preview = client.preview(
        "https://space.bilibili.com/123/channel/collectiondetail?sid=456",
        cookies={"SESSDATA": "secret"},
    )

    data = preview.to_api()
    assert data["sourceType"] == "collection"
    assert data["title"] == "线代合集"
    assert data["defaultSelectionMode"] == "all_parts"
    assert data["totalParts"] == 2
    assert data["parts"][0]["partId"] == "collection-456-bv-BV1xx411c7mD-cid-101-p1"


def test_bili_client_preview_collection_fetches_all_archive_pages():
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def get_json(self, url: str, *, params=None, cookies=None):
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            assert url == COLLECTION_API_URL
            page_num = params["page_num"]
            if page_num == 1:
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "分页合集"},
                        "page": {"total": 2, "page_size": 1, "page_num": 1},
                        "archives": [
                            {
                                "bvid": "BV1xx411c7mD",
                                "cid": 101,
                                "title": "P1",
                                "duration": 600,
                            }
                        ],
                    },
                }
            if page_num == 2:
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "分页合集"},
                        "page": {"total": 2, "page_size": 1, "page_num": 2},
                        "archives": [
                            {
                                "bvid": "BV1yy411c7mD",
                                "cid": 102,
                                "title": "P2",
                                "duration": 720,
                            }
                        ],
                    },
                }
            raise AssertionError(page_num)

    transport = FakeTransport()
    client = BiliClient(transport=transport, preview_id_factory=lambda: "bili_preview_collection")

    preview = client.preview(
        "https://space.bilibili.com/123/channel/collectiondetail?sid=456",
        cookies={"SESSDATA": "secret"},
    )

    data = preview.to_api()
    assert data["totalParts"] == 2
    assert [part["partId"] for part in data["parts"]] == [
        "collection-456-bv-BV1xx411c7mD-cid-101-p1",
        "collection-456-bv-BV1yy411c7mD-cid-102-p2",
    ]
    assert [call["params"]["page_num"] for call in transport.calls] == [1, 2]


def test_bili_client_preview_collection_rejects_malformed_page_metadata():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            assert url == COLLECTION_API_URL
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "坏分页合集"},
                    "page": {"total": "bad", "page_size": 1, "page_num": 1},
                    "archives": [
                        {
                            "bvid": "BV1xx411c7mD",
                            "cid": 101,
                            "title": "P1",
                            "duration": 600,
                        }
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_collection")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://space.bilibili.com/123/channel/collectiondetail?sid=456", cookies={})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_collection_rejects_incomplete_page_metadata():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            assert url == COLLECTION_API_URL
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "缺分页字段合集"},
                    "page": {"total": 2},
                    "archives": [
                        {
                            "bvid": "BV1xx411c7mD",
                            "cid": 101,
                            "title": "P1",
                            "duration": 600,
                        }
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_collection")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://space.bilibili.com/123/channel/collectiondetail?sid=456", cookies={})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_collection_rejects_non_dict_page_metadata():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            assert url == COLLECTION_API_URL
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "坏分页合集"},
                    "page": "bad",
                    "archives": [
                        {
                            "bvid": "BV1xx411c7mD",
                            "cid": 101,
                            "title": "P1",
                            "duration": 600,
                        }
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_collection")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://space.bilibili.com/123/channel/collectiondetail?sid=456", cookies={})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_collection_resolves_cid_from_video_view_when_archives_omit_cid():
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def get_json(self, url: str, *, params=None, cookies=None):
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            if url == COLLECTION_API_URL:
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "线代合集"},
                        "archives": [{"bvid": "BV1xx411c7mD", "title": "合集视频", "duration": 600}],
                    },
                }
            if url == VIEW_API_URL:
                assert params == {"bvid": "BV1xx411c7mD"}
                return {
                    "code": 0,
                    "data": {
                        "pages": [{"cid": 101, "page": 1, "part": "P1 行列式", "duration": 600}]
                    },
                }
            raise AssertionError(url)

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_collection")
    preview = client.preview(
        "https://space.bilibili.com/123/channel/collectiondetail?sid=456",
        cookies={"SESSDATA": "secret"},
    )

    data = preview.to_api()
    assert data["totalParts"] == 1
    assert data["parts"][0]["partId"] == "collection-456-bv-BV1xx411c7mD-cid-101-p1"
    assert data["parts"][0]["title"] == "P1 行列式"


def test_bili_client_preview_collection_rejects_non_numeric_cid_as_metadata_failed():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "合集"},
                    "archives": [
                        {"bvid": "BV1xx411c7mD", "cid": "", "title": "坏数据", "duration": 600}
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_collection")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://space.bilibili.com/123/channel/collectiondetail?sid=456", cookies={})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_bangumi_defaults_to_current_episode():
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def get_json(self, url: str, *, params=None, cookies=None):
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            return {
                "code": 0,
                "result": {
                    "title": "番剧课程",
                    "cover": "https://i0.hdslb.com/bangumi.jpg",
                    "episodes": [
                        {
                            "id": 123455,
                            "bvid": "BV1aa411c7mD",
                            "cid": 201,
                            "page": 10,
                            "long_title": "上一讲",
                            "duration": 500000,
                        },
                        {
                            "id": 123456,
                            "bvid": "BV1bb411c7mD",
                            "cid": 202,
                            "page_no": 20,
                            "long_title": "当前讲",
                            "duration": 9500,
                        },
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_bangumi")
    preview = client.preview("https://www.bilibili.com/bangumi/play/ep123456", cookies={"SESSDATA": "secret"})

    data = preview.to_api()
    assert data["sourceType"] == "bangumi"
    assert data["defaultSelectionMode"] == "current_part"
    assert data["totalParts"] == 2
    assert data["parts"][0]["pageNo"] == 1
    assert data["parts"][0]["durationSec"] == 500
    assert data["parts"][0]["partId"] == "bangumi-ep-123455-bv-BV1aa411c7mD-cid-201-p1"
    assert data["parts"][1]["pageNo"] == 2
    assert data["parts"][1]["durationSec"] == 9
    assert data["parts"][1]["selectedByDefault"] is True
    assert data["parts"][1]["partId"] == "bangumi-ep-123456-bv-BV1bb411c7mD-cid-202-p2"


def test_bili_client_preview_bangumi_data_body_keeps_second_durations():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            return {
                "code": 0,
                "data": {
                    "title": "番剧课程",
                    "episodes": [
                        {
                            "id": 123456,
                            "bvid": "BV1bb411c7mD",
                            "cid": 202,
                            "long_title": "当前讲",
                            "duration": 650,
                        }
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_bangumi")

    preview = client.preview("https://www.bilibili.com/bangumi/play/ep123456", cookies={"SESSDATA": "secret"})

    data = preview.to_api()
    assert data["parts"][0]["durationSec"] == 650
    assert data["parts"][0]["partId"] == "bangumi-ep-123456-bv-BV1bb411c7mD-cid-202-p1"


def test_bili_client_preview_bangumi_rejects_non_numeric_cid_as_metadata_failed():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            return {
                "code": 0,
                "data": {
                    "title": "番剧课程",
                    "episodes": [
                        {
                            "id": 123456,
                            "bvid": "BV1bb411c7mD",
                            "cid": "bad",
                            "long_title": "当前讲",
                            "duration": 650,
                        }
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_bangumi")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://www.bilibili.com/bangumi/play/ep123456", cookies={"SESSDATA": "secret"})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_bangumi_rejects_empty_cid_as_metadata_failed():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            return {
                "code": 0,
                "data": {
                    "title": "番剧课程",
                    "episodes": [
                        {
                            "id": 123456,
                            "bvid": "BV1bb411c7mD",
                            "cid": "",
                            "long_title": "当前讲",
                            "duration": 650,
                        }
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_bangumi")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://www.bilibili.com/bangumi/play/ep123456", cookies={"SESSDATA": "secret"})

    assert exc_info.value.error_code == "bilibili.metadata_failed"
    assert exc_info.value.status_code == 502


def test_bili_client_preview_bangumi_rejects_when_current_episode_not_playable():
    class FakeTransport:
        def get_json(self, url: str, *, params=None, cookies=None):
            return {
                "code": 0,
                "data": {
                    "title": "番剧课程",
                    "episodes": [
                        {
                            "id": 123455,
                            "bvid": "BV1aa411c7mD",
                            "cid": 201,
                            "long_title": "上一讲",
                            "duration": 500,
                        },
                        {"id": 123456, "long_title": "当前讲", "duration": 650},
                    ],
                },
            }

    client = BiliClient(transport=FakeTransport(), preview_id_factory=lambda: "bili_preview_bangumi")

    with pytest.raises(ServiceError) as exc_info:
        client.preview("https://www.bilibili.com/bangumi/play/ep123456", cookies={"SESSDATA": "secret"})

    assert exc_info.value.error_code == "bilibili.access_denied"
    assert exc_info.value.status_code == 403


def test_bili_client_playurl_uses_transport_and_maps_failures() -> None:
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            self.response = {
                "code": 0,
                "data": {
                    "dash": {
                        "video": [{"baseUrl": "https://upos.example/video.m4s"}],
                        "audio": [{"baseUrl": "https://upos.example/audio.m4s"}],
                    }
                },
            }

        def get_json(
            self,
            url: str,
            *,
            params: dict[str, Any] | None = None,
            cookies: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            return self.response

    transport = FakeTransport()
    client = BiliClient(transport=transport)

    data = client.playurl(bvid="BV1xx411c7mD", cid=102, cookies={"SESSDATA": "secret"})

    assert transport.calls == [
        {
            "url": "https://api.bilibili.com/x/player/wbi/playurl",
            "params": {"bvid": "BV1xx411c7mD", "cid": 102, "fnval": 16},
            "cookies": {"SESSDATA": "secret"},
        }
    ]
    assert data == {
        "dash": {
            "video": [{"baseUrl": "https://upos.example/video.m4s"}],
            "audio": [{"baseUrl": "https://upos.example/audio.m4s"}],
        }
    }

    transport.response = {"code": -400, "message": "bad request"}
    with pytest.raises(ServiceError) as exc:
        client.playurl(bvid="BV1xx411c7mD", cid=102, cookies={"SESSDATA": "secret"})
    assert exc.value.error_code == "bilibili.playurl_failed"


def test_bili_client_maps_auth_and_access_errors() -> None:
    class FakeTransport:
        def __init__(self, response: dict[str, Any]) -> None:
            self.response = response

        def get_json(
            self,
            url: str,
            *,
            params: dict[str, Any] | None = None,
            cookies: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return self.response

    expired_client = BiliClient(transport=FakeTransport({"code": -101, "message": "账号未登录"}))
    with pytest.raises(ServiceError) as expired:
        expired_client.preview("https://www.bilibili.com/video/BV1xx411c7mD/", cookies={})
    assert expired.value.error_code == "bilibili.auth_expired"
    assert expired.value.status_code == 401

    denied_client = BiliClient(transport=FakeTransport({"code": -10403, "message": "权限不足"}))
    with pytest.raises(ServiceError) as denied:
        denied_client.preview("https://www.bilibili.com/video/BV1xx411c7mD/", cookies={"SESSDATA": "secret"})
    assert denied.value.error_code == "bilibili.access_denied"
    assert denied.value.status_code == 403


def test_bili_client_refresh_qr_session_extracts_transport_cookies() -> None:
    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def get_json(
            self,
            url: str,
            *,
            params: dict[str, Any] | None = None,
            cookies: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            self.calls.append({"url": url, "params": params, "cookies": cookies})
            return {
                "code": 0,
                "data": {"code": 0},
                "headers": {
                    "Set-Cookie": [
                        "SESSDATA=secret-cookie; Path=/; HttpOnly",
                        "bili_jct=csrf-cookie; Path=/",
                        "DedeUserID=12345; Path=/",
                    ],
                },
            }

    transport = FakeTransport()
    client = BiliClient(transport=transport)

    refreshed = client.refresh_qr_session("qr-demo-1", {"qrcode_key": "qr-key-1"})

    assert transport.calls == [
        {
            "url": "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
            "params": {"qrcode_key": "qr-key-1"},
            "cookies": None,
        }
    ]
    assert refreshed["status"] == "confirmed"
    assert refreshed["cookies"] == {
        "SESSDATA": "secret-cookie",
        "bili_jct": "csrf-cookie",
        "DedeUserID": "12345",
    }
    assert "headers" not in refreshed


def test_downloader_writes_stream_and_reports_progress(tmp_path) -> None:
    class FakeStream:
        def __init__(self) -> None:
            self.closed = False

        def iter_bytes(self):
            yield b"abc"
            yield b"de"

        def close(self) -> None:
            self.closed = True

    streams: list[FakeStream] = []

    def stream_factory(url: str, *, cookies: dict[str, Any] | None = None):
        stream = FakeStream()
        streams.append(stream)
        assert url == "https://upos.example/video.m4s"
        assert cookies == {"SESSDATA": "secret"}
        return stream

    progress: list[dict[str, int]] = []
    downloader = BiliDownloader(stream_factory=stream_factory)
    output_path = tmp_path / "video.m4s"

    result = downloader.download(
        "https://upos.example/video.m4s",
        output_path,
        cookies={"SESSDATA": "secret"},
        progress_callback=progress.append,
    )

    assert result == output_path
    assert output_path.read_bytes() == b"abcde"
    assert progress == [{"downloadedBytes": 3}, {"downloadedBytes": 5}]
    assert streams[0].closed is True


def test_downloader_cleans_partial_file_when_canceled(tmp_path) -> None:
    class CancelToken:
        canceled = False

    class FakeStream:
        def __init__(self, token: CancelToken) -> None:
            self.closed = False
            self.token = token

        def iter_bytes(self):
            yield b"abc"
            self.token.canceled = True
            yield b"de"

        def close(self) -> None:
            self.closed = True

    token = CancelToken()
    streams: list[FakeStream] = []

    def stream_factory(url: str, *, cookies: dict[str, Any] | None = None):
        stream = FakeStream(token)
        streams.append(stream)
        return stream

    output_path = tmp_path / "video.m4s"
    downloader = BiliDownloader(stream_factory=stream_factory)

    with pytest.raises(DownloadCanceled):
        downloader.download(
            "https://upos.example/video.m4s",
            output_path,
            cancel_token=token,
        )

    assert streams[0].closed is True
    assert output_path.exists() is False


def test_ffmpeg_merger_builds_stream_copy_command(tmp_path) -> None:
    commands: list[list[str]] = []

    def run_command(command: list[str]) -> int:
        commands.append(command)
        return 0

    video_path = tmp_path / "video.m4s"
    audio_path = tmp_path / "audio.m4s"
    output_path = tmp_path / "merged.mp4"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")
    merger = FfmpegMerger(run_command=run_command)

    result = merger.merge(video_path, audio_path, output_path)

    assert result == output_path
    assert commands == [
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c",
            "copy",
            str(output_path),
        ]
    ]


def test_ffmpeg_merger_cleans_output_on_failure_and_cancel(tmp_path) -> None:
    def failing_command(command: list[str]) -> int:
        output_path.write_bytes(b"partial")
        return 1

    video_path = tmp_path / "video.m4s"
    audio_path = tmp_path / "audio.m4s"
    output_path = tmp_path / "merged.mp4"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")
    merger = FfmpegMerger(run_command=failing_command)

    with pytest.raises(FfmpegMergeError):
        merger.merge(video_path, audio_path, output_path)
    assert output_path.exists() is False

    class CancelToken:
        canceled = True

    output_path.write_bytes(b"stale")
    with pytest.raises(MergeCanceled):
        merger.merge(video_path, audio_path, output_path, cancel_token=CancelToken())
    assert output_path.exists() is False


def test_ffmpeg_merger_terminates_running_process_when_canceled(tmp_path) -> None:
    class CancelToken:
        canceled = False

    class FakeProcess:
        def __init__(self, token: CancelToken) -> None:
            self.token = token
            self.poll_calls = 0
            self.terminated = False
            self.killed = False
            self.returncode = None

        def poll(self):
            self.poll_calls += 1
            if self.poll_calls == 2:
                self.token.canceled = True
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

        def wait(self, timeout: float | None = None):
            return self.returncode

    token = CancelToken()
    processes: list[FakeProcess] = []

    def popen_factory(command: list[str]):
        output_path.write_bytes(b"partial")
        process = FakeProcess(token)
        processes.append(process)
        return process

    video_path = tmp_path / "video.m4s"
    audio_path = tmp_path / "audio.m4s"
    output_path = tmp_path / "merged.mp4"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")
    merger = FfmpegMerger(popen_factory=popen_factory, poll_interval_sec=0)

    with pytest.raises(MergeCanceled):
        merger.merge(video_path, audio_path, output_path, cancel_token=token)

    assert processes[0].terminated is True
    assert processes[0].killed is False
    assert output_path.exists() is False
