from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from server.infra.db.base import Base
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.infra.storage import ObjectStat
from server.tasks.bilibili_import import BilibiliImportRunner
from server.tests.test_api import AUTH_HEADERS, create_manual_course, request
from server.tests.test_bilibili_import_runner import FakeDownloader, FakeMerger


class _UploadStorage:
    def __init__(self, *, fail_on_upload: int | None = None) -> None:
        self.fail_on_upload = fail_on_upload
        self.uploads: list[dict[str, Any]] = []

    def upload_file(
        self,
        object_key: str,
        source_path: str | Path,
        *,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ObjectStat:
        self.uploads.append(
            {
                "objectKey": object_key,
                "contentType": content_type,
                "metadata": dict(metadata or {}),
            }
        )
        if self.fail_on_upload is not None and len(self.uploads) == self.fail_on_upload:
            raise RuntimeError("upload failed")
        return ObjectStat(
            size_bytes=Path(source_path).stat().st_size,
            checksum_required=False,
        )

    def delete_object(self, object_key: str) -> None:
        return None


class _PreviewClient:
    def __init__(self, *, parts: list[dict[str, Any]], source_type: str = "multi_p", title: str = "B站课程") -> None:
        self.parts = parts
        self.source_type = source_type
        self.title = title

    def preview(self, source_url: str, cookies: dict[str, Any]) -> dict[str, Any]:
        return {
            "previewId": f"preview-{self.source_type}",
            "sourceUrl": source_url,
            "sourceType": self.source_type,
            "title": self.title,
            "coverUrl": None,
            "totalParts": len(self.parts),
            "defaultSelectionMode": "all_parts",
            "parts": self.parts,
        }

    def playurl(
        self,
        *,
        source_url: str,
        part: dict[str, Any],
        cookies: dict[str, Any],
        quality_preference: str,
    ) -> dict[str, Any]:
        return {
            "videoUrl": f"https://upos.test/{part['partId']}.video.m4s",
            "audioUrl": f"https://upos.test/{part['partId']}.audio.m4s",
            "headers": {"Referer": source_url},
        }


class _MappingFailureRepository(MemoryScaffoldRepository):
    def __init__(self, store: RuntimeStore) -> None:
        super().__init__(store)
        self.fail_next_resource_mapping = True

    def update_bilibili_import_run(self, import_run_id: int, **changes: Any) -> dict[str, Any] | None:
        selection = changes.get("selection")
        if self.fail_next_resource_mapping and isinstance(selection, dict):
            part_map = selection.get("partLessonMap")
            if isinstance(part_map, dict) and any(
                isinstance(mapping, dict) and mapping.get("resourceId") is not None
                for mapping in part_map.values()
            ):
                self.fail_next_resource_mapping = False
                raise RuntimeError("mapping write failed after resource create")
        return super().update_bilibili_import_run(import_run_id, **changes)


def _document_payload(course_id: int, suffix: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "resourceType": "pdf",
        "objectKey": f"raw/1/{course_id}/{suffix}.pdf",
        "originalName": f"{suffix}.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 1024,
        "checksum": f"sha256:{suffix}",
    }
    payload.update(overrides)
    return payload


def _video_payload(course_id: int, suffix: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "resourceType": "mp4",
        "objectKey": f"raw/1/{course_id}/{suffix}.mp4",
        "originalName": f"{suffix}.mp4",
        "mimeType": "video/mp4",
        "sizeBytes": 2048,
        "checksum": f"sha256:{suffix}",
    }
    payload.update(overrides)
    return payload


def _create_lesson(course_id: int, title: str) -> dict[str, Any]:
    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/lessons",
            headers=AUTH_HEADERS,
            json_body={"title": title},
        )
    )
    assert status == 201
    return body["data"]["lesson"]


def _complete_upload(course_id: int, payload: dict[str, Any], *, key: str) -> tuple[int, dict[str, Any]]:
    return asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-complete",
            headers=AUTH_HEADERS | {"idempotency-key": key},
            json_body=payload,
        )
    )


