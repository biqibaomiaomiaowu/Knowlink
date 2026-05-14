from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from functools import lru_cache
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

import jsonschema
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from server.ai.embedding import get_configured_embedding_client
from server.ai.vector_projection import build_vector_document_inputs
from server.infra.db.base import utcnow
from server.infra.db.models import (
    AsyncTask,
    Course,
    CourseResource,
    CourseSegment,
    HandoutVersion,
    ParseRun,
    VectorDocument,
)
from server.infra.db.session import create_session
from server.infra.storage import ObjectStorage, ObjectStorageError
from server.parsers import parse_resource


DOCUMENT_RESOURCE_TYPES = {"pdf", "pptx", "docx"}
VIDEO_RESOURCE_TYPES = {"mp4", "srt"}
PIPELINE_TERMINAL_STATUSES = {"succeeded", "partial_success", "failed", "canceled"}
PIPELINE_SUCCESS_STATUSES = {"succeeded", "partial_success"}
STEP_CODES = [
    "resource_validate",
    "caption_extract",
    "document_parse",
    "knowledge_extract",
    "vectorize",
]


class ParsePipelineInputError(ValueError):
    pass


def run_parse_pipeline(
    message: Mapping[str, Any],
    *,
    session_factory: Callable[[], Session] = create_session,
    parse_resource_func: Callable[[str, str | Path], Any] = parse_resource,
    embedding_client_factory: Callable[[], Any] = get_configured_embedding_client,
    object_storage: ObjectStorage | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    task_id = _required_int(message, "taskId", "task_id")
    course_id = _required_int(message, "courseId", "course_id")
    parse_run_id = _required_int(message, "parseRunId", "parse_run_id")

    session = session_factory()
    try:
        return _run_with_session(
            session=session,
            task_id=task_id,
            course_id=course_id,
            parse_run_id=parse_run_id,
            parse_resource_func=parse_resource_func,
            embedding_client_factory=embedding_client_factory,
            object_storage=object_storage,
            base_dir=base_dir or Path.cwd(),
        )
    finally:
        session.close()


def _run_with_session(
    *,
    session: Session,
    task_id: int,
    course_id: int,
    parse_run_id: int,
    parse_resource_func: Callable[[str, str | Path], Any],
    embedding_client_factory: Callable[[], Any],
    object_storage: ObjectStorage | None,
    base_dir: Path,
) -> dict[str, Any]:
    root_task = _require_model(session, AsyncTask, task_id, "async_task.not_found")
    parse_run = _require_model(session, ParseRun, parse_run_id, "parse_run.not_found")
    course = _require_model(session, Course, course_id, "course.not_found")
    _validate_message_consistency(root_task=root_task, parse_run=parse_run, course=course)
    step_tasks = _step_tasks(session, course_id=course_id, parse_run_id=parse_run_id, root_task_id=task_id)
    if _should_return_existing_pipeline_result(root_task=root_task, parse_run=parse_run):
        return _existing_pipeline_result(
            session=session,
            root_task=root_task,
            parse_run=parse_run,
            course=course,
        )
    _discard_parse_run_artifacts(session=session, parse_run_id=parse_run_id)
    resources = list(
        session.scalars(
            select(CourseResource)
            .where(CourseResource.course_id == course_id)
            .order_by(CourseResource.sort_order.asc(), CourseResource.id.asc())
        )
    )

    started_at = utcnow()
    _set_task_running(root_task, progress_pct=5, started_at=started_at)
    parse_run.status = "running"
    parse_run.started_at = parse_run.started_at or started_at
    parse_run.progress_pct = max(parse_run.progress_pct, 5)
    course.pipeline_stage = "parse"
    course.pipeline_status = "running"
    session.commit()

    summary: dict[str, Any] = {"resourceCount": len(resources), "segmentCount": 0, "vectorDocumentCount": 0, "issues": []}
    valid_resources = _validate_resources(resources=resources, base_dir=base_dir, object_storage=object_storage)
    invalid_count = len(resources) - len(valid_resources)
    if not valid_resources:
        _finish_step(
            step_tasks.get("resource_validate"),
            status="failed",
            progress_pct=100,
            error_code="resource.not_found",
            error_message="No readable local resource file was found for this parse run.",
        )
        summary["issues"].append({"code": "resource.not_found", "count": invalid_count})
        return _finish_pipeline(
            session=session,
            course=course,
            parse_run=parse_run,
            root_task=root_task,
            status="failed",
            summary=summary,
            error_code="resource.not_found",
            error_message="No readable local resource file was found for this parse run.",
        )

    _finish_step(
        step_tasks.get("resource_validate"),
        status="partial_success" if invalid_count else "succeeded",
        progress_pct=100,
        result_json={"validResourceCount": len(valid_resources), "invalidResourceCount": invalid_count},
    )

    parsed_segments: list[dict[str, Any]] = []
    parse_failures: list[dict[str, Any]] = []
    caption_segments, caption_failures = _parse_resource_group(
        session=session,
        resources=[item for item in valid_resources if item[0].resource_type in VIDEO_RESOURCE_TYPES],
        course_id=course_id,
        parse_run_id=parse_run_id,
        step_task=step_tasks.get("caption_extract"),
        skipped_when_empty=True,
        parse_resource_func=parse_resource_func,
    )
    document_segments, document_failures = _parse_resource_group(
        session=session,
        resources=[item for item in valid_resources if item[0].resource_type in DOCUMENT_RESOURCE_TYPES],
        course_id=course_id,
        parse_run_id=parse_run_id,
        step_task=step_tasks.get("document_parse"),
        skipped_when_empty=True,
        parse_resource_func=parse_resource_func,
    )
    parsed_segments.extend(caption_segments)
    parsed_segments.extend(document_segments)
    parse_failures.extend(caption_failures)
    parse_failures.extend(document_failures)
    summary["issues"].extend(parse_failures)
    summary["segmentCount"] = len(parsed_segments)

    schema_invalid_failure = _failure_with_code(parse_failures, "parse.schema_invalid")
    if schema_invalid_failure is not None:
        error_message = _failure_message(
            schema_invalid_failure,
            default="Parser returned schema-invalid normalized_document.",
        )
        if _failure_with_code(caption_failures, "parse.schema_invalid") is not None:
            _finish_step(
                step_tasks.get("caption_extract"),
                status="failed",
                progress_pct=100,
                error_code="parse.schema_invalid",
                error_message=error_message,
            )
        if _failure_with_code(document_failures, "parse.schema_invalid") is not None:
            _finish_step(
                step_tasks.get("document_parse"),
                status="failed",
                progress_pct=100,
                error_code="parse.schema_invalid",
                error_message=error_message,
            )
        _mark_resources_failed_for_schema_invalid(
            resources=[resource for resource, _path in valid_resources],
            parse_run_id=parse_run_id,
            error_message=error_message,
        )
        _discard_parse_run_artifacts(session=session, parse_run_id=parse_run_id)
        summary["segmentCount"] = 0
        summary["vectorDocumentCount"] = 0
        _finish_step(
            step_tasks.get("knowledge_extract"),
            status="failed",
            progress_pct=100,
            error_code="parse.schema_invalid",
            error_message=error_message,
        )
        _finish_step(
            step_tasks.get("vectorize"),
            status="failed",
            progress_pct=100,
            error_code="parse.schema_invalid",
            error_message="Vectorization was skipped because parser output failed schema validation.",
        )
        return _finish_pipeline(
            session=session,
            course=course,
            parse_run=parse_run,
            root_task=root_task,
            status="failed",
            summary=summary,
            error_code="parse.schema_invalid",
            error_message=error_message,
        )

    if parsed_segments:
        _finish_step(
            step_tasks.get("knowledge_extract"),
            status="succeeded",
            progress_pct=100,
            result_json={"mode": "caption_timeline_ready" if caption_segments else "document_fallback", "segmentCount": len(parsed_segments)},
        )
    else:
        error_code = _first_failure_code(parse_failures, default="parse.segment_empty")
        error_message = _first_failure_message(parse_failures, default="Parsing produced no active segment.")
        _finish_step(
            step_tasks.get("knowledge_extract"),
            status="failed",
            progress_pct=100,
            error_code=error_code,
            error_message=error_message,
        )
        return _finish_pipeline(
            session=session,
            course=course,
            parse_run=parse_run,
            root_task=root_task,
            status="failed",
            summary=summary,
            error_code=error_code,
            error_message=error_message,
        )

    vector_status, vector_count, vector_issue = _vectorize_segments(
        session=session,
        segments=parsed_segments,
        step_task=step_tasks.get("vectorize"),
        embedding_client_factory=embedding_client_factory,
    )
    summary["vectorDocumentCount"] = vector_count
    if vector_issue is not None:
        summary["issues"].append(vector_issue)

    final_status = "succeeded"
    if parse_failures or invalid_count or vector_status != "succeeded":
        final_status = "partial_success"
    return _finish_pipeline(
        session=session,
        course=course,
        parse_run=parse_run,
        root_task=root_task,
        status=final_status,
        summary=summary,
    )


def _parse_resource_group(
    *,
    session: Session,
    resources: list[tuple[CourseResource, Path]],
    course_id: int,
    parse_run_id: int,
    step_task: AsyncTask | None,
    skipped_when_empty: bool,
    parse_resource_func: Callable[[str, str | Path], Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not resources:
        if skipped_when_empty:
            _finish_step(step_task, status="skipped", progress_pct=100)
        return [], []

    _set_task_running(step_task, progress_pct=50, started_at=utcnow())
    session.commit()
    created_segments: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for resource, path in resources:
        try:
            result = parse_resource_func(resource.resource_type, path)
        except Exception as exc:
            resource.processing_status = "failed"
            resource.last_error = str(exc)
            failures.append({"code": "parse.exception", "resourceId": resource.id, "message": str(exc)})
            continue

        if getattr(result, "status", None) != "succeeded":
            issues = [_issue_dict(issue) for issue in getattr(result, "issues", [])]
            resource.processing_status = "failed"
            resource.last_error = issues[0]["message"] if issues else "Parser returned failed status."
            failures.append(
                {
                    "code": issues[0]["code"] if issues else "parse.failed",
                    "resourceId": resource.id,
                    "issues": issues,
                }
            )
            continue

        document = getattr(result, "normalized_document", None) or {}
        schema_issues = _normalized_document_schema_issues(document, expected_resource_type=resource.resource_type)
        if schema_issues:
            message = schema_issues[0]["message"]
            resource.processing_status = "failed"
            resource.last_error = f"schema invalid: {message}"
            failures.append(
                {
                    "code": "parse.schema_invalid",
                    "resourceId": resource.id,
                    "message": message,
                    "issues": schema_issues,
                }
            )
            continue

        raw_segments = document.get("segments") or []
        if not isinstance(raw_segments, list) or not raw_segments:
            resource.processing_status = "failed"
            resource.last_error = "Parser returned no segment."
            failures.append({"code": "parse.segment_empty", "resourceId": resource.id})
            continue

        resource.processing_status = "succeeded"
        resource.last_error = None
        resource.last_parse_run_id = parse_run_id
        for index, raw_segment in enumerate(raw_segments, start=len(created_segments) + 1):
            if not isinstance(raw_segment, dict):
                continue
            row = CourseSegment(
                course_id=course_id,
                resource_id=resource.id,
                parse_run_id=parse_run_id,
                segment_type=str(_payload_value(raw_segment, "segmentType", "segment_type")),
                title=_payload_value(raw_segment, "title"),
                section_path=_payload_value(raw_segment, "sectionPath", "section_path", default=[]),
                text_content=str(_payload_value(raw_segment, "textContent", "text_content", default="")),
                plain_text=str(
                    _payload_value(
                        raw_segment,
                        "plainText",
                        "plain_text",
                        "textContent",
                        "text_content",
                        default="",
                    )
                ),
                start_sec=_payload_value(raw_segment, "startSec", "start_sec"),
                end_sec=_payload_value(raw_segment, "endSec", "end_sec"),
                page_no=_payload_value(raw_segment, "pageNo", "page_no"),
                slide_no=_payload_value(raw_segment, "slideNo", "slide_no"),
                image_key=_payload_value(raw_segment, "imageKey", "image_key"),
                formula_text=_payload_value(raw_segment, "formulaText", "formula_text"),
                bbox_json=_payload_value(raw_segment, "bboxJson", "bbox_json"),
                order_no=int(_payload_value(raw_segment, "orderNo", "order_no", default=index)),
                token_count=int(_payload_value(raw_segment, "tokenCount", "token_count", default=0)),
                is_active=bool(_payload_value(raw_segment, "isActive", "is_active", default=True)),
            )
            session.add(row)
            session.flush()
            created_segments.append(_segment_dict(row, resource_type=resource.resource_type))

    if created_segments and failures:
        status = "partial_success"
    elif created_segments:
        status = "succeeded"
    else:
        status = "failed"
    _finish_step(
        step_task,
        status=status,
        progress_pct=100,
        result_json={"segmentCount": len(created_segments)} if created_segments else None,
        error_code=_first_failure_code(failures, default="parse.failed") if status == "failed" else None,
        error_message=_first_failure_message(failures, default="No resource in this step parsed successfully.")
        if status == "failed"
        else None,
    )
    session.commit()
    return created_segments, failures


def _vectorize_segments(
    *,
    session: Session,
    segments: list[dict[str, Any]],
    step_task: AsyncTask | None,
    embedding_client_factory: Callable[[], Any],
) -> tuple[str, int, dict[str, Any] | None]:
    inputs = build_vector_document_inputs(segments=segments)
    if not inputs:
        _finish_step(
            step_task,
            status="failed",
            progress_pct=100,
            error_code="vector.no_input",
            error_message="No vectorizable segment input was produced.",
        )
        session.commit()
        return "failed", 0, {"code": "vector.no_input"}

    client = embedding_client_factory()
    if client is None:
        _finish_step(
            step_task,
            status="failed",
            progress_pct=100,
            error_code="embedding.not_configured",
            error_message="Embedding client is not configured; vector documents were not created.",
        )
        session.commit()
        return "failed", 0, {"code": "embedding.not_configured"}

    _set_task_running(step_task, progress_pct=50, started_at=utcnow())
    session.commit()
    try:
        embeddings = client.embed_texts([item.content_text for item in inputs])
    except Exception as exc:
        _finish_step(
            step_task,
            status="failed",
            progress_pct=100,
            error_code="embedding.failed",
            error_message=str(exc),
        )
        session.commit()
        return "failed", 0, {"code": "embedding.failed", "message": str(exc)}
    if len(embeddings) != len(inputs):
        _finish_step(
            step_task,
            status="failed",
            progress_pct=100,
            error_code="embedding.count_mismatch",
            error_message="Embedding provider returned a different vector count.",
        )
        session.commit()
        return "failed", 0, {"code": "embedding.count_mismatch"}

    for item, embedding in zip(inputs, embeddings, strict=True):
        session.add(
            VectorDocument(
                course_id=int(item.course_id or 0),
                parse_run_id=item.parse_run_id,
                handout_version_id=item.handout_version_id,
                owner_type=item.owner_type,
                owner_id=int(item.owner_id),
                resource_id=item.resource_id,
                content_text=item.content_text,
                metadata_json=item.metadata_json,
                embedding=embedding,
            )
        )
    _finish_step(
        step_task,
        status="succeeded",
        progress_pct=100,
        result_json={"vectorDocumentCount": len(inputs)},
    )
    session.commit()
    return "succeeded", len(inputs), None


def _finish_pipeline(
    *,
    session: Session,
    course: Course,
    parse_run: ParseRun,
    root_task: AsyncTask,
    status: str,
    summary: dict[str, Any],
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    now = utcnow()
    progress_pct = 100 if status in {"succeeded", "partial_success", "failed"} else root_task.progress_pct
    _finish_step(
        root_task,
        status=status,
        progress_pct=progress_pct,
        result_json=summary,
        error_code=error_code,
        error_message=error_message,
    )
    parse_run.status = status
    parse_run.progress_pct = progress_pct
    parse_run.summary_json = summary
    parse_run.finished_at = now
    course.pipeline_stage = "parse"
    course.pipeline_status = status
    if status in {"succeeded", "partial_success"}:
        course.lifecycle_status = "inquiry_ready"
        course.active_parse_run_id = parse_run.id
        active_handout = (
            session.get(HandoutVersion, course.active_handout_version_id)
            if course.active_handout_version_id is not None
            else None
        )
        if active_handout is not None and active_handout.source_parse_run_id != parse_run.id:
            course.active_handout_version_id = None
    course.updated_at = now
    session.commit()
    return {"taskId": root_task.id, "courseId": course.id, "parseRunId": parse_run.id, "status": status, **summary}


def _should_return_existing_pipeline_result(*, root_task: AsyncTask, parse_run: ParseRun) -> bool:
    root_status = str(root_task.status or "")
    parse_run_status = str(parse_run.status or "")
    if root_status in PIPELINE_TERMINAL_STATUSES:
        return True
    return parse_run_status in PIPELINE_SUCCESS_STATUSES


def _existing_pipeline_result(
    *,
    session: Session,
    root_task: AsyncTask,
    parse_run: ParseRun,
    course: Course,
) -> dict[str, Any]:
    status = str(parse_run.status if parse_run.status in PIPELINE_TERMINAL_STATUSES else root_task.status)
    summary = (
        _coerce_pipeline_summary(parse_run.summary_json)
        or _coerce_pipeline_summary(root_task.result_json)
        or _existing_artifact_summary(session=session, course_id=course.id, parse_run_id=parse_run.id)
    )
    return {"taskId": root_task.id, "courseId": course.id, "parseRunId": parse_run.id, "status": status, **summary}


def _coerce_pipeline_summary(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    summary = dict(payload)
    summary.setdefault("resourceCount", 0)
    summary.setdefault("segmentCount", 0)
    summary.setdefault("vectorDocumentCount", 0)
    issues = summary.get("issues")
    summary["issues"] = issues if isinstance(issues, list) else []
    return summary


def _existing_artifact_summary(*, session: Session, course_id: int, parse_run_id: int) -> dict[str, Any]:
    resource_count = len(
        session.scalars(select(CourseResource.id).where(CourseResource.course_id == course_id)).all()
    )
    segment_count = len(
        session.scalars(select(CourseSegment.id).where(CourseSegment.parse_run_id == parse_run_id)).all()
    )
    vector_count = len(
        session.scalars(select(VectorDocument.id).where(VectorDocument.parse_run_id == parse_run_id)).all()
    )
    return {
        "resourceCount": resource_count,
        "segmentCount": segment_count,
        "vectorDocumentCount": vector_count,
        "issues": [],
    }


def _discard_parse_run_artifacts(*, session: Session, parse_run_id: int) -> None:
    session.execute(
        delete(VectorDocument).where(
            VectorDocument.parse_run_id == parse_run_id,
            VectorDocument.owner_type == "segment",
        )
    )
    session.execute(delete(CourseSegment).where(CourseSegment.parse_run_id == parse_run_id))
    session.flush()


def _mark_resources_failed_for_schema_invalid(
    *,
    resources: list[CourseResource],
    parse_run_id: int,
    error_message: str,
) -> None:
    for resource in resources:
        resource.processing_status = "failed"
        resource.last_error = f"schema invalid: {error_message}"
        if resource.last_parse_run_id == parse_run_id:
            resource.last_parse_run_id = None


def _validate_resources(
    *,
    resources: list[CourseResource],
    base_dir: Path,
    object_storage: ObjectStorage | None,
) -> list[tuple[CourseResource, Path]]:
    valid: list[tuple[CourseResource, Path]] = []
    for resource in resources:
        if resource.resource_type not in DOCUMENT_RESOURCE_TYPES | VIDEO_RESOURCE_TYPES:
            resource.validation_status = "failed"
            resource.last_error = f"Unsupported resource type: {resource.resource_type}"
            continue
        path = _resolve_object_key(resource.object_key, base_dir=base_dir, object_storage=object_storage)
        if path is None:
            resource.validation_status = "failed"
            resource.last_error = f"Resource file not found: {resource.object_key}"
            continue
        resource.validation_status = "passed"
        resource.last_error = None
        valid.append((resource, path))
    return valid


def _resolve_object_key(object_key: str, *, base_dir: Path, object_storage: ObjectStorage | None) -> Path | None:
    raw = object_key.removeprefix("file://")
    path = Path(raw)
    candidates = [path] if path.is_absolute() else []
    storage_root = os.getenv("KNOWLINK_LOCAL_STORAGE_ROOT", "").strip()
    if storage_root and not path.is_absolute():
        candidates.append(Path(storage_root) / path)
    if not path.is_absolute():
        candidates.extend([base_dir / path, path])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if object_storage is not None and _is_downloadable_raw_object_key(object_key):
        return _download_object_to_worker_cache(object_key, object_storage=object_storage)
    return None


def _download_object_to_worker_cache(object_key: str, *, object_storage: ObjectStorage) -> Path | None:
    cache_path = _worker_cache_path(object_key)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    download_to_file = getattr(object_storage, "download_object_to_file", None)
    if callable(download_to_file):
        try:
            download_to_file(object_key, cache_path)
        except ObjectStorageError:
            return None
        return cache_path

    try:
        content = object_storage.read_object_bytes(object_key)
    except ObjectStorageError:
        return None

    cache_path.write_bytes(content)
    return cache_path


def _worker_cache_path(object_key: str) -> Path:
    configured_dir = os.getenv("KNOWLINK_WORKER_CACHE_DIR", "").strip()
    cache_dir = Path(configured_dir) if configured_dir else Path(tempfile.gettempdir()) / "knowlink-worker-cache"
    suffix = Path(object_key.rsplit("/", 1)[-1]).suffix
    digest = hashlib.sha256(object_key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}{suffix}"


def _is_downloadable_raw_object_key(object_key: str) -> bool:
    if not object_key.startswith("raw/") or object_key.startswith("/") or "\\" in object_key:
        return False
    return not any(segment in {"", ".", ".."} for segment in object_key.split("/"))


def _step_tasks(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int,
    root_task_id: int,
) -> dict[str, AsyncTask]:
    tasks = session.scalars(
        select(AsyncTask)
        .where(
            AsyncTask.course_id == course_id,
            AsyncTask.parse_run_id == parse_run_id,
            AsyncTask.parent_task_id == root_task_id,
            AsyncTask.step_code.is_not(None),
        )
        .order_by(AsyncTask.id.asc())
    ).all()
    return {str(task.step_code): task for task in tasks if task.step_code in STEP_CODES}


def _set_task_running(task: AsyncTask | None, *, progress_pct: int, started_at: Any) -> None:
    if task is None:
        return
    task.status = "running"
    task.progress_pct = progress_pct
    task.started_at = task.started_at or started_at
    task.finished_at = None
    task.error_code = None
    task.error_message = None


def _finish_step(
    task: AsyncTask | None,
    *,
    status: str,
    progress_pct: int,
    result_json: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if task is None:
        return
    task.status = status
    task.progress_pct = progress_pct
    task.result_json = result_json
    task.error_code = error_code
    task.error_message = error_message
    if status in {"succeeded", "failed", "skipped", "partial_success"}:
        task.finished_at = utcnow()


def _segment_dict(segment: CourseSegment, *, resource_type: str) -> dict[str, Any]:
    return {
        "segmentId": segment.id,
        "courseId": segment.course_id,
        "resourceId": segment.resource_id,
        "parseRunId": segment.parse_run_id,
        "resourceType": resource_type,
        "segmentType": segment.segment_type,
        "title": segment.title,
        "sectionPath": segment.section_path or [],
        "textContent": segment.text_content,
        "plainText": segment.plain_text,
        "startSec": segment.start_sec,
        "endSec": segment.end_sec,
        "pageNo": segment.page_no,
        "slideNo": segment.slide_no,
        "imageKey": segment.image_key,
        "formulaText": segment.formula_text,
        "bboxJson": segment.bbox_json,
        "orderNo": segment.order_no,
        "tokenCount": segment.token_count,
        "isActive": segment.is_active,
    }


def _normalized_document_schema_issues(document: Any, *, expected_resource_type: str) -> list[dict[str, Any]]:
    errors = sorted(_normalized_document_validator().iter_errors(document), key=lambda item: list(item.absolute_path))
    issues = [
        {
            "code": "parse.schema_invalid",
            "path": _json_path(error.absolute_path),
            "message": error.message,
        }
        for error in errors
    ]
    if isinstance(document, Mapping):
        actual_resource_type = document.get("resourceType")
        if isinstance(actual_resource_type, str) and actual_resource_type != expected_resource_type:
            issues.append(
                {
                    "code": "parse.schema_invalid",
                    "path": "$.resourceType",
                    "message": f"resourceType {actual_resource_type!r} does not match resource type {expected_resource_type!r}",
                }
            )
    return issues


@lru_cache(maxsize=1)
def _normalized_document_validator() -> jsonschema.Draft202012Validator:
    schema_text = (
        importlib_resources.files("schemas.parse")
        .joinpath("normalized_document.schema.json")
        .read_text(encoding="utf-8")
    )
    schema = json.loads(schema_text)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _first_failure_code(failures: list[dict[str, Any]], *, default: str) -> str:
    for failure in failures:
        code = failure.get("code")
        if code:
            return str(code)
    return default


def _failure_with_code(failures: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    for failure in failures:
        if failure.get("code") == code:
            return failure
    return None


def _failure_message(failure: dict[str, Any], *, default: str) -> str:
    message = failure.get("message")
    if message:
        return str(message)
    issues = failure.get("issues")
    if isinstance(issues, list) and issues:
        first_issue = issues[0]
        if isinstance(first_issue, Mapping) and first_issue.get("message"):
            return str(first_issue["message"])
    return default


def _first_failure_message(failures: list[dict[str, Any]], *, default: str) -> str:
    for failure in failures:
        message = _failure_message(failure, default="")
        if message:
            return message
    return default


def _required_int(payload: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            break
    raise ParsePipelineInputError(f"parse pipeline message missing integer field: {keys[0]}")


def _require_model(session: Session, model: type[Any], model_id: int, code: str) -> Any:
    row = session.get(model, model_id)
    if row is None:
        raise ParsePipelineInputError(f"{code}: {model_id}")
    return row


def _validate_message_consistency(*, root_task: AsyncTask, parse_run: ParseRun, course: Course) -> None:
    if root_task.course_id != course.id or parse_run.course_id != course.id or root_task.parse_run_id != parse_run.id:
        raise ParsePipelineInputError("parse pipeline message does not match task/course/parse_run ownership")


def _payload_value(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _issue_dict(issue: Any) -> dict[str, Any]:
    if hasattr(issue, "to_dict"):
        return issue.to_dict()
    if isinstance(issue, dict):
        return issue
    return {"code": "parse.issue", "message": str(issue)}
