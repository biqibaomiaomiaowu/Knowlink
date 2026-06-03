from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from server.ai.embedding import get_configured_embedding_client
from server.ai.handout_block import generate_handout_block
from server.ai.vector_projection import build_vector_document_inputs
from server.infra.db.base import utcnow
from server.infra.db.models import AsyncTask, Course, CourseSegment, HandoutBlock, HandoutVersion, VectorDocument
from server.infra.db.session import create_session
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks.vector_backfill import build_search_text


class HandoutTaskInputError(ValueError):
    pass


def run_handout_generate(
    message: Mapping[str, Any],
    *,
    session_factory: Callable[[], Session] = create_session,
) -> dict[str, Any]:
    task_id = _required_int(message, "taskId", "task_id")
    course_id = _required_int(message, "courseId", "course_id")
    handout_version_id = _required_int(message, "handoutVersionId", "handout_version_id")
    source_parse_run_id = _required_int(message, "sourceParseRunId", "source_parse_run_id")

    session = session_factory()
    try:
        return _run_handout_generate_with_session(
            session=session,
            task_id=task_id,
            course_id=course_id,
            handout_version_id=handout_version_id,
            source_parse_run_id=source_parse_run_id,
        )
    finally:
        session.close()


def run_handout_block_generate(
    message: Mapping[str, Any],
    *,
    session_factory: Callable[[], Session] = create_session,
    generate_block_func: Callable[..., dict[str, Any]] = generate_handout_block,
    embedding_client_factory: Callable[[], Any] | None = get_configured_embedding_client,
) -> dict[str, Any]:
    task_id = _required_int(message, "taskId", "task_id")
    course_id = _required_int(message, "courseId", "course_id")
    handout_version_id = _required_int(message, "handoutVersionId", "handout_version_id")
    handout_block_id = _required_int(message, "handoutBlockId", "handout_block_id")
    source_parse_run_id = _required_int(message, "sourceParseRunId", "source_parse_run_id")

    session = session_factory()
    try:
        return _run_handout_block_generate_with_session(
            session=session,
            task_id=task_id,
            course_id=course_id,
            handout_version_id=handout_version_id,
            handout_block_id=handout_block_id,
            source_parse_run_id=source_parse_run_id,
            generate_block_func=generate_block_func,
            embedding_client_factory=embedding_client_factory,
        )
    finally:
        session.close()


def _run_handout_generate_with_session(
    *,
    session: Session,
    task_id: int,
    course_id: int,
    handout_version_id: int,
    source_parse_run_id: int,
) -> dict[str, Any]:
    task = _require_model(session, AsyncTask, task_id, "async_task.not_found")
    version = _require_model(session, HandoutVersion, handout_version_id, "handout.not_found")
    course = _require_model(session, Course, course_id, "course.not_found")
    _validate_root_handout_task(
        task=task,
        version=version,
        course=course,
        source_parse_run_id=source_parse_run_id,
    )

    now = utcnow()
    task.status = "running"
    task.progress_pct = 50
    task.started_at = task.started_at or now
    task.error_code = None
    task.error_message = None
    course.pipeline_stage = "handout"
    course.pipeline_status = "running"
    course.updated_at = now
    session.commit()

    finished_at = utcnow()
    task.status = "succeeded"
    task.progress_pct = 100
    task.result_json = {
        "courseId": course.id,
        "handoutVersionId": version.id,
        "sourceParseRunId": version.source_parse_run_id,
        "status": version.status,
        "outlineStatus": version.outline_status,
        "totalBlocks": version.total_blocks,
        "readyBlocks": version.ready_blocks,
        "pendingBlocks": version.pending_blocks,
    }
    task.finished_at = finished_at
    course.pipeline_stage = "handout"
    course.pipeline_status = "succeeded"
    course.updated_at = finished_at
    session.commit()

    return {
        "taskId": task.id,
        "courseId": course.id,
        "handoutVersionId": version.id,
        "sourceParseRunId": version.source_parse_run_id,
        "status": version.status,
        "outlineStatus": version.outline_status,
        "totalBlocks": version.total_blocks,
        "readyBlocks": version.ready_blocks,
        "pendingBlocks": version.pending_blocks,
    }