def test_document_upload_requires_scope_and_accepts_course_or_lesson_scope() -> None:
    course_id, _ = create_manual_course(
        idempotency_key="task5-doc-scope-course",
        title="Task5 文档资料课",
    )

    for resource_type, mime_type in [
        ("pdf", "application/pdf"),
        ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("srt", "text/plain"),
    ]:
        suffix = f"missing-scope-{resource_type}"
        init_missing_status, init_missing_body = asyncio.run(
            request(
                "POST",
                f"/api/v1/courses/{course_id}/resources/upload-init",
                headers=AUTH_HEADERS,
                json_body={
                    "resourceType": resource_type,
                    "filename": f"{suffix}.{resource_type}",
                    "mimeType": mime_type,
                    "sizeBytes": 1024,
                    "checksum": f"sha256:init-{suffix}",
                },
            )
        )
        missing_status, missing_body = _complete_upload(
            course_id,
            _document_payload(
                course_id,
                suffix,
                resourceType=resource_type,
                objectKey=f"raw/1/{course_id}/{suffix}.{resource_type}",
                originalName=f"{suffix}.{resource_type}",
                mimeType=mime_type,
                checksum=f"sha256:{suffix}",
            ),
            key=f"task5-doc-{suffix}",
        )
        assert init_missing_status == 400
        assert init_missing_body["errorCode"] == "resource.scope_required"
        assert missing_status == 400
        assert missing_body["errorCode"] == "resource.scope_required"

    no_lesson_status, no_lesson_body = _complete_upload(
        course_id,
        _document_payload(course_id, "lesson-no-id", scopeType="lesson"),
        key="task5-doc-lesson-no-id",
    )
    assert no_lesson_status == 400
    assert no_lesson_body["errorCode"] == "resource.lesson_mismatch"

    bad_lesson_status, bad_lesson_body = _complete_upload(
        course_id,
        _document_payload(course_id, "lesson-bad-id", scopeType="lesson", lessonId=999999),
        key="task5-doc-lesson-bad-id",
    )
    assert bad_lesson_status == 400
    assert bad_lesson_body["errorCode"] == "resource.lesson_mismatch"

    lesson = _create_lesson(course_id, "资料节课")
    course_status, course_body = _complete_upload(
        course_id,
        _document_payload(course_id, "course-scope", scopeType="course"),
        key="task5-doc-course-scope",
    )
    lesson_status, lesson_body = _complete_upload(
        course_id,
        _document_payload(
            course_id,
            "lesson-scope",
            scopeType="lesson",
            lessonId=lesson["lessonId"],
            usageRole="lesson_material",
        ),
        key="task5-doc-lesson-scope",
    )

    assert course_status == 201
    assert course_body["data"]["scopeType"] == "course"
    assert course_body["data"]["lessonId"] is None
    assert course_body["data"]["usageRole"] == "course_material"
    assert lesson_status == 201
    assert lesson_body["data"]["scopeType"] == "lesson"
    assert lesson_body["data"]["lessonId"] == lesson["lessonId"]
    assert lesson_body["data"]["usageRole"] == "lesson_material"


def test_upload_init_writes_scope_metadata_for_object_storage() -> None:
    course_id, _ = create_manual_course(
        idempotency_key="task5-init-scope-course",
        title="Task5 初始化上传课",
    )
    lesson = _create_lesson(course_id, "视频节课")

    status, body = asyncio.run(
        request(
            "POST",
            f"/api/v1/courses/{course_id}/resources/upload-init",
            headers=AUTH_HEADERS,
            json_body={
                "resourceType": "mp4",
                "filename": "binding.mp4",
                "mimeType": "video/mp4",
                "sizeBytes": 2048,
                "checksum": "sha256:binding",
                "lessonPlacement": "bind_existing",
                "lessonId": lesson["lessonId"],
            },
        )
    )

    assert status == 200
    assert body["data"]["headers"]["x-amz-meta-scope-type"] == "lesson"
    assert body["data"]["headers"]["x-amz-meta-lesson-id"] == str(lesson["lessonId"])


