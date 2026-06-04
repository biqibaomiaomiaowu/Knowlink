from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.infra.db.base import Base
from server.infra.repositories.memory_runtime import RuntimeStore
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


def _sql_repo() -> Iterator[SqlAlchemyRuntimeRepository]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    session = session_factory()
    try:
        yield SqlAlchemyRuntimeRepository(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(params=["memory", "sql"])
def repo(request: pytest.FixtureRequest) -> Iterator[Any]:
    if request.param == "memory":
        yield RuntimeStore()
        return
    yield from _sql_repo()


def _create_course(repo: Any, title: str = "数据库系统") -> int:
    course = repo.create_course(
        title=title,
        entry_type="manual_import",
        goal_text="期末复习",
        preferred_style="balanced",
    )
    return int(course["courseId"])


def _resource_payload(
    *,
    resource_type: str = "pdf",
    original_name: str = "material.pdf",
    scope_type: str | None = "course",
    lesson_id: int | None = None,
    usage_role: str | None = "course_material",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "resourceType": resource_type,
        "sourceType": "upload",
        "objectKey": f"raw/{original_name}",
        "previewKey": None,
        "originalName": original_name,
        "mimeType": "video/mp4" if resource_type == "mp4" else "application/pdf",
        "sizeBytes": 1024,
        "checksum": f"sha256:{original_name}",
        "ingestStatus": "uploaded",
        "validationStatus": "valid",
        "processingStatus": "pending",
    }
    if scope_type is not None:
        payload["scopeType"] = scope_type
    if lesson_id is not None:
        payload["lessonId"] = lesson_id
    if usage_role is not None:
        payload["usageRole"] = usage_role
    return payload


def test_lessons_append_monotonic_order_and_reorder(repo: Any) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="关系模型")
    second = repo.create_lesson(course_id=course_id, title="关系代数")
    third = repo.create_lesson(course_id=course_id, title="SQL")

    assert [first["orderIndex"], second["orderIndex"], third["orderIndex"]] == [1, 2, 3]

    reordered = repo.reorder_lessons(
        course_id=course_id,
        lesson_ids=[third["lessonId"], first["lessonId"], second["lessonId"]],
    )

    assert [(lesson["lessonId"], lesson["orderIndex"]) for lesson in reordered] == [
        (third["lessonId"], 1),
        (first["lessonId"], 2),
        (second["lessonId"], 3),
    ]

    with pytest.raises(ValueError, match="lesson.order_conflict"):
        repo.reorder_lessons(
            course_id=course_id,
            lesson_ids=[first["lessonId"], first["lessonId"], second["lessonId"]],
        )


def test_soft_delete_lesson_marks_deleted_and_compresses_order(repo: Any) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")
    third = repo.create_lesson(course_id=course_id, title="第 3 节")

    deleted = repo.soft_delete_lesson(course_id=course_id, lesson_id=second["lessonId"])

    assert deleted["lessonStatus"] == "deleted"
    active_lessons = repo.list_lessons(course_id)
    assert [lesson["lessonId"] for lesson in active_lessons] == [first["lessonId"], third["lessonId"]]
    assert [lesson["orderIndex"] for lesson in active_lessons] == [1, 2]
    assert repo.get_lesson(course_id=course_id, lesson_id=second["lessonId"]) is None
    assert repo.get_lesson(course_id=course_id, lesson_id=second["lessonId"], include_deleted=True)[
        "lessonStatus"
    ] == "deleted"


def test_soft_delete_multiple_lessons_keeps_deleted_order_unique(repo: Any) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")
    third = repo.create_lesson(course_id=course_id, title="第 3 节")
    fourth = repo.create_lesson(course_id=course_id, title="第 4 节")

    repo.soft_delete_lesson(course_id=course_id, lesson_id=second["lessonId"])
    repo.soft_delete_lesson(course_id=course_id, lesson_id=third["lessonId"])

    active_lessons = repo.list_lessons(course_id)
    assert [lesson["lessonId"] for lesson in active_lessons] == [first["lessonId"], fourth["lessonId"]]
    assert [lesson["orderIndex"] for lesson in active_lessons] == [1, 2]