def _run_handout_block_generate_with_session(
    *,
    session: Session,
    task_id: int,
    course_id: int,
    handout_version_id: int,
    handout_block_id: int,
    source_parse_run_id: int,
    generate_block_func: Callable[..., dict[str, Any]],
    embedding_client_factory: Callable[[], Any] | None,
) -> dict[str, Any]:
    task = _require_model(session, AsyncTask, task_id, "async_task.not_found")
    course = _require_model(session, Course, course_id, "course.not_found")
    version = _require_model(session, HandoutVersion, handout_version_id, "handout.not_found")
    block = _require_model(session, HandoutBlock, handout_block_id, "handout_block.not_found")
    _validate_block_task(
        task=task,
        course=course,
        version=version,
        block=block,
        source_parse_run_id=source_parse_run_id,
    )
    if task.status in {"succeeded", "failed", "canceled", "skipped"}:
        return _terminal_block_task_result(task=task, course=course, version=version, block=block)
    if block.status == "ready":
        task.status = "succeeded"
        task.progress_pct = 100
        task.result_json = {
            "courseId": course.id,
            "handoutVersionId": version.id,
            "handoutBlockId": block.id,
            "status": "ready",
            "reason": "block_already_ready",
        }
        task.finished_at = task.finished_at or utcnow()
        session.commit()
        return _terminal_block_task_result(task=task, course=course, version=version, block=block)

    now = utcnow()
    task.status = "running"
    task.progress_pct = 50
    task.started_at = task.started_at or now
    task.error_code = None
    task.error_message = None
    block.status = "generating"
    course.pipeline_stage = "handout"
    course.pipeline_status = "running"
    course.updated_at = now
    session.commit()

    outline_item = _outline_item_from_block(block)
    segments = _segments_for_block_generation(
        session,
        course_id=course.id,
        parse_run_id=version.source_parse_run_id,
    )
    try:
        payload = generate_block_func(outline_item, segments, preferences={})
        saved = SqlAlchemyRuntimeRepository(session, user_id=course.user_id).save_handout_block_result(block.id, payload)
        if saved is None:
            raise HandoutTaskInputError("handout block result was rejected by repository")
        embedding_client = embedding_client_factory() if embedding_client_factory is not None else None
        _replace_handout_block_vector(session, saved, course=course, version=version, embedding_client=embedding_client)
    except Exception as exc:
        finished_at = utcnow()
        task.status = "failed"
        task.progress_pct = 100
        task.error_code = "handout_block.generate_failed"
        task.error_message = str(exc)
        task.finished_at = finished_at
        block.status = "failed"
        _refresh_handout_version_status(session=session, version=version)
        course.pipeline_stage = "handout"
        course.pipeline_status = "failed"
        course.last_error = str(exc)
        course.updated_at = finished_at
        session.commit()
        return {
            "taskId": task.id,
            "courseId": course.id,
            "handoutVersionId": version.id,
            "handoutBlockId": block.id,
            "status": "failed",
            "errorMessage": str(exc),
        }

    finished_at = utcnow()
    task.status = "succeeded"
    task.progress_pct = 100
    generation_metadata = _generation_metadata_from_payload(payload)
    task.result_json = {
        "courseId": course.id,
        "handoutVersionId": version.id,
        "handoutBlockId": block.id,
        "status": "ready",
    }
    if generation_metadata:
        task.result_json["generationMetadata"] = generation_metadata
    task.finished_at = finished_at
    course.pipeline_stage = "handout"
    course.pipeline_status = "succeeded"
    course.last_error = None
    course.updated_at = finished_at
    session.commit()
    result = {
        "taskId": task.id,
        "courseId": course.id,
        "handoutVersionId": version.id,
        "handoutBlockId": block.id,
        "status": "ready",
    }
    if generation_metadata:
        result["generationMetadata"] = generation_metadata
    return result


def _terminal_block_task_result(
    *,
    task: AsyncTask,
    course: Course,
    version: HandoutVersion,
    block: HandoutBlock,
) -> dict[str, Any]:
    return {
        "taskId": task.id,
        "courseId": course.id,
        "handoutVersionId": version.id,
        "handoutBlockId": block.id,
        "status": block.status if task.status == "succeeded" else task.status,
        "taskStatus": task.status,
    }