def test_local_video_upload_auto_creates_or_binds_primary_lesson_video() -> None:
    course_id, _ = create_manual_course(
        idempotency_key="task5-video-placement-course",
        title="Task5 本地视频课",
    )

    auto_status, auto_body = _complete_upload(
        course_id,
        _video_payload(
            course_id,
            "auto-video",
            lessonPlacement="auto_create",
            lessonTitle="自动生成节课",
            durationSec=90,
        ),
        key="task5-video-auto-create",
    )

    assert auto_status == 201
    auto_resource = auto_body["data"]
    assert auto_resource["scopeType"] == "lesson"
    assert auto_resource["usageRole"] == "primary_video"
    lessons_status, lessons_body = asyncio.run(
        request("GET", f"/api/v1/courses/{course_id}/lessons", headers=AUTH_HEADERS)
    )
    assert lessons_status == 200
    auto_lesson = lessons_body["data"]["items"][0]
    assert auto_lesson["title"] == "自动生成节课"
    assert auto_lesson["primaryVideoResourceId"] == auto_resource["resourceId"]

    target = _create_lesson(course_id, "绑定节课")
    bind_status, bind_body = _complete_upload(
        course_id,
        _video_payload(
            course_id,
            "bound-video",
            lessonPlacement="bind_existing",
            lessonId=target["lessonId"],
            durationSec=120,
        ),
        key="task5-video-bind-existing",
    )
    bad_status, bad_body = _complete_upload(
        course_id,
        _video_payload(
            course_id,
            "bad-bound-video",
            lessonPlacement="bind_existing",
            lessonId=999999,
        ),
        key="task5-video-bind-invalid",
    )

    assert bind_status == 201
    assert bind_body["data"]["lessonId"] == target["lessonId"]
    assert bind_body["data"]["usageRole"] == "primary_video"
    detail_status, detail_body = asyncio.run(
        request(
            "GET",
            f"/api/v1/courses/{course_id}/lessons/{target['lessonId']}",
            headers=AUTH_HEADERS,
        )
    )
    assert detail_status == 200
    assert detail_body["data"]["lesson"]["primaryVideoResourceId"] == bind_body["data"]["resourceId"]
    assert bad_status == 400
    assert bad_body["errorCode"] == "resource.lesson_mismatch"


def _parts(*titles: str) -> list[dict[str, Any]]:
    return [
        {
            "partId": f"p{index}",
            "title": title,
            "durationSec": 60 + index,
            "cid": 1000 + index,
            "pageNo": index,
            "selectedByDefault": True,
        }
        for index, title in enumerate(titles, start=1)
    ]


def _build_import_run(
    *,
    source_type: str,
    parts: list[dict[str, Any]],
    selection: dict[str, Any] | None = None,
) -> tuple[MemoryScaffoldRepository, dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title=f"{source_type} 导入课",
        entry_type="manual_import",
        goal_text="导入 B站视频",
        preferred_style="balanced",
    )
    preview = {
        "previewId": f"preview-{source_type}",
        "sourceUrl": "https://www.bilibili.com/video/BVtask5",
        "sourceType": source_type,
        "title": f"{source_type} 预览",
        "coverUrl": None,
        "totalParts": len(parts),
        "defaultSelectionMode": "all_parts",
        "parts": parts,
    }
    run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url=preview["sourceUrl"],
        source_type=source_type,
        preview=preview,
        selection=selection
        or {
            "selectionMode": "all_parts",
            "selectedPartIds": [],
            "qualityPreference": "android_safe",
            "lessonMode": "auto_per_video",
            "partLessonTitles": {},
            "partLessonMap": {},
        },
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


def _run_import(
    *,
    repo: Any,
    course: dict[str, Any],
    run: dict[str, Any],
    task: dict[str, Any],
    parts: list[dict[str, Any]],
    tmp_path: Path,
    storage: _UploadStorage | None = None,
    source_type: str = "multi_p",
) -> None:
    runner = BilibiliImportRunner(
        bilibili=repo,
        resources=repo,
        lessons=getattr(repo, "store", repo),
        async_tasks=repo,
        storage=storage or _UploadStorage(),
        bili_client=_PreviewClient(parts=parts, source_type=source_type),
        downloader=FakeDownloader(),
        merger=FakeMerger(),
        runtime_dir=tmp_path,
    )
    runner.run(
        {
            "courseId": course["courseId"],
            "importRunId": run["importRunId"],
            "taskId": task["taskId"],
        }
    )


