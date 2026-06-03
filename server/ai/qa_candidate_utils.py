from __future__ import annotations

from typing import Any, Mapping

from server.ai.qa_types import QaEvidenceCandidate


def locator_tuple(locator: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple((key, locator[key]) for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec") if key in locator)


def locator_key(locator: Mapping[str, Any]) -> str:
    return "-".join(f"{key}-{value}" for key, value in locator_tuple(locator))


def qa_candidate_identity(candidate: QaEvidenceCandidate) -> tuple[int, str, tuple[tuple[str, Any], ...]]:
    if candidate.segment_id is not None:
        segment_identity = f"id:{candidate.segment_id}"
    elif candidate.segment_key:
        segment_identity = f"key:{candidate.segment_key}"
    else:
        segment_identity = f"source:{candidate.source}:{candidate.rank}"
    return (candidate.resource_id, segment_identity, locator_tuple(candidate.locator))


def replace_candidate_rank(candidate: QaEvidenceCandidate, rank: int) -> QaEvidenceCandidate:
    return QaEvidenceCandidate(
        candidate_key=candidate.candidate_key,
        source=candidate.source,
        rank=rank,
        content_text=candidate.content_text,
        resource_id=candidate.resource_id,
        ref_label=candidate.ref_label,
        locator=candidate.locator,
        segment_id=candidate.segment_id,
        segment_key=candidate.segment_key,
        course_id=candidate.course_id,
        parse_run_id=candidate.parse_run_id,
        handout_version_id=candidate.handout_version_id,
        handout_block_id=candidate.handout_block_id,
        metadata_json=candidate.metadata_json,
        score=candidate.score,
    )
