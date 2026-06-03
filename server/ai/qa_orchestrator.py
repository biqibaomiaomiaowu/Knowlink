from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

from server.ai.core.errors import fallback_reason_for_error
from server.ai.qa_candidate_utils import qa_candidate_identity, replace_candidate_rank
from server.ai.qa_exact_retrieval import ExactEvidenceRetriever, qa_evidence_candidate_from_segment_payload
from server.ai.qa_pgvector_retrieval import HandoutBlockHybridCandidate, build_hybrid_retrieval_candidates
from server.ai.qa_policy import (
    QaAnswerClient,
    build_qa_message_refs,
    _fallback_course_prior_response,
    _fallback_handout_context_response,
    _fallback_qa_response,
    _normalize_unreferenced_qa_response,
    _out_of_scope_response,
    _course_scope_text,
    insufficient_evidence_response,
    normalize_qa_answer_with_refs,
)
from server.ai.qa_scope import (
    QaScopeGuard,
    active_ints,
    build_qa_scope,
    lexical_relevance_score,
    scope_matches_payload,
)
from server.ai.qa_types import HandoutContextCandidate, QaEvidenceCandidate, QaGenerationResult, QaScope, RetrievalTrace
from server.parsers.base import clean_text


EXPECTED_QUERY_EMBEDDING_DIM = 1536