def test_fake_bilibili_single_video_creates_one_lesson(tmp_path: Path) -> None:
    parts = _parts("单视频")
    repo, course, run, task = _build_import_run(source_type="single_video", parts=parts)

    _run_import(repo=repo, course=course, run=run, task=task, parts=parts, tmp_path=tmp_path, source_type="single_video")

    lessons = repo.store.list_lessons(course["courseId"])
    resources = repo.list_resources(course["courseId"])
    updated = repo.get_bilibili_import_run(run["importRunId"])
    assert len(lessons) == 1
    assert len(resources) == 1
    assert resources[0]["scopeType"] == "lesson"
    assert resources[0]["lessonId"] == lessons[0]["lessonId"]
    assert resources[0]["sourcePartId"] == "p1"
    assert lessons[0]["primaryVideoResourceId"] == resources[0]["resourceId"]
    assert updated["selection"]["partLessonMap"]["p1"]["lessonId"] == lessons[0]["lessonId"]


def test_fake_bilibili_multi_p_and_collection_create_one_lesson_per_selected_item(tmp_path: Path) -> None:
    multi_parts = _parts("第一讲", "第二讲")
    repo, course, run, task = _build_import_run(
        source_type="multi_p",
        parts=multi_parts,
        selection={
            "selectionMode": "selected_parts",
            "selectedPartIds": ["p1", "p2"],
            "qualityPreference": "android_safe",
            "lessonMode": "auto_per_video",
            "partLessonTitles": {"p2": "自定义第二讲"},
            "partLessonMap": {},
        },
    )

    _run_import(repo=repo, course=course, run=run, task=task, parts=multi_parts, tmp_path=tmp_path, source_type="multi_p")

    lessons = repo.store.list_lessons(course["courseId"])
    resources = repo.list_resources(course["courseId"])
    assert [lesson["title"] for lesson in lessons] == ["第一讲", "自定义第二讲"]
    assert [resource["sourcePartId"] for resource in resources] == ["p1", "p2"]
    assert {resource["lessonId"] for resource in resources} == {lesson["lessonId"] for lesson in lessons}

    collection_parts = _parts("合集第一讲", "合集第二讲")
    collection_repo, collection_course, collection_run, collection_task = _build_import_run(
        source_type="collection",
        parts=collection_parts,
    )
    _run_import(
        repo=collection_repo,
        course=collection_course,
        run=collection_run,
        task=collection_task,
        parts=collection_parts,
        tmp_path=tmp_path,
        source_type="collection",
    )

    assert len(collection_repo.store.list_lessons(collection_course["courseId"])) == 2
    assert [
        resource["sourceType"]
        for resource in collection_repo.list_resources(collection_course["courseId"])
    ] == ["bilibili_collection_item", "bilibili_collection_item"]


def test_bilibili_import_retry_reuses_existing_part_lesson(tmp_path: Path) -> None:
    parts = _parts("第一讲", "第二讲")
    repo, course, run, task = _build_import_run(source_type="multi_p", parts=parts)

    failing_storage = _UploadStorage(fail_on_upload=2)
    _run_import(
        repo=repo,
        course=course,
        run=run,
        task=task,
        parts=parts,
        tmp_path=tmp_path,
        storage=failing_storage,
        source_type="multi_p",
    )
    assert repo.get_bilibili_import_run(run["importRunId"])["status"] == "failed"
    failed_lessons = repo.store.list_lessons(course["courseId"])
    assert len(failed_lessons) == 2
    assert len(repo.list_resources(course["courseId"])) == 1

    repo.update_bilibili_import_run(run["importRunId"], status="recoverable", stage="error")
    _run_import(repo=repo, course=course, run=run, task=task, parts=parts, tmp_path=tmp_path, source_type="multi_p")

    lessons = repo.store.list_lessons(course["courseId"])
    resources = repo.list_resources(course["courseId"])
    updated = repo.get_bilibili_import_run(run["importRunId"])
    assert updated["status"] == "imported"
    assert len(lessons) == 2
    assert len(resources) == 2
    assert sorted(updated["resourceIds"]) == sorted(resource["resourceId"] for resource in resources)
    assert set(updated["selection"]["partLessonMap"]) == {"p1", "p2"}