def _validate_root_handout_task(
    *,
    task: AsyncTask,
    version: HandoutVersion,
    course: Course,
    source_parse_run_id: int,
) -> None:
    if task.course_id != course.id or version.course_id != course.id:
        raise HandoutTaskInputError("handout task message does not match task/course/version ownership")
    if task.task_type != "handout_generate":
        raise HandoutTaskInputError(f"async task is not handout_generate: {task.task_type}")
    if task.target_type != "handout_version" or task.target_id != version.id:
        raise HandoutTaskInputError("handout task target does not match handout version")
    if course.active_handout_version_id != version.id:
        raise HandoutTaskInputError("handout task does not target the active handout version")
    if version.source_parse_run_id != source_parse_run_id:
        raise HandoutTaskInputError("handout task source parse run does not match handout version")
    if course.active_parse_run_id != version.source_parse_run_id:
        raise HandoutTaskInputError("handout task does not match the active parse run")
    if task.parse_run_id != source_parse_run_id:
        raise HandoutTaskInputError("handout task does not match source parse run")
    if version.status != "outline_ready" or version.outline_status != "ready":
        raise HandoutTaskInputError("handout root task only supports outline-ready versions")


def _validate_block_task(
    *,
    task: AsyncTask,
    course: Course,
    version: HandoutVersion,
    block: HandoutBlock,
    source_parse_run_id: int,
) -> None:
    if version.course_id != course.id or block.handout_version_id != version.id:
        raise HandoutTaskInputError("handout block task message does not match course/version/block ownership")
    if course.active_handout_version_id != version.id:
        raise HandoutTaskInputError("handout block task does not target the active handout version")
    if version.source_parse_run_id != source_parse_run_id:
        raise HandoutTaskInputError("handout block task source parse run does not match handout version")
    if course.active_parse_run_id != version.source_parse_run_id:
        raise HandoutTaskInputError("handout block task does not match the active parse run")
    if task.course_id != course.id or task.parse_run_id != source_parse_run_id:
        raise HandoutTaskInputError("handout block task does not match course/source parse run")
    if task.task_type != "handout_block_generate":
        raise HandoutTaskInputError(f"async task is not handout_block_generate: {task.task_type}")
    if task.target_type != "handout_block" or task.target_id != block.id:
        raise HandoutTaskInputError("handout block task target does not match block")


def _outline_item_from_block(block: HandoutBlock) -> dict[str, Any]:
    return {
        "outlineKey": block.outline_key,
        "title": block.title,
        "summary": block.summary,
        "startSec": block.start_sec,
        "endSec": block.end_sec,
        "sortNo": block.sort_no,
        "generationStatus": block.status,
        "sourceSegmentKeys": list(block.source_segment_keys_json or []),
    }


def _segments_for_block_generation(
    session: Session,
    *,
    course_id: int,
    parse_run_id: int | None,
) -> list[dict[str, Any]]:
    if parse_run_id is None:
        return []
    rows = session.scalars(
        select(CourseSegment)
        .where(
            CourseSegment.course_id == course_id,
            CourseSegment.parse_run_id == parse_run_id,
            CourseSegment.is_active.is_(True),
        )
        .order_by(CourseSegment.order_no.asc(), CourseSegment.id.asc())
    ).all()
    return [_segment_payload(row) for row in rows]


def _segment_payload(segment: CourseSegment) -> dict[str, Any]:
    return {
        "courseId": segment.course_id,
        "parseRunId": segment.parse_run_id,
        "resourceId": segment.resource_id,
        "segmentId": segment.id,
        "segmentKey": f"segment-{segment.id}",
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
    }