class QaOrchestrator:
    def __init__(
        self,
        *,
        retrieval_repository: Any | None = None,
        embedding_client: Any | None = None,
        qa_answer_client: QaAnswerClient | None = None,
        answer_client: QaAnswerClient | None = None,
    ) -> None:
        self.retrieval_repository = retrieval_repository
        self.embedding_client = embedding_client
        self.answer_client = qa_answer_client if qa_answer_client is not None else answer_client
        self.exact_retriever = ExactEvidenceRetriever()

    def answer(self, question: str, context: Mapping[str, Any]) -> QaGenerationResult:
        scope = build_qa_scope(context)
        guard = QaScopeGuard(scope=scope, context=context)
        if guard.is_hard_security_out_of_scope(question):
            response = _hard_security_out_of_scope_response()
            return QaGenerationResult(response=response, refs=[], candidate_count=0)

        is_source_fact = guard.is_source_fact_intent(question)
        exact_candidates = _relevant_candidates(
            question,
            self.exact_retriever.retrieve(scope=scope, context=_exact_context(context)),
        )
        hybrid_original_candidates = self._hybrid_original_candidates(question, scope=scope, context=context)
        context_original_candidates = _course_wide_context_segment_candidates(context, scope=scope)
        original_candidates = _relevant_candidates(
            question,
            _dedupe_candidates([*exact_candidates, *hybrid_original_candidates, *context_original_candidates]),
        )
        if original_candidates:
            return self._answer_with_original_evidence(
                question,
                original_candidates,
                scope=scope,
                trace=RetrievalTrace(current_block_candidate_count=len(exact_candidates), original_evidence_count=len(exact_candidates)),
            )

        if is_source_fact:
            return QaGenerationResult(
                response=insufficient_evidence_response(
                    source="fallback",
                    reason="source_fact_without_original_evidence",
                ),
                refs=[],
                candidate_count=0,
            )

        if guard.is_ordinary_out_of_scope(question):
            return QaGenerationResult(response=_out_of_scope_response(), refs=[], candidate_count=0)

        handout_contexts = _relevant_handout_contexts(
            question,
            _dedupe_handout_contexts(
                [
                    *self._hybrid_handout_context_candidates(question, scope=scope, context=context),
                    *_handout_context_candidates(context, scope=scope),
                ]
            ),
            scope=scope,
        )
        if handout_contexts:
            response = self._answer_with_handout_context(question, handout_contexts[0])
            return QaGenerationResult(
                response=_force_unreferenced_response(response),
                refs=[],
                candidate_count=len(handout_contexts),
                retrieval_trace=RetrievalTrace(handout_context_candidate_count=len(handout_contexts), handout_context_count=1),
            )

        if guard.is_course_related(question):
            response = self._answer_with_course_prior(question, context)
            return QaGenerationResult(
                response=_force_unreferenced_response(response),
                refs=[],
                candidate_count=0,
                retrieval_trace=RetrievalTrace(course_prior_count=1),
            )

        return QaGenerationResult(
            response=_out_of_scope_response(),
            refs=[],
            candidate_count=0,
            retrieval_trace=RetrievalTrace(out_of_scope_count=1),
        )

    def _answer_with_original_evidence(
        self,
        question: str,
        candidates: Sequence[QaEvidenceCandidate],
        *,
        scope: QaScope,
        trace: RetrievalTrace,
    ) -> QaGenerationResult:
        if self.answer_client is not None:
            try:
                raw_payload = self.answer_client.generate_answer(question, list(candidates))
                answer = normalize_qa_answer_with_refs(
                    raw_payload,
                    candidates,
                    active_course_id=active_ints(scope)[0],
                    active_parse_run_id=active_ints(scope)[1],
                    active_handout_version_id=active_ints(scope)[2],
                )
                return QaGenerationResult(
                    response=answer.response,
                    refs=answer.refs,
                    candidate_count=len(candidates),
                    retrieval_trace=trace,
                )
            except Exception as exc:
                response = _fallback_qa_response(candidates, reason=fallback_reason_for_error(exc))
        else:
            response = _fallback_qa_response(candidates, reason="model_unavailable")

        refs = build_qa_message_refs(
            response,
            candidates,
            active_course_id=active_ints(scope)[0],
            active_parse_run_id=active_ints(scope)[1],
            active_handout_version_id=active_ints(scope)[2],
        )
        return QaGenerationResult(
            response=response,
            refs=refs,
            candidate_count=len(candidates),
            retrieval_trace=trace,
        )

    def _answer_with_handout_context(self, question: str, context: HandoutContextCandidate) -> dict[str, Any]:
        if self.answer_client is not None:
            try:
                return _normalize_unreferenced_qa_response(
                    self.answer_client.generate_unreferenced_answer(
                        question,
                        context_text=context.content_text,
                        evidence_tier="handout_context",
                    ),
                    evidence_tier="handout_context",
                    reason="handout_context_match",
                    handout_context=context,
                )
            except Exception as exc:
                return _fallback_handout_context_response(context, reason=fallback_reason_for_error(exc))
        return _fallback_handout_context_response(context, reason="handout_context_match")

    def _answer_with_course_prior(self, question: str, context: Mapping[str, Any]) -> dict[str, Any]:
        course_scope = context.get("courseScope") or context.get("course_scope") or {}
        if self.answer_client is not None:
            try:
                return _normalize_unreferenced_qa_response(
                    self.answer_client.generate_unreferenced_answer(
                        question,
                        context_text=_course_scope_text(course_scope),
                        evidence_tier="course_prior",
                        course_scope=course_scope,
                    ),
                    evidence_tier="course_prior",
                    reason="course_related_prior",
                )
            except Exception as exc:
                return _fallback_course_prior_response(question, reason=fallback_reason_for_error(exc))
        return _fallback_course_prior_response(question, reason="course_related_prior")

    def _hybrid_original_candidates(
        self,
        question: str,
        *,
        scope: QaScope,
        context: Mapping[str, Any],
    ) -> list[QaEvidenceCandidate]:
        if self.retrieval_repository is None:
            return []
        query_embedding = self._embed_question(question)
        vector_hits = (
            self.retrieval_repository.search_vector_segments(scope, query_embedding, 40)
            if query_embedding is not None and hasattr(self.retrieval_repository, "search_vector_segments")
            else []
        )
        lexical_hits = (
            self.retrieval_repository.search_lexical_segments(scope, question, 40)
            if hasattr(self.retrieval_repository, "search_lexical_segments")
            else []
        )
        candidates = build_hybrid_retrieval_candidates(
            vector_hits=vector_hits,
            lexical_hits=lexical_hits,
            current_handout_block_id=scope.current_handout_block_id,
            adjacent_handout_block_ids=_adjacent_handout_block_ids(context),
            max_candidates=10,
        )
        original_candidates = [
            _with_active_handout_version(candidate, scope)
            for candidate in candidates
            if isinstance(candidate, QaEvidenceCandidate) and _has_citable_locator(candidate)
        ]
        if original_candidates:
            return original_candidates

        return self._legacy_course_wide_repository_candidates(question, scope=scope)

    def _hybrid_handout_context_candidates(
        self,
        question: str,
        *,
        scope: QaScope,
        context: Mapping[str, Any],
    ) -> list[HandoutContextCandidate]:
        if self.retrieval_repository is None:
            return []
        query_embedding = self._embed_question(question)
        vector_hits = (
            self.retrieval_repository.search_vector_handout_blocks(scope, query_embedding, 40)
            if query_embedding is not None and hasattr(self.retrieval_repository, "search_vector_handout_blocks")
            else []
        )
        lexical_hits = (
            self.retrieval_repository.search_lexical_handout_blocks(scope, question, 40)
            if hasattr(self.retrieval_repository, "search_lexical_handout_blocks")
            else []
        )
        hybrid_candidates = build_hybrid_retrieval_candidates(
            vector_hits=vector_hits,
            lexical_hits=lexical_hits,
            current_handout_block_id=scope.current_handout_block_id,
            adjacent_handout_block_ids=_adjacent_handout_block_ids(context),
            max_candidates=6,
        )
        contexts: list[HandoutContextCandidate] = []
        for candidate in hybrid_candidates:
            if isinstance(candidate, HandoutBlockHybridCandidate):
                contexts.append(_handout_context_from_hybrid_candidate(candidate, scope=scope, rank=len(contexts) + 1))
        return contexts

    def _legacy_course_wide_repository_candidates(self, question: str, *, scope: QaScope) -> list[QaEvidenceCandidate]:
        if self.retrieval_repository is None:
            return []
        method = getattr(self.retrieval_repository, "search_course_wide_original_segments", None)
        if method is None:
            return []
        raw_segments = method(
            question=question,
            course_id=scope.course_id,
            parse_run_id=scope.active_parse_run_id,
            handout_version_id=scope.active_handout_version_id,
            handout_block_id=scope.current_handout_block_id,
            limit=8,
        )
        return _segment_candidates(raw_segments, scope=scope, source="course_wide_segment_lexical", start_rank=1)

    def _embed_question(self, question: str) -> list[float] | None:
        if self.embedding_client is None:
            return None
        try:
            embeddings = self.embedding_client.embed_texts([question])
        except Exception:
            return None
        if (
            len(embeddings) != 1
            or not isinstance(embeddings[0], list)
            or len(embeddings[0]) != EXPECTED_QUERY_EMBEDDING_DIM
        ):
            return None
        try:
            return [float(value) for value in embeddings[0]]
        except (TypeError, ValueError):
            return None