def test_bilibili_import_ignores_client_supplied_resource_mapping(tmp_path: Path) -> None:
    parts = _parts("第一讲")
    repo, course, run, task = _build_import_run(
        source_type="multi_p",
        parts=parts,
        selection={
            "selectionMode": "all_parts",
            "selectedPartIds": [],
            "qualityPreference": "android_safe",
            "lessonMode": "auto_per_video",
            "partLessonTitles": {},
            "partLessonMap": {},
        },
    )
    other_course = repo.create_course(
        title="其他课程",
        entry_type="manual_import",
        goal_text="不应被复用",
        preferred_style="balanced",
    )
    other_resource = repo.create_resource(
        other_course["courseId"],
        {
            "resourceType": "mp4",
            "scopeType": "course",
            "usageRole": "course_material",
            "sourceType": "bilibili_part",
            "sourcePartId": "p1",
            "originUrl": "https://www.bilibili.com/video/BVother",
            "objectKey": "raw/1/other/bilibili/other.mp4",
            "originalName": "other.mp4",
            "mimeType": "video/mp4",
            "sizeBytes": 100,
            "checksum": "sha256:other",
            "parsePolicyJson": {"source": "bilibili", "importRunId": 999999},
        },
    )
    selection = dict(run["selection"])
    selection["partLessonMap"] = {
        "p1": {"resourceId": other_resource["resourceId"], "sourcePartId": "p1"}
    }
    repo.update_bilibili_import_run(run["importRunId"], selection=selection)

    _run_import(repo=repo, course=course, run=run, task=task, parts=parts, tmp_path=tmp_path, source_type="multi_p")

    resources = repo.list_resources(course["courseId"])
    lessons = repo.store.list_lessons(course["courseId"])
    updated = repo.get_bilibili_import_run(run["importRunId"])
    assert len(resources) == 1
    assert len(lessons) == 1
    assert resources[0]["resourceId"] != other_resource["resourceId"]
    assert updated["selection"]["partLessonMap"]["p1"]["resourceId"] == resources[0]["resourceId"]


def test_bilibili_import_retry_reuses_resource_created_before_mapping_failure(tmp_path: Path) -> None:
    parts = _parts("第一讲")
    repo = _MappingFailureRepository(RuntimeStore())
    course = repo.create_course(
        title="mapping 失败重试课",
        entry_type="manual_import",
        goal_text="导入 B站视频",
        preferred_style="balanced",
    )
    preview = {
        "previewId": "preview-mapping-failure",
        "sourceUrl": "https://www.bilibili.com/video/BVmapping",
        "sourceType": "multi_p",
        "title": "mapping 失败预览",
        "coverUrl": None,
        "totalParts": len(parts),
        "defaultSelectionMode": "all_parts",
        "parts": parts,
    }
    run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url=preview["sourceUrl"],
        source_type="multi_p",
        preview=preview,
        selection={
            "selectionMode": "all_parts",
            "selectedPartIds": [],
            "qualityPreference": "android_safe",
            "lessonMode": "auto_per_video",
            "partLessonTitles": {},
            "partLessonMap": {},
        },
    )
    task = repo.create_async_task(
        course_id=course["courseId"],
        task_type="bilibili_import",
        payload_json={"courseId": course["courseId"], "importRunId": run["importRunId"]},
        target_type="bilibili_import_run",
        target_id=run["importRunId"],
    )
    repo.update_bilibili_import_run(run["importRunId"], task_id=task["taskId"])

    _run_import(repo=repo, course=course, run=run, task=task, parts=parts, tmp_path=tmp_path, source_type="multi_p")
    failed = repo.get_bilibili_import_run(run["importRunId"])
    assert failed["status"] == "failed"
    assert len(repo.list_resources(course["courseId"])) == 1
    assert failed["selection"]["partLessonMap"]["p1"].get("resourceId") is None

    repo.update_bilibili_import_run(run["importRunId"], status="recoverable", stage="error")
    _run_import(repo=repo, course=course, run=run, task=task, parts=parts, tmp_path=tmp_path, source_type="multi_p")

    updated = repo.get_bilibili_import_run(run["importRunId"])
    resources = repo.list_resources(course["courseId"])
    assert updated["status"] == "imported"
    assert len(resources) == 1
    assert updated["selection"]["partLessonMap"]["p1"]["resourceId"] == resources[0]["resourceId"]