def _generation_metadata_from_payload(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    metadata = payload.get("generationMetadata") or payload.get("generation_metadata")
    if not isinstance(metadata, Mapping):
        return None
    source = metadata.get("source")
    reason = metadata.get("reason")
    if source not in {"model", "fallback"} or not isinstance(reason, str) or not reason.strip():
        return None
    return {"source": source, "reason": reason.strip()}


def _replace_handout_block_vector(
    session: Session,
    block: dict[str, Any],
    *,
    course: Course,
    version: HandoutVersion,
    embedding_client: Any | None = None,
) -> None:
    stored_block = session.get(HandoutBlock, int(block["blockId"]))
    if stored_block is not None and stored_block.handout_version_id == version.id:
        vector_block = {
            "courseId": course.id,
            "parseRunId": version.source_parse_run_id,
            "handoutVersionId": version.id,
            "handoutBlockId": stored_block.id,
            "blockId": stored_block.id,
            "outlineKey": stored_block.outline_key,
            "title": stored_block.title,
            "summary": stored_block.summary,
            "contentMd": stored_block.content_md,
            "sourceSegmentKeys": list(stored_block.source_segment_keys_json or []),
            "knowledgePoints": list(stored_block.knowledge_points_json or []),
            "citations": list(stored_block.citations_json or []),
        }
    else:
        vector_block = {
            **block,
            "courseId": course.id,
            "parseRunId": version.source_parse_run_id,
            "handoutVersionId": version.id,
            "handoutBlockId": block["blockId"],
        }
    inputs = build_vector_document_inputs(handout_block=vector_block)
    embeddings: list[list[float]] | None = None
    embedding_error: str | None = None
    if inputs and embedding_client is not None:
        try:
            embeddings = embedding_client.embed_texts([item.content_text for item in inputs])
            if len(embeddings) != len(inputs):
                embeddings = None
                embedding_error = "Embedding provider returned a different vector count."
            else:
                for embedding in embeddings:
                    if len(embedding) != VectorDocument.EMBEDDING_DIM:
                        embeddings = None
                        embedding_error = (
                            f"Embedding provider returned vector dimension {len(embedding)}, "
                            f"expected {VectorDocument.EMBEDDING_DIM}."
                        )
                        break
        except Exception as exc:
            embeddings = None
            embedding_error = str(exc)
    session.execute(
        delete(VectorDocument).where(
            VectorDocument.course_id == course.id,
            VectorDocument.parse_run_id == version.source_parse_run_id,
            VectorDocument.handout_version_id == version.id,
            VectorDocument.owner_type == "handout_block",
            VectorDocument.owner_id == int(block["blockId"]),
        )
    )
    embedding_model = _embedding_model_name(embedding_client) if embedding_client is not None and embeddings is not None else None
    for index, item in enumerate(inputs):
        embedding_vector = list(embeddings[index]) if embeddings is not None else None
        session.add(
            VectorDocument(
                course_id=int(item.course_id or course.id),
                parse_run_id=item.parse_run_id,
                handout_version_id=item.handout_version_id,
                owner_type=item.owner_type,
                owner_id=int(item.owner_id),
                resource_id=item.resource_id,
                content_text=item.content_text,
                metadata_json=item.metadata_json,
                embedding=embedding_vector,
                embedding_vector=embedding_vector,
                embedding_model=embedding_model,
                embedding_dim=VectorDocument.EMBEDDING_DIM if embedding_vector is not None else None,
                embedding_status="ready"
                if embedding_vector is not None
                else ("failed" if embedding_client is not None else "pending"),
                embedding_error=None if embedding_vector is not None or embedding_client is None else embedding_error,
                search_text=build_search_text(item.content_text, item.metadata_json),
            )
        )


def _refresh_handout_version_status(*, session: Session, version: HandoutVersion) -> None:
    blocks = session.scalars(
        select(HandoutBlock).where(HandoutBlock.handout_version_id == version.id)
    ).all()
    ready_blocks = sum(1 for item in blocks if item.status == "ready")
    pending_blocks = sum(1 for item in blocks if item.status in {"pending", "generating"})
    failed_blocks = sum(1 for item in blocks if item.status == "failed")
    version.ready_blocks = ready_blocks
    version.pending_blocks = pending_blocks
    if blocks and ready_blocks == len(blocks):
        version.status = "ready"
    elif failed_blocks and pending_blocks == 0:
        version.status = "partial_success" if ready_blocks else "failed"
    elif version.outline_status == "ready":
        version.status = "outline_ready"


def _required_int(payload: Mapping[str, Any], *keys: str) -> int:
    parsed = _optional_int(payload, *keys)
    if parsed is None:
        raise HandoutTaskInputError(f"handout task message missing integer field: {keys[0]}")
    return parsed


def _optional_int(payload: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _embedding_model_name(client: Any) -> str:
    for attr in ("model", "model_name"):
        value = getattr(client, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


def _require_model(session: Session, model: type[Any], model_id: int, code: str) -> Any:
    row = session.get(model, model_id)
    if row is None:
        raise HandoutTaskInputError(f"{code}: {model_id}")
    return row
