from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.ai.embedding import get_configured_embedding_client
from server.ai.vector_projection import build_vector_document_inputs
from server.infra.db.base import utcnow
from server.infra.db.models import AsyncTask, Course, CourseResource, CourseSegment, ParseRun, VectorDocument
from server.infra.db.session import create_session
from server.parsers import parse_resource


DOCUMENT_RESOURCE_TYPES = {"pdf", "pptx", "docx"}
VIDEO_RESOURCE_TYPES = {"mp4", "srt"}
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
    base_dir: Path,
) -> dict[str, Any]:
    root_task = _require_model(session, AsyncTask, task_id, "async_task.not_found")
    parse_run = _require_model(session, ParseRun, parse_run_id, "parse_run.not_found")
    course = _require_model(session, Course, course_id, "course.not_found")
    _validate_message_consistency(root_task=root_task, parse_run=parse_run, course=course)
    step_tasks = _step_tasks(session, course_id=course_id, parse_run_id=parse_run_id, root_task_id=task_id)
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
    valid_resources = _validate_resources(resources=resources, base_dir=base_dir)
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

    if parsed_segments:
        _finish_step(
            step_tasks.get("knowledge_extract"),
            status="succeeded",
            progress_pct=100,
            result_json={"mode": "caption_timeline_ready" if caption_segments else "document_fallback", "segmentCount": len(parsed_segments)},
        )
    else:
        _finish_step(
            step_tasks.get("knowledge_extract"),
            status="failed",
            progress_pct=100,
            error_code="parse.segment_empty",
            error_message="Parsing produced no active segment.",
        )
        return _finish_pipeline(
            session=session,
            course=course,
            parse_run=parse_run,
            root_task=root_task,
            status="failed",
            summary=summary,
            error_code="parse.segment_empty",
            error_message="Parsing produced no active segment.",
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
        error_code="parse.failed" if status == "failed" else None,
        error_message="No resource in this step parsed successfully." if status == "failed" else None,
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
    course.updated_at = now
    session.commit()
    return {"taskId": root_task.id, "courseId": course.id, "parseRunId": parse_run.id, "status": status, **summary}


def _validate_resources(*, resources: list[CourseResource], base_dir: Path) -> list[tuple[CourseResource, Path]]:
    valid: list[tuple[CourseResource, Path]] = []
    for resource in resources:
        if resource.resource_type not in DOCUMENT_RESOURCE_TYPES | VIDEO_RESOURCE_TYPES:
            resource.validation_status = "failed"
            resource.last_error = f"Unsupported resource type: {resource.resource_type}"
            continue
        path = _resolve_object_key(resource.object_key, base_dir=base_dir)
        if path is None:
            resource.validation_status = "failed"
            resource.last_error = f"Resource file not found: {resource.object_key}"
            continue
        resource.validation_status = "passed"
        resource.last_error = None
        valid.append((resource, path))
    return valid


def _resolve_object_key(object_key: str, *, base_dir: Path) -> Path | None:
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
    return None


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
