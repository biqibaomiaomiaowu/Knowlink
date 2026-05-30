from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from server.ai.qa_types import (
    FusedSearchHit,
    LexicalSearchHit,
    QaEvidenceCandidate,
    VectorSearchHit,
)


DEFAULT_RRF_K = 60
DEFAULT_CURRENT_BLOCK_BOOST = 1.25
DEFAULT_ADJACENT_BLOCK_BOOST = 1.10


@dataclass(frozen=True)
class HandoutBlockHybridCandidate:
    owner_type: str
    rank: int
    content_text: str
    handout_block_id: int | str | None
    score: float
    citations: list[dict]
    refs: list[dict]
    text: str | None = None
    content: str | None = None
    source: str = "course_wide_handout_block_hybrid"
    matched_by: str | None = None
    course_id: int | None = None
    handout_version_id: int | None = None
    metadata_json: dict | None = None


def rrf_merge_hits(
    vector_hits: Iterable[VectorSearchHit],
    lexical_hits: Iterable[LexicalSearchHit],
    *,
    k: int = DEFAULT_RRF_K,
) -> list[FusedSearchHit]:
    fused_by_key: dict[str, FusedSearchHit] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        existing = fused_by_key.get(hit.identity_key)
        score = _rrf_score(rank, k)
        fused_by_key[hit.identity_key] = _merge_hit(
            existing,
            hit,
            score=score,
            vector_rank=rank,
            vector_score=hit.score,
        )

    for rank, hit in enumerate(lexical_hits, start=1):
        existing = fused_by_key.get(hit.identity_key)
        score = (existing.score if existing else 0.0) + _rrf_score(rank, k)
        fused_by_key[hit.identity_key] = _merge_hit(
            existing,
            hit,
            score=score,
            lexical_rank=rank,
            lexical_score=hit.score,
        )

    return sorted(
        fused_by_key.values(),
        key=lambda hit: (-hit.score, _best_rank(hit), hit.identity_key),
    )


def apply_current_block_boost(
    hits: Iterable[FusedSearchHit],
    *,
    current_handout_block_id: int | str | None,
    adjacent_handout_block_ids: Iterable[int | str] = (),
    current_boost: float = DEFAULT_CURRENT_BLOCK_BOOST,
    adjacent_boost: float = DEFAULT_ADJACENT_BLOCK_BOOST,
) -> list[FusedSearchHit]:
    adjacent_ids = set(adjacent_handout_block_ids)

    def boosted_score(hit: FusedSearchHit) -> float:
        if current_handout_block_id is not None and hit.handout_block_id == current_handout_block_id:
            return hit.score * current_boost
        if hit.handout_block_id in adjacent_ids:
            return hit.score * adjacent_boost
        return hit.score

    return sorted(
        hits,
        key=lambda hit: (-boosted_score(hit), _best_rank(hit), hit.identity_key),
    )


def build_hybrid_retrieval_candidates(
    vector_hits: Iterable[VectorSearchHit],
    lexical_hits: Iterable[LexicalSearchHit],
    *,
    current_handout_block_id: int | str | None = None,
    adjacent_handout_block_ids: Iterable[int | str] = (),
    max_candidates: int = 10,
) -> list[QaEvidenceCandidate | HandoutBlockHybridCandidate]:
    fused_hits = rrf_merge_hits(vector_hits, lexical_hits)
    boosted_hits = apply_current_block_boost(
        fused_hits,
        current_handout_block_id=current_handout_block_id,
        adjacent_handout_block_ids=adjacent_handout_block_ids,
    )

    candidates: list[QaEvidenceCandidate | HandoutBlockHybridCandidate] = []
    for rank, hit in enumerate(boosted_hits[:max_candidates], start=1):
        if hit.owner_type == "handout_block":
            candidates.append(_to_handout_candidate(hit, rank))
        else:
            candidates.append(_to_evidence_candidate(hit, rank))
    return candidates


def _rrf_score(rank: int, k: int) -> float:
    return 1.0 / (k + rank)