def test_reorder_after_deleted_lesson_avoids_temporary_order_collision(repo: Any) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")
    third = repo.create_lesson(course_id=course_id, title="第 3 节")

    repo.soft_delete_lesson(course_id=course_id, lesson_id=first["lessonId"])
    reordered = repo.reorder_lessons(course_id=course_id, lesson_ids=[third["lessonId"], second["lessonId"]])

    assert [lesson["lessonId"] for lesson in reordered] == [third["lessonId"], second["lessonId"]]
    assert [lesson["orderIndex"] for lesson in reordered] == [1, 2]


def test_soft_delete_missing_lesson_raises_consistently(repo: Any) -> None:
    course_id = _create_course(repo)

    with pytest.raises(ValueError, match="lesson.not_found"):
        repo.soft_delete_lesson(course_id=course_id, lesson_id=999999)


def test_update_lesson_and_mark_lesson_artifacts_stale(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="旧标题")

    updated = repo.update_lesson(
        course_id=course_id,
        lesson_id=lesson["lessonId"],
        changes={"title": "新标题", "primaryVideoStartSec": 10, "primaryVideoEndSec": 120},
    )
    artifact = repo.create_scoped_artifact(
        artifact_type="handout_version",
        course_id=course_id,
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="ready",
    )

    stale_artifacts = repo.mark_lesson_artifacts_stale(course_id=course_id, lesson_ids=[lesson["lessonId"]])
    artifacts = repo.list_lesson_artifacts(course_id=course_id, lesson_id=lesson["lessonId"])

    assert updated["title"] == "新标题"
    assert updated["primaryVideoStartSec"] == 10
    assert updated["primaryVideoEndSec"] == 120
    assert stale_artifacts == [
        {
            "artifactId": artifact["artifactId"],
            "artifactType": "handout_version",
            "courseId": course_id,
            "scopeType": "lesson",
            "lessonId": lesson["lessonId"],
            "startLessonId": None,
            "endLessonId": None,
            "status": "stale",
        }
    ]
    assert artifacts[0]["artifactId"] == artifact["artifactId"]
    assert artifacts[0]["artifactType"] == "handout_version"
    assert artifacts[0]["scopeType"] == "lesson"
    assert artifacts[0]["lessonId"] == lesson["lessonId"]
    assert artifacts[0]["status"] == "stale"


def test_update_resource_scope_moves_lesson_resources(repo: Any) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")
    resource = repo.create_resource(
        course_id,
        _resource_payload(
            original_name="second-note.pdf",
            scope_type="lesson",
            lesson_id=second["lessonId"],
            usage_role="lesson_material",
        ),
    )

    moved = dict(
        repo.update_resource_scope(
            course_id=course_id,
            resource_id=resource["resourceId"],
            scope_type="lesson",
            lesson_id=first["lessonId"],
            usage_role="lesson_material",
        )
    )
    promoted = repo.update_resource_scope(
        course_id=course_id,
        resource_id=resource["resourceId"],
        scope_type="course",
        lesson_id=None,
        usage_role="primary_video",
    )

    assert moved["scopeType"] == "lesson"
    assert moved["lessonId"] == first["lessonId"]
    assert promoted["scopeType"] == "course"
    assert promoted["lessonId"] is None
    assert promoted["usageRole"] == "primary_video"
    assert repo.get_resource(resource["resourceId"])["scopeType"] == "course"
    with pytest.raises(ValueError, match="resource.lesson_mismatch"):
        repo.update_resource_scope(
            course_id=course_id,
            resource_id=resource["resourceId"],
            scope_type="lesson",
            lesson_id=999999,
        )


