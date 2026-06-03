from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class EvidenceTier(StrEnum):
    ORIGINAL_EVIDENCE = "original_evidence"
    HANDOUT_CONTEXT = "handout_context"
    COURSE_PRIOR = "course_prior"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class QaScope:
    course_id: int | None = None
    active_parse_run_id: int | None = None
    active_handout_version_id: int | None = None
    current_handout_block_id: int | str | None = None
    current_outline_key: str | None = None
    current_sort_no: int | None = None


QaCandidateSource = Literal[
    "current_block_ref",
    "current_block_source_segment",
    "knowledge_point_evidence",
    "adjacent_block",
    "course_document_segment",
    "course_wide_segment_semantic",
    "course_wide_segment_lexical",
    "course_wide_segment_hybrid",
]


@dataclass(frozen=True)
class QaEvidenceCandidate:
    candidate_key: str
    source: QaCandidateSource
    rank: int
    content_text: str
    resource_id: int
    ref_label: str
    locator: dict[str, Any]
    segment_id: int | None = None
    segment_key: str | None = None
    course_id: int | None = None
    parse_run_id: int | None = None
    handout_version_id: int | None = None
    handout_block_id: int | str | None = None
    metadata_json: dict[str, Any] | None = None
    score: float | None = None

    def to_qa_citation(self) -> dict[str, Any]:
        return {"resourceId": self.resource_id, "refLabel": self.ref_label, **self.locator}


@dataclass(frozen=True)
class HandoutContextCandidate:
    rank: int
    content_text: str
    handout_block_id: int | str | None
    outline_key: str | None
    title: str
    source: Literal["current_handout_block", "adjacent_handout_block", "course_wide_handout_block"]
    score: float | None = None
    matched_by: str | None = None
    course_id: int | None = None
    handout_version_id: int | None = None
    sort_no: int | None = None
    metadata_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class VectorSearchHit:
    identity_key: str
    score: float
    text: str
    segment_key: str | None = None
    resource_id: int | None = None
    owner_type: str = "segment"
    handout_block_id: int | str | None = None
    segment_id: int | None = None
    course_id: int | None = None
    parse_run_id: int | None = None
    handout_version_id: int | None = None
    metadata_json: dict[str, Any] | None = None
    locator: dict[str, Any] | None = None
    distance: float | None = None
    rank: int | None = None


@dataclass(frozen=True)
class LexicalSearchHit:
    identity_key: str
    score: float
    text: str
    segment_key: str | None = None
    resource_id: int | None = None
    owner_type: str = "segment"
    handout_block_id: int | str | None = None
    segment_id: int | None = None
    course_id: int | None = None
    parse_run_id: int | None = None
    handout_version_id: int | None = None
    metadata_json: dict[str, Any] | None = None
    locator: dict[str, Any] | None = None
    distance: float | None = None
    rank: int | None = None


@dataclass(frozen=True)
class FusedSearchHit:
    identity_key: str
    score: float
    text: str
    segment_key: str | None = None
    resource_id: int | None = None
    owner_type: str = "segment"
    handout_block_id: int | str | None = None
    segment_id: int | None = None
    course_id: int | None = None
    parse_run_id: int | None = None
    handout_version_id: int | None = None
    metadata_json: dict[str, Any] | None = None
    locator: dict[str, Any] | None = None
    distance: float | None = None
    rank: int | None = None
    vector_rank: int | None = None
    lexical_rank: int | None = None
    vector_score: float | None = None
    lexical_score: float | None = None


@dataclass(frozen=True)
class RetrievalTrace:
    current_block_candidate_count: int = 0
    adjacent_block_candidate_count: int = 0
    course_document_candidate_count: int = 0
    handout_context_candidate_count: int = 0
    vector_hit_count: int = 0
    lexical_hit_count: int = 0
    fused_hit_count: int = 0
    original_evidence_count: int = 0
    handout_context_count: int = 0
    course_prior_count: int = 0
    out_of_scope_count: int = 0
    dropped_duplicate_count: int = 0
    dropped_scope_mismatch_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QaGenerationResult:
    response: dict[str, Any]
    refs: list[dict[str, Any]]
    candidate_count: int
    retrieval_trace: RetrievalTrace | None = None