def _merge_hit(
    existing: FusedSearchHit | None,
    hit: VectorSearchHit | LexicalSearchHit,
    *,
    score: float,
    vector_rank: int | None = None,
    lexical_rank: int | None = None,
    vector_score: float | None = None,
    lexical_score: float | None = None,
) -> FusedSearchHit:
    return FusedSearchHit(
        identity_key=hit.identity_key,
        score=score,
        text=_coalesce(hit.text, existing.text if existing else None, ""),
        segment_key=_coalesce(hit.segment_key, existing.segment_key if existing else None),
        resource_id=_coalesce(hit.resource_id, existing.resource_id if existing else None),
        owner_type=_coalesce(hit.owner_type, existing.owner_type if existing else None, "segment"),
        handout_block_id=_coalesce(
            hit.handout_block_id,
            existing.handout_block_id if existing else None,
        ),
        segment_id=_coalesce(hit.segment_id, existing.segment_id if existing else None),
        course_id=_coalesce(hit.course_id, existing.course_id if existing else None),
        parse_run_id=_coalesce(hit.parse_run_id, existing.parse_run_id if existing else None),
        handout_version_id=_coalesce(
            hit.handout_version_id,
            existing.handout_version_id if existing else None,
        ),
        metadata_json=_coalesce(hit.metadata_json, existing.metadata_json if existing else None),
        locator=_coalesce(hit.locator, existing.locator if existing else None),
        distance=_coalesce(hit.distance, existing.distance if existing else None),
        rank=_coalesce(hit.rank, existing.rank if existing else None),
        vector_rank=_coalesce(vector_rank, existing.vector_rank if existing else None),
        lexical_rank=_coalesce(lexical_rank, existing.lexical_rank if existing else None),
        vector_score=_coalesce(vector_score, existing.vector_score if existing else None),
        lexical_score=_coalesce(lexical_score, existing.lexical_score if existing else None),
    )


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _best_rank(hit: FusedSearchHit) -> int:
    ranks = [rank for rank in (hit.vector_rank, hit.lexical_rank) if rank is not None]
    return min(ranks) if ranks else 0


def _to_evidence_candidate(hit: FusedSearchHit, rank: int) -> QaEvidenceCandidate:
    return QaEvidenceCandidate(
        candidate_key=hit.identity_key,
        source=_candidate_source(hit),
        rank=rank,
        content_text=hit.text,
        resource_id=hit.resource_id or 0,
        ref_label=hit.segment_key or hit.identity_key,
        locator=hit.locator or {},
        segment_id=hit.segment_id,
        segment_key=hit.segment_key,
        course_id=hit.course_id,
        parse_run_id=hit.parse_run_id,
        handout_version_id=hit.handout_version_id,
        handout_block_id=hit.handout_block_id,
        metadata_json=hit.metadata_json,
        score=hit.score,
    )


def _candidate_source(hit: FusedSearchHit):
    if hit.vector_rank is not None and hit.lexical_rank is not None:
        return "course_wide_segment_hybrid"
    if hit.vector_rank is not None:
        return "course_wide_segment_semantic"
    return "course_wide_segment_lexical"


def _to_handout_candidate(hit: FusedSearchHit, rank: int) -> HandoutBlockHybridCandidate:
    return HandoutBlockHybridCandidate(
        owner_type="handout_block",
        rank=rank,
        content_text=hit.text,
        handout_block_id=hit.handout_block_id,
        score=hit.score,
        citations=[],
        refs=[],
        text=hit.text,
        content=hit.text,
        matched_by=_matched_by(hit),
        course_id=hit.course_id,
        handout_version_id=hit.handout_version_id,
        metadata_json=hit.metadata_json,
    )


def _matched_by(hit: FusedSearchHit) -> str:
    if hit.vector_rank is not None and hit.lexical_rank is not None:
        return "hybrid"
    if hit.vector_rank is not None:
        return "semantic"
    return "lexical"