def test_mark_lesson_artifacts_stale_returns_type_disambiguated_rows(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="第 1 节")
    handout = repo.create_scoped_artifact(
        artifact_type="handout_version",
        course_id=course_id,
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="ready",
    )
    quiz = repo.create_scoped_artifact(
        artifact_type="quiz",
        course_id=course_id,
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="ready",
    )

    stale_artifacts = repo.mark_lesson_artifacts_stale(course_id=course_id, lesson_ids=[lesson["lessonId"]])

    assert {
        (artifact["artifactType"], artifact["artifactId"], artifact["status"])
        for artifact in stale_artifacts
    } == {
        ("handout_version", handout["artifactId"], "stale"),
        ("quiz", quiz["artifactId"], "stale"),
    }


def test_lesson_mutations_refresh_course_recent_activity(repo: Any) -> None:
    touched_course = _create_course(repo, title="待操作课程")
    newer_course = _create_course(repo, title="暂时较新课程")

    first = repo.create_lesson(course_id=touched_course, title="第 1 节")
    second = repo.create_lesson(course_id=touched_course, title="第 2 节")
    assert repo.list_courses({"sort": "recent_activity_desc"})[0]["courseId"] == touched_course

    repo.update_course(newer_course, {"title": "暂时较新课程 2"})
    repo.reorder_lessons(course_id=touched_course, lesson_ids=[second["lessonId"], first["lessonId"]])
    assert repo.list_courses({"sort": "recent_activity_desc"})[0]["courseId"] == touched_course

    repo.update_course(newer_course, {"title": "暂时较新课程 3"})
    repo.soft_delete_lesson(course_id=touched_course, lesson_id=first["lessonId"])
    assert repo.list_courses({"sort": "recent_activity_desc"})[0]["courseId"] == touched_course


def test_resource_scope_validation_and_storage(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="关系模型")

    course_resource = repo.create_resource(
        course_id,
        _resource_payload(scope_type="course", usage_role="course_material"),
    )
    lesson_resource = repo.create_resource(
        course_id,
        _resource_payload(
            resource_type="mp4",
            original_name="lesson-1.mp4",
            scope_type="lesson",
            lesson_id=lesson["lessonId"],
            usage_role="primary_video",
        ),
    )
    default_lesson_resource = repo.create_resource(
        course_id,
        _resource_payload(
            original_name="lesson-default.pdf",
            scope_type="lesson",
            lesson_id=lesson["lessonId"],
            usage_role=None,
        ),
    )

    assert course_resource["scopeType"] == "course"
    assert course_resource["lessonId"] is None
    assert course_resource["usageRole"] == "course_material"
    assert lesson_resource["scopeType"] == "lesson"
    assert lesson_resource["lessonId"] == lesson["lessonId"]
    assert lesson_resource["usageRole"] == "primary_video"
    assert default_lesson_resource["usageRole"] == "lesson_material"

    legacy_resource = repo.create_resource(course_id, _resource_payload(scope_type=None))
    assert legacy_resource["scopeType"] == "course"
    assert legacy_resource["lessonId"] is None

    with pytest.raises(ValueError, match="resource.lesson_mismatch"):
        repo.create_resource(
            course_id,
            _resource_payload(scope_type="lesson", lesson_id=None, usage_role="lesson_material"),
        )


def test_user_lesson_progress_upsert_and_get(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="关系模型")

    progress = repo.upsert_user_lesson_progress(
        course_id=course_id,
        lesson_id=lesson["lessonId"],
        payload={
            "lastPositionSec": 420,
            "handoutReadPercent": 35,
            "quizStatus": "not_generated",
            "reviewStatus": "due",
        },
    )

    assert progress["courseId"] == course_id
    assert progress["lessonId"] == lesson["lessonId"]
    assert progress["lastPositionSec"] == 420
    assert progress["lastHandoutBlockId"] is None
    assert progress["handoutReadPercent"] == 35
    assert progress["quizStatus"] == "not_generated"
    assert progress["reviewStatus"] == "due"
    assert repo.get_user_lesson_progress(course_id=course_id, lesson_id=lesson["lessonId"]) == progress


