from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import importlib

import pytest

from server.domain.services.errors import ServiceError
from server.infra.bilibili.models import BilibiliPart, BilibiliPreview, BilibiliSourceType
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.tasks.dispatcher import DramatiqTaskDispatcher, InMemoryTaskDispatcher, NoopTaskDispatcher


class FakeClient:
    def __init__(self, *, playurl_error: Exception | None = None) -> None:
        self.playurl_error = playurl_error
        self.preview_calls: list[dict[str, Any]] = []
        self.playurl_calls: list[dict[str, Any]] = []

    def preview(self, source_url: str, cookies: dict[str, Any]) -> BilibiliPreview:
        self.preview_calls.append({"sourceUrl": source_url, "cookies": dict(cookies)})
        return BilibiliPreview(
            preview_id="bili_preview_1",
            source_url=source_url,
            source_type=BilibiliSourceType.SINGLE_VIDEO,
            title="Runner demo",
            cover_url=None,
            total_parts=1,
            parts=[
                BilibiliPart(
                    part_id="p1",
                    title="P1",
                    duration_sec=30,
                    cid=1001,
                    page_no=1,
                    selected_by_default=True,
                )
            ],
            default_selection_mode="current_part",
        )

    def playurl(self, *, source_url: str, part: BilibiliPart, cookies: dict[str, Any], quality_preference: str):
        if self.playurl_error is not None:
            raise self.playurl_error
        self.playurl_calls.append(
            {
                "sourceUrl": source_url,
                "part": part,
                "cookies": dict(cookies),
                "qualityPreference": quality_preference,
            }
        )
        return {
            "videoUrl": "https://upos.test/video.m4s",
            "audioUrl": "https://upos.test/audio.m4s",
            "headers": {"Referer": source_url},
        }


class CollectionPreviewClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.playurl_calls: list[dict[str, Any]] = []

    def preview(self, source_url: str, cookies: dict[str, Any]) -> BilibiliPreview:
        return BilibiliPreview(
            preview_id="bili_preview_collection",
            source_url=source_url,
            source_type=BilibiliSourceType.COLLECTION,
            title="合集课",
            cover_url=None,
            total_parts=1,
            parts=[
                BilibiliPart(
                    part_id="collection-456-bv-BV1xx411c7mD-cid-1001-p1",
                    title="合集第一讲",
                    duration_sec=30,
                    cid=1001,
                    page_no=1,
                    selected_by_default=True,
                )
            ],
            default_selection_mode="all_parts",
        )

    def playurl(self, *, bvid: str, cid: int, cookies: dict[str, Any], qn: int | None = None):
        self.playurl_calls.append({"bvid": bvid, "cid": cid, "qn": qn})
        return {
            "dash": {
                "video": [{"baseUrl": "https://upos.test/video.m4s"}],
                "audio": [{"baseUrl": "https://upos.test/audio.m4s"}],
            }
        }


class FakeDownloader:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.downloaded: list[Path] = []

    def download(self, url: str, destination: str | Path, **kwargs: Any) -> Path:
        if self.error is not None:
            raise self.error
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(url.encode("utf-8"))
        self.downloaded.append(path)
        on_progress = kwargs.get("on_progress") or kwargs.get("progress_callback")
        if on_progress:
            on_progress({"downloadedBytes": path.stat().st_size})
        return path


class FakeMerger:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error

    def merge(self, video_path: str | Path, audio_path: str | Path, output_path: str | Path, **kwargs: Any) -> Path:
        if self.error is not None:
            raise self.error
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(Path(video_path).read_bytes() + b"|" + Path(audio_path).read_bytes())
        return output


class CancelAfterMerge(FakeMerger):
    def __init__(self, repo: MemoryScaffoldRepository, import_run_id: int) -> None:
        super().__init__()
        self.repo = repo
        self.import_run_id = import_run_id

    def merge(self, video_path: str | Path, audio_path: str | Path, output_path: str | Path, **kwargs: Any) -> Path:
        output = super().merge(video_path, audio_path, output_path, **kwargs)
        self.repo.update_bilibili_import_run(self.import_run_id, status="canceled", stage="canceled")
        return output