def _build_sql_import_run(
    *,
    source_type: str,
    parts: list[dict[str, Any]],
    selection: dict[str, Any] | None = None,
) -> tuple[SqlAlchemyRuntimeRepository, Session, dict[str, Any], dict[str, Any], dict[str, Any]]:
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    repo = SqlAlchemyRuntimeRepository(session)
    course = repo.create_course(
        title=f"{source_type} SQL 导入课",
        entry_type="manual_import",
        goal_text="导入 B站视频",
        preferred_style="balanced",
    )
    preview = {
        "previewId": f"preview-sql-{source_type}",
        "sourceUrl": "https://www.bilibili.com/video/BVtask5sql",
        "sourceType": source_type,
        "title": f"{source_type} SQL 预览",
        "coverUrl": None,
        "totalParts": len(parts),
        "defaultSelectionMode": "all_parts",
        "parts": parts,
    }
    run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url=preview["sourceUrl"],
        source_type=source_type,
        preview=preview,
        selection=selection
        or {
            "selectionMode": "all_parts",
            "selectedPartIds": [],
            "qualityPreference": "android_safe",
            "lessonMode": "auto_per_video",
            "partLessonTitles": {},
            "partLessonMap": {},
        },
    )
    task = repo.create_async_task(
        course_id=course["courseId"],
        task_type="bilibili_import",
        payload_json={"courseId": course["courseId"], "importRunId": run["importRunId"]},
        target_type="bilibili_import_run",
        target_id=run["importRunId"],
    )
    repo.update_bilibili_import_run(run["importRunId"], task_id=task["taskId"])
    return repo, session, course, run, task


def test_sql_bilibili_import_retry_reuses_existing_part_lesson_and_items(tmp_path: Path) -> None:
    parts = _parts("SQL 第一讲", "SQL 第二讲")
    repo, session, course, run, task = _build_sql_import_run(source_type="multi_p", parts=parts)

    _run_import(
        repo=repo,
        course=course,
        run=run,
        task=task,
        parts=parts,
        tmp_path=tmp_path,
        storage=_UploadStorage(fail_on_upload=2),
        source_type="multi_p",
    )
    failed_run = repo.get_bilibili_import_run(run["importRunId"])
    assert failed_run["status"] == "failed"
    assert len(repo.list_lessons(course["courseId"])) == 2
    assert len(repo.list_resources(course["courseId"])) == 1
    assert {item["itemKey"] for item in failed_run["items"]} == {"p1", "p2"}
    assert {item["lessonId"] for item in failed_run["items"]} == {
        lesson["lessonId"] for lesson in repo.list_lessons(course["courseId"])
    }

    repo.update_bilibili_import_run(run["importRunId"], status="recoverable", stage="error")
    _run_import(repo=repo, course=course, run=run, task=task, parts=parts, tmp_path=tmp_path, source_type="multi_p")

    updated = repo.get_bilibili_import_run(run["importRunId"])
    lessons = repo.list_lessons(course["courseId"])
    resources = repo.list_resources(course["courseId"])
    assert updated["status"] == "imported"
    assert len(lessons) == 2
    assert len(resources) == 2
    assert set(updated["selection"]["partLessonMap"]) == {"p1", "p2"}
    assert sorted(item["itemKey"] for item in updated["items"]) == ["p1", "p2"]
    assert all(item["status"] == "imported" for item in updated["items"])
    assert all(item["lessonId"] is not None for item in updated["items"])
    assert all(item["metadataJson"]["sourcePartId"] == item["itemKey"] for item in updated["items"])
    assert session.execute(sa.text("select count(*) from course_lessons")).scalar_one() == 2