def test_user_lesson_progress_rejects_unknown_handout_block(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="关系模型")

    with pytest.raises(ValueError, match="artifact.scope_invalid"):
        repo.upsert_user_lesson_progress(
            course_id=course_id,
            lesson_id=lesson["lessonId"],
            payload={"lastHandoutBlockId": 88},
        )


@pytest.mark.parametrize(
    ("artifact_type", "scope_type"),
    [
        ("handout_version", "course"),
        ("handout_version", "lesson"),
        ("qa_session", "course"),
        ("qa_session", "lesson"),
        ("quiz", "lesson_range"),
        ("review_task_run", "lesson"),
        ("mastery_record", "lesson"),
        ("graph_snapshot", "course"),
        ("export_run", "lesson"),
    ],
)
def test_scoped_artifact_rows_accept_contract_scopes(
    repo: Any,
    artifact_type: str,
    scope_type: str,
) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")

    artifact = repo.create_scoped_artifact(
        artifact_type=artifact_type,
        course_id=course_id,
        scope_type=scope_type,
        lesson_id=first["lessonId"] if scope_type == "lesson" else None,
        start_lesson_id=first["lessonId"] if scope_type == "lesson_range" else None,
        end_lesson_id=second["lessonId"] if scope_type == "lesson_range" else None,
    )

    assert artifact["artifactType"] == artifact_type
    assert artifact["courseId"] == course_id
    assert artifact["scopeType"] == scope_type
    if scope_type == "lesson":
        assert artifact["lessonId"] == first["lessonId"]
    if scope_type == "lesson_range":
        assert artifact["startLessonId"] == first["lessonId"]
        assert artifact["endLessonId"] == second["lessonId"]


def test_lesson_range_artifact_rejects_reversed_order(repo: Any) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")

    with pytest.raises(ValueError, match="artifact.scope_invalid"):
        repo.create_scoped_artifact(
            artifact_type="quiz",
            course_id=course_id,
            scope_type="lesson_range",
            start_lesson_id=second["lessonId"],
            end_lesson_id=first["lessonId"],
        )


def test_export_artifact_preserves_requested_export_type(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="第 1 节")

    artifact = repo.create_scoped_artifact(
        artifact_type="export_run",
        course_id=course_id,
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
        status="placeholder",
        exportType="lesson_summary",
    )

    assert artifact["exportType"] == "lesson_summary"


@pytest.mark.parametrize(
    "artifact_type",
    [
        "handout_version",
        "qa_session",
        "review_task_run",
        "mastery_record",
        "graph_snapshot",
        "export_run",
    ],
)
def test_non_quiz_artifacts_reject_lesson_range_scope(repo: Any, artifact_type: str) -> None:
    course_id = _create_course(repo)
    first = repo.create_lesson(course_id=course_id, title="第 1 节")
    second = repo.create_lesson(course_id=course_id, title="第 2 节")

    with pytest.raises(ValueError, match="artifact.scope_invalid"):
        repo.create_scoped_artifact(
            artifact_type=artifact_type,
            course_id=course_id,
            scope_type="lesson_range",
            start_lesson_id=first["lessonId"],
            end_lesson_id=second["lessonId"],
        )


def test_mastery_record_scope_keeps_course_and_lesson_uniqueness(repo: Any) -> None:
    course_id = _create_course(repo)
    lesson = repo.create_lesson(course_id=course_id, title="关系模型")

    repo.create_scoped_artifact(artifact_type="mastery_record", course_id=course_id, scope_type="course")
    repo.create_scoped_artifact(
        artifact_type="mastery_record",
        course_id=course_id,
        scope_type="lesson",
        lesson_id=lesson["lessonId"],
    )

    with pytest.raises(ValueError, match="artifact.scope_invalid"):
        repo.create_scoped_artifact(artifact_type="mastery_record", course_id=course_id, scope_type="course")

    with pytest.raises(ValueError, match="artifact.scope_invalid"):
        repo.create_scoped_artifact(
            artifact_type="mastery_record",
            course_id=course_id,
            scope_type="lesson",
            lesson_id=lesson["lessonId"],
        )