class FakeStorage:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.uploads: list[dict[str, Any]] = []
        self.deletes: list[str] = []

    def upload_file(
        self,
        object_key: str,
        source_path: str | Path,
        *,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        if self.error is not None:
            raise self.error
        self.uploads.append(
            {
                "objectKey": object_key,
                "sourcePath": str(source_path),
                "contentType": content_type,
                "metadata": metadata or {},
            }
        )
        from server.infra.storage import ObjectStat

        return ObjectStat(size_bytes=Path(source_path).stat().st_size, checksum_required=False)

    def delete_object(self, object_key: str) -> None:
        self.deletes.append(object_key)


class CancelAfterUploadStorage(FakeStorage):
    def __init__(self, repo: MemoryScaffoldRepository, import_run_id: int) -> None:
        super().__init__()
        self.repo = repo
        self.import_run_id = import_run_id

    def upload_file(
        self,
        object_key: str,
        source_path: str | Path,
        *,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        stat = super().upload_file(
            object_key,
            source_path,
            content_type=content_type,
            metadata=metadata,
        )
        self.repo.update_bilibili_import_run(self.import_run_id, status="canceled", stage="canceled")
        return stat


def _build_run(
    *,
    source_url: str = "https://www.bilibili.com/video/BV1xx411c7mD",
    source_type: str = "single_video",
    selection: dict[str, Any] | None = None,
) -> tuple[MemoryScaffoldRepository, dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Runner course",
        entry_type="manual_import",
        goal_text="导入 B站",
        preferred_style="balanced",
    )
    run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url=source_url,
        source_type=source_type,
        preview={"title": "Runner demo"},
        selection=selection
        or {"selectionMode": "current_part", "selectedPartIds": ["p1"], "qualityPreference": "android_safe"},
    )
    task = repo.create_async_task(
        course_id=course["courseId"],
        task_type="bilibili_import",
        payload_json={"courseId": course["courseId"], "importRunId": run["importRunId"]},
        target_type="bilibili_import_run",
        target_id=run["importRunId"],
    )
    repo.update_bilibili_import_run(run["importRunId"], task_id=task["taskId"])
    return repo, course, run, task


def _runner(repo: MemoryScaffoldRepository, tmp_path: Path, **overrides: Any) -> BilibiliImportRunner:
    return _runner_class()(
        bilibili=repo,
        resources=repo,
        async_tasks=repo,
        storage=overrides.get("storage") or FakeStorage(),
        bili_client=overrides.get("bili_client") or FakeClient(),
        downloader=overrides.get("downloader") or FakeDownloader(),
        merger=overrides.get("merger") or FakeMerger(),
        runtime_dir=tmp_path,
    )


def _runner_class():
    module = importlib.import_module("server.tasks.bilibili_import")
    assert hasattr(module, "BilibiliImportRunner")
    return module.BilibiliImportRunner


def test_runner_imports_bilibili_video_into_course_resource(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    storage = FakeStorage()
    client = FakeClient()
    runner = _runner(repo, tmp_path, storage=storage, bili_client=client)

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    async_task = repo.get_async_task(task["taskId"])
    resources = repo.list_resources(course["courseId"])
    assert updated is not None
    assert async_task is not None
    assert updated["status"] == "imported"
    assert updated["stage"] == "done"
    assert updated["progressPct"] == 100
    assert updated["resourceIds"] == [resources[0]["resourceId"]]
    assert async_task["status"] == "succeeded"
    assert async_task["progressPct"] == 100
    assert resources[0]["sourceType"] == "bilibili"
    assert resources[0]["originUrl"] == run["sourceUrl"]
    assert resources[0]["resourceType"] == "mp4"
    assert resources[0]["parsePolicyJson"] == {"source": "bilibili", "importRunId": run["importRunId"]}
    assert storage.uploads[0]["objectKey"].startswith(f"raw/1/{course['courseId']}/bilibili/{run['importRunId']}/")
    assert client.preview_calls[0]["cookies"] == {}
    assert client.playurl_calls[0]["cookies"] == {}
    assert not (tmp_path / str(run["importRunId"])).exists()


def test_runner_ignores_expired_auth_session_and_uses_anonymous_cookies(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    repo.save_bilibili_auth_session(
        cookies_json={"SESSDATA": "expired-cookie"},
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        status="active",
    )
    client = FakeClient()
    runner = _runner(repo, tmp_path, bili_client=client)

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    assert repo.get_bilibili_import_run(run["importRunId"])["status"] == "imported"
    assert client.preview_calls[0]["cookies"] == {}
    assert client.playurl_calls[0]["cookies"] == {}


def test_runner_uses_bvid_encoded_in_collection_part_id_for_playurl(tmp_path: Path) -> None:
    repo, course, run, task = _build_run(
        source_url="https://space.bilibili.com/123/channel/collectiondetail?sid=456",
        source_type="collection",
        selection={"selectionMode": "all_parts", "selectedPartIds": [], "qualityPreference": "android_safe"},
    )
    repo.update_bilibili_import_run(
        run["importRunId"],
        preview={},
    )
    client = CollectionPreviewClient()
    runner = _runner(repo, tmp_path, bili_client=client)

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    assert client.playurl_calls == [{"bvid": "BV1xx411c7mD", "cid": 1001, "qn": 80}]
    assert repo.get_bilibili_import_run(run["importRunId"])["status"] == "imported"


@pytest.mark.parametrize(
    ("component", "error_code"),
    [
        ("playurl", "bilibili.playurl_failed"),
        ("download", "bilibili.download_failed"),
        ("merge", "bilibili.merge_failed"),
        ("upload", "bilibili.upload_failed"),
        ("resource", "bilibili.import_failed"),
    ],
)
def test_runner_marks_failures_on_run_and_async_task(tmp_path: Path, component: str, error_code: str) -> None:
    repo, course, run, task = _build_run()
    kwargs: dict[str, Any] = {}
    if component == "playurl":
        kwargs["bili_client"] = FakeClient(playurl_error=RuntimeError("playurl boom"))
    elif component == "download":
        kwargs["downloader"] = FakeDownloader(error=RuntimeError("download boom"))
    elif component == "merge":
        kwargs["merger"] = FakeMerger(error=RuntimeError("merge boom"))
    elif component == "upload":
        kwargs["storage"] = FakeStorage(error=RuntimeError("upload boom"))
    elif component == "resource":
        repo.create_resource = lambda *args, **kw: (_ for _ in ()).throw(RuntimeError("resource boom"))  # type: ignore[method-assign]
    runner = _runner(repo, tmp_path, **kwargs)

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    async_task = repo.get_async_task(task["taskId"])
    assert updated is not None
    assert async_task is not None
    assert updated["status"] == "failed"
    assert updated["stage"] == "error"
    assert updated["errorCode"] == error_code
    assert updated["failureReason"]
    assert async_task["status"] == "failed"
    assert async_task["errorCode"] == error_code
    assert repo.list_resources(course["courseId"]) == []


def test_runner_marks_auth_expired_provider_failure_recoverable(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    runner = _runner(
        repo,
        tmp_path,
        bili_client=FakeClient(
            playurl_error=ServiceError(
                message="Bilibili auth session is expired.",
                error_code="bilibili.auth_expired",
                status_code=401,
            )
        ),
    )

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    async_task = repo.get_async_task(task["taskId"])
    assert updated is not None
    assert async_task is not None
    assert updated["status"] == "recoverable"
    assert updated["stage"] == "error"
    assert updated["errorCode"] == "bilibili.auth_expired"
    assert updated["recoverable"] is True
    assert async_task["status"] == "failed"


def test_runner_cleans_runtime_dir_on_failure(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    runner = _runner(repo, tmp_path, downloader=FakeDownloader(error=RuntimeError("download boom")))

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    assert updated is not None
    assert updated["status"] == "failed"
    assert not (tmp_path / str(run["importRunId"])).exists()


def test_runner_stops_when_run_is_already_canceled(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    repo.update_bilibili_import_run(run["importRunId"], status="canceled", stage="canceled")
    downloader = FakeDownloader()
    runner = _runner(repo, tmp_path, downloader=downloader)

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    assert updated is not None
    assert updated["status"] == "canceled"
    assert repo.list_resources(course["courseId"]) == []
    assert downloader.downloaded == []


def test_runner_does_not_upload_or_create_resource_when_canceled_after_merge(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    storage = FakeStorage()
    runner = _runner(repo, tmp_path, storage=storage, merger=CancelAfterMerge(repo, run["importRunId"]))

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    async_task = repo.get_async_task(task["taskId"])
    assert updated is not None
    assert async_task is not None
    assert updated["status"] == "canceled"
    assert updated["stage"] == "canceled"
    assert async_task["status"] == "canceled"
    assert storage.uploads == []
    assert repo.list_resources(course["courseId"]) == []


def test_runner_deletes_uploaded_object_when_canceled_after_upload(tmp_path: Path) -> None:
    repo, course, run, task = _build_run()
    storage = CancelAfterUploadStorage(repo, run["importRunId"])
    runner = _runner(repo, tmp_path, storage=storage)

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": task["taskId"]})

    updated = repo.get_bilibili_import_run(run["importRunId"])
    async_task = repo.get_async_task(task["taskId"])
    assert updated is not None
    assert async_task is not None
    assert updated["status"] == "canceled"
    assert updated["stage"] == "canceled"
    assert async_task["status"] == "canceled"
    assert len(storage.uploads) == 1
    assert storage.deletes == [storage.uploads[0]["objectKey"]]
    assert repo.list_resources(course["courseId"]) == []


def test_bilibili_import_payload_and_dispatchers_are_registered() -> None:
    payloads = importlib.import_module("server.tasks.payloads")
    assert hasattr(payloads, "BilibiliImportPayload")
    BilibiliImportPayload = payloads.BilibiliImportPayload
    TASK_PAYLOAD_MODELS = payloads.TASK_PAYLOAD_MODELS

    payload = BilibiliImportPayload(courseId=101, importRunId=9101).model_dump(by_alias=True)
    assert payload == {"courseId": 101, "importRunId": 9101}
    assert TASK_PAYLOAD_MODELS["bilibili_import"] is BilibiliImportPayload

    noop = NoopTaskDispatcher()
    noop.enqueue_bilibili_import(task_id=7001, payload=payload)
    assert noop.enqueued == [
        {"taskId": 7001, "taskType": "bilibili_import", "payload": payload, "adapter": "noop"}
    ]

    repo, _, _, _ = _build_run()
    in_memory = InMemoryTaskDispatcher(parse_runs=repo, async_tasks=repo)
    in_memory.enqueue_bilibili_import(task_id=7002, payload=payload)
    assert in_memory.enqueued == [
        {"taskId": 7002, "taskType": "bilibili_import", "payload": payload, "adapter": "in_memory"}
    ]

    dispatcher = DramatiqTaskDispatcher()
    assert dispatcher.bilibili_import_actor_path == "server.tasks.worker:bilibili_import"