def _exact_context(context: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(context)
    merged["segments"] = [*_mapping_sequence(context.get("segments")), *_mapping_sequence(context.get("currentSegments") or context.get("current_segments"))]
    return merged


def _course_wide_context_segment_candidates(context: Mapping[str, Any], *, scope: QaScope) -> list[QaEvidenceCandidate]:
    return _segment_candidates(
        [*_mapping_sequence(context.get("segments")), *_mapping_sequence(context.get("currentSegments") or context.get("current_segments"))],
        scope=scope,
        source="course_document_segment",
        start_rank=1,
    )


def _segment_candidates(
    raw_segments: Any,
    *,
    scope: QaScope,
    source: str,
    start_rank: int,
) -> list[QaEvidenceCandidate]:
    candidates: list[QaEvidenceCandidate] = []
    for raw_segment in _mapping_sequence(raw_segments):
        if not scope_matches_payload(raw_segment, scope, require_course_parse=True):
            continue
        if source == "course_document_segment" and _field_value(raw_segment, "segmentType", "segment_type") == "video_caption":
            continue
        candidate = qa_evidence_candidate_from_segment_payload(
            raw_segment,
            source=source,  # type: ignore[arg-type]
            rank=start_rank + len(candidates),
            handout_version_id=scope.active_handout_version_id,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _handout_context_candidates(context: Mapping[str, Any], *, scope: QaScope) -> list[HandoutContextCandidate]:
    if "readyBlocks" in context:
        blocks = list(_mapping_sequence(context.get("readyBlocks")))
    elif "ready_blocks" in context:
        blocks = list(_mapping_sequence(context.get("ready_blocks")))
    else:
        blocks = [
            *_mapping_sequence([context.get("currentBlock") or context.get("current_block")]),
            *_mapping_sequence(context.get("adjacentBlocks") or context.get("adjacent_blocks")),
        ]
    candidates: list[HandoutContextCandidate] = []
    for block in blocks:
        if not scope_matches_payload(block, scope, require_handout_version=True):
            continue
        text = _block_text(block)
        if not text:
            continue
        block_id = _field_value(block, "handoutBlockId", "handout_block_id", "blockId", "block_id")
        is_current = block_id is not None and scope.current_handout_block_id is not None and str(block_id) == str(scope.current_handout_block_id)
        candidates.append(
            HandoutContextCandidate(
                rank=len(candidates) + 1,
                content_text=text,
                handout_block_id=block_id,
                outline_key=_field_value(block, "outlineKey", "outline_key"),
                title=_handout_context_title(block),
                source="current_handout_block" if is_current else _handout_source(block, context),
                course_id=scope.course_id,
                handout_version_id=scope.active_handout_version_id,
                sort_no=_as_int(_field_value(block, "sortNo", "sort_no")),
            )
        )
    return candidates


def _relevant_handout_contexts(
    question: str,
    contexts: Sequence[HandoutContextCandidate],
    *,
    scope: QaScope,
) -> list[HandoutContextCandidate]:
    scored = []
    for context in contexts:
        score = lexical_relevance_score(question, context.content_text)
        if score <= 0 and context.matched_by not in {"semantic", "hybrid"}:
            continue
        ranking_score = float(score) if score > 0 else float(context.score or 0.0)
        current_boost = 0 if str(context.handout_block_id) == str(scope.current_handout_block_id) else 1
        scored.append((-ranking_score, current_boost, context.sort_no or 0, str(context.handout_block_id or ""), context))
    return [
        _replace_handout_rank(item[-1], rank)
        for rank, item in enumerate(sorted(scored), start=1)
    ]


def _relevant_candidates(question: str, candidates: Sequence[QaEvidenceCandidate]) -> list[QaEvidenceCandidate]:
    relevant: list[tuple[float, QaEvidenceCandidate]] = []
    for candidate in candidates:
        score = lexical_relevance_score(question, candidate.content_text)
        if score <= 0 and not _semantic_original_candidate(candidate):
            continue
        relevant.append((float(score) if score > 0 else float(candidate.score or 0.0), candidate))
    ordered = [
        candidate
        for _, candidate in sorted(
            relevant,
            key=lambda item: (-item[0], item[1].rank, item[1].candidate_key),
        )
    ]
    return [replace_candidate_rank(candidate, index) for index, candidate in enumerate(ordered, start=1)]


def _dedupe_candidates(candidates: Sequence[QaEvidenceCandidate]) -> list[QaEvidenceCandidate]:
    output: list[QaEvidenceCandidate] = []
    seen: set[tuple[int, str, tuple[tuple[str, Any], ...]]] = set()
    for candidate in candidates:
        identity = qa_candidate_identity(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(candidate)
    return [replace_candidate_rank(candidate, index) for index, candidate in enumerate(output, start=1)]


def _dedupe_handout_contexts(contexts: Sequence[HandoutContextCandidate]) -> list[HandoutContextCandidate]:
    output: list[HandoutContextCandidate] = []
    seen: set[str] = set()
    for context in contexts:
        key = str(context.handout_block_id or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        output.append(context)
    return [_replace_handout_rank(context, index) for index, context in enumerate(output, start=1)]


def _with_active_handout_version(candidate: QaEvidenceCandidate, scope: QaScope) -> QaEvidenceCandidate:
    if candidate.handout_version_id == scope.active_handout_version_id:
        return candidate
    if candidate.handout_version_id is not None:
        return candidate
    return replace(candidate, handout_version_id=scope.active_handout_version_id)


def _has_citable_locator(candidate: QaEvidenceCandidate) -> bool:
    return candidate.resource_id > 0 and bool(candidate.locator)


def _semantic_original_candidate(candidate: QaEvidenceCandidate) -> bool:
    return candidate.source in {"course_wide_segment_semantic", "course_wide_segment_hybrid"}


def _handout_context_from_hybrid_candidate(
    candidate: HandoutBlockHybridCandidate,
    *,
    scope: QaScope,
    rank: int,
) -> HandoutContextCandidate:
    metadata = candidate.metadata_json or {}
    block_id = candidate.handout_block_id
    if block_id is not None and str(block_id) == str(scope.current_handout_block_id):
        source = "current_handout_block"
    else:
        source = "course_wide_handout_block"
    return HandoutContextCandidate(
        rank=rank,
        content_text=candidate.content_text,
        handout_block_id=block_id,
        outline_key=metadata.get("outlineKey") if isinstance(metadata.get("outlineKey"), str) else None,
        title=clean_text(str(metadata.get("title") or "")) or "讲义块",
        source=source,
        score=candidate.score,
        matched_by=candidate.matched_by,
        course_id=scope.course_id,
        handout_version_id=scope.active_handout_version_id,
        metadata_json=metadata,
    )


def _adjacent_handout_block_ids(context: Mapping[str, Any]) -> list[int | str]:
    return [
        block_id
        for block_id in (
            _field_value(item, "handoutBlockId", "handout_block_id", "blockId", "block_id")
            for item in _mapping_sequence(context.get("adjacentBlocks") or context.get("adjacent_blocks"))
        )
        if block_id not in (None, "")
    ]


def _force_unreferenced_response(response: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(response)
    normalized["citations"] = []
    return normalized


def _hard_security_out_of_scope_response() -> dict[str, Any]:
    response = _out_of_scope_response()
    metadata = dict(response.get("generationMetadata") or {})
    metadata["reason"] = "hard_security_out_of_scope"
    response["generationMetadata"] = metadata
    return response


def _block_text(block: Mapping[str, Any]) -> str:
    return clean_text(
        "\n".join(
            str(_field_value(block, key, _camel_to_snake(key)) or "")
            for key in ("title", "summary", "contentMd")
        )
    )


def _handout_context_title(block: Mapping[str, Any]) -> str:
    title = clean_text(str(_field_value(block, "title") or ""))
    for line in str(_field_value(block, "contentMd", "content_md") or "").splitlines():
        match = line.strip()
        if match.startswith("#"):
            heading = clean_text(match.lstrip("#").strip())
            if heading:
                return heading
    return title or "\u8bb2\u4e49\u5757"


def _handout_source(block: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    adjacent_ids = {
        str(_field_value(item, "handoutBlockId", "handout_block_id", "blockId", "block_id"))
        for item in _mapping_sequence(context.get("adjacentBlocks") or context.get("adjacent_blocks"))
    }
    block_id = str(_field_value(block, "handoutBlockId", "handout_block_id", "blockId", "block_id"))
    return "adjacent_handout_block" if block_id in adjacent_ids else "course_wide_handout_block"


def _replace_handout_rank(context: HandoutContextCandidate, rank: int) -> HandoutContextCandidate:
    return HandoutContextCandidate(
        rank=rank,
        content_text=context.content_text,
        handout_block_id=context.handout_block_id,
        outline_key=context.outline_key,
        title=context.title,
        source=context.source,
        score=context.score,
        matched_by=context.matched_by,
        course_id=context.course_id,
        handout_version_id=context.handout_version_id,
        sort_no=context.sort_no,
        metadata_json=context.metadata_json,
    )


def _mapping_sequence(value: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _field_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _camel_to_snake(value: str) -> str:
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in value).lstrip("_")


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
