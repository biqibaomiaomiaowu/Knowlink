from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence

from server.ai.core.errors import AIOutputParseError, fallback_reason_for_error
from server.ai.core.types import ChatMessage, JsonChatRequest
from server.ai.deepseek import get_configured_deepseek_chat_config
from server.ai.providers.deepseek_chat import (
    DeepSeekLangChainConfig,
    DeepSeekLangChainJsonClient,
    normalize_deepseek_base_url,
)
from server.ai.providers.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleJsonClient
from server.ai.service import AIService, get_default_ai_service
from server.config.settings import load_root_dotenv
from server.parsers.base import clean_text


QaCandidateSource = Literal[
    "current_block_ref",
    "knowledge_point_evidence",
    "adjacent_block",
    "course_document_segment",
]
QaAnswerType = Literal["direct_answer", "clarification", "insufficient_evidence"]
UnreferencedEvidenceTier = Literal["handout_context", "course_prior"]
_DEFAULT_QA_MODEL = "Doubao-Seed-2.0-pro"
_DEFAULT_QA_TIMEOUT_SEC = 60.0
_OUT_OF_SCOPE_INTENT_TERM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("天气", "气象", "气温", "温度", "下雨", "降雨", "降水", "气压", "台风", "预报"),
    ("新闻", "热搜", "娱乐", "明星", "媒体", "报道"),
    ("股票", "股价", "基金", "彩票", "中奖", "证券", "投资"),
)
_QA_SYSTEM_PROMPT = """你是 KnowLink 的块级学习问答助手。只返回 JSON，不要返回 Markdown 代码块或解释。
JSON 格式固定为：
{"answerMd":"...","answerType":"direct_answer|clarification|insufficient_evidence","citations":[{"resourceId":1,"segmentKey":"...","pageNo":1,"refLabel":"..."}]}
规则：
1. 只能基于输入 evidenceCandidates 回答，不得使用候选外资料或常识补充。
2. 如果候选证据不足，answerType 返回 insufficient_evidence，citations 返回空数组。
3. citations 只能从 evidenceCandidates 中选择，必须保留候选的 resourceId、segmentId 或 segmentKey、locator 和 refLabel。
4. 每个 citation 只能使用一种定位：pageNo、slideNo、anchorKey、或 startSec/endSec。
5. answerMd 使用中文 Markdown，简洁回答用户问题。
"""
_UNREFERENCED_QA_SYSTEM_PROMPT = """你是 KnowLink 的课程学习问答助手。只返回 JSON，不要返回 Markdown 代码块或解释。
JSON 格式固定为：
{"answerMd":"...","answerType":"direct_answer|clarification","citations":[]}
规则：
1. citations 必须返回空数组，不得编造或返回任何引用。
2. evidenceTier 为 handout_context 时，只能依据输入的讲义上下文回答；answerMd 必须说明“依据讲义内容回答，未找到可追溯原始资料引用”；上下文不足时返回 clarification。
3. evidenceTier 为 course_prior 时，只能回答与当前课程范围相关的问题；answerMd 必须说明“课程资料和讲义中未找到直接证据，以下是基于当前课程主题的补充解释”；超出课程范围或无法判断时返回 clarification。
4. answerMd 使用中文 Markdown，简洁回答用户问题。
"""


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

    def to_qa_citation(self) -> dict[str, Any]:
        return {"resourceId": self.resource_id, "refLabel": self.ref_label, **self.locator}


@dataclass(frozen=True)
class HandoutContextCandidate:
    rank: int
    content_text: str
    handout_block_id: int | str | None
    outline_key: str | None
    title: str
    source: Literal["current_handout_block", "adjacent_handout_block"]


@dataclass(frozen=True)
class QaAnswerWithRefs:
    response: dict[str, Any]
    refs: list[dict[str, Any]]


class QaAnswerClient(Protocol):
    def generate_answer(self, question: str, candidates: Sequence[QaEvidenceCandidate]) -> dict[str, Any]:
        """Return a raw QA response generated only from the provided candidates."""

    def generate_unreferenced_answer(
        self,
        question: str,
        *,
        context_text: str,
        evidence_tier: UnreferencedEvidenceTier,
        course_scope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a raw QA response without citations for non-original evidence tiers."""


def get_configured_qa_answer_client() -> QaAnswerClient | None:
    load_root_dotenv()
    provider = os.getenv("KNOWLINK_QA_PROVIDER", "vivo").strip().lower()
    if provider == "deepseek":
        config = get_configured_deepseek_chat_config()
        if config is None:
            return None
        return DeepSeekQaAnswerClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            timeout_sec=_env_float("KNOWLINK_VIVO_QA_TIMEOUT_SEC", _DEFAULT_QA_TIMEOUT_SEC),
            ai_service=_default_ai_service_for_provider("deepseek"),
        )
    if provider not in {"", "vivo"}:
        return None

    if not _env_bool("KNOWLINK_ENABLE_VIVO_QA"):
        return None

    app_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not app_key:
        return None

    return VivoQaAnswerClient(
        app_key=app_key,
        base_url=os.getenv("KNOWLINK_VIVO_BASE_URL", "https://api-ai.vivo.com.cn"),
        model=os.getenv("KNOWLINK_VIVO_QA_MODEL", _DEFAULT_QA_MODEL),
        timeout_sec=_env_float("KNOWLINK_VIVO_QA_TIMEOUT_SEC", _DEFAULT_QA_TIMEOUT_SEC),
        ai_service=_default_ai_service_for_provider("vivo"),
    )


class VivoQaAnswerClient:
    def __init__(
        self,
        *,
        app_key: str,
        base_url: str,
        model: str,
        timeout_sec: float | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self._model = model
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_QA_TIMEOUT_SEC
        self._ai_service = ai_service or _scoped_vivo_ai_service(
            app_key=app_key,
            base_url=base_url,
            model=model,
            timeout_sec=self._timeout_sec,
        )
        self._last_request_at = 0.0
        self._min_request_interval_sec = 0.8

    def generate_answer(self, question: str, candidates: Sequence[QaEvidenceCandidate]) -> dict[str, Any]:
        if not candidates:
            raise RuntimeError("vivo qa requires at least one evidence candidate")

        self._throttle()
        return _complete_model_json(
            self._ai_service,
            JsonChatRequest(
                provider="vivo",
                model=self._model,
                messages=[
                    ChatMessage(role="system", content=_QA_SYSTEM_PROMPT),
                    ChatMessage(role="user", content=_build_qa_prompt(question, candidates)),
                ],
                temperature=0.1,
                timeout_sec=self._timeout_sec,
                response_format={"type": "json_object"},
                metadata={"max_tokens": 2048, "stream": False, "request_id": str(uuid.uuid4())},
            ),
            label="vivo qa",
        )

    def generate_unreferenced_answer(
        self,
        question: str,
        *,
        context_text: str,
        evidence_tier: UnreferencedEvidenceTier,
        course_scope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._throttle()
        return _complete_model_json(
            self._ai_service,
            JsonChatRequest(
                provider="vivo",
                model=self._model,
                messages=[
                    ChatMessage(role="system", content=_UNREFERENCED_QA_SYSTEM_PROMPT),
                    ChatMessage(
                        role="user",
                        content=_build_unreferenced_qa_prompt(
                            question,
                            context_text=context_text,
                            evidence_tier=evidence_tier,
                            course_scope=course_scope,
                        ),
                    ),
                ],
                temperature=0.1,
                timeout_sec=self._timeout_sec,
                response_format={"type": "json_object"},
                metadata={"max_tokens": 2048, "stream": False, "request_id": str(uuid.uuid4())},
            ),
            label="vivo unreferenced qa",
        )

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_request_interval_sec:
            time.sleep(self._min_request_interval_sec - elapsed)
        self._last_request_at = time.monotonic()


class DeepSeekQaAnswerClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str,
        timeout_sec: float | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._timeout_sec = timeout_sec if timeout_sec is not None else _DEFAULT_QA_TIMEOUT_SEC
        self._ai_service = ai_service or _scoped_deepseek_ai_service(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_sec=self._timeout_sec,
        )

    def generate_answer(self, question: str, candidates: Sequence[QaEvidenceCandidate]) -> dict[str, Any]:
        if not candidates:
            raise RuntimeError("deepseek qa requires at least one evidence candidate")

        return _complete_model_json(
            self._ai_service,
            JsonChatRequest(
                provider="deepseek",
                model=self._model,
                messages=[
                    ChatMessage(role="system", content=_QA_SYSTEM_PROMPT),
                    ChatMessage(role="user", content=_build_qa_prompt(question, candidates)),
                ],
                timeout_sec=self._timeout_sec,
                response_format={"type": "json_object"},
                metadata={"max_tokens": 4096, "reasoning_effort": self._reasoning_effort},
            ),
            label="deepseek qa",
        )

    def generate_unreferenced_answer(
        self,
        question: str,
        *,
        context_text: str,
        evidence_tier: UnreferencedEvidenceTier,
        course_scope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _complete_model_json(
            self._ai_service,
            JsonChatRequest(
                provider="deepseek",
                model=self._model,
                messages=[
                    ChatMessage(role="system", content=_UNREFERENCED_QA_SYSTEM_PROMPT),
                    ChatMessage(
                        role="user",
                        content=_build_unreferenced_qa_prompt(
                            question,
                            context_text=context_text,
                            evidence_tier=evidence_tier,
                            course_scope=course_scope,
                        ),
                    ),
                ],
                timeout_sec=self._timeout_sec,
                response_format={"type": "json_object"},
                metadata={"max_tokens": 4096, "reasoning_effort": self._reasoning_effort},
            ),
            label="deepseek unreferenced qa",
        )


def generate_block_qa_response(
    question: str,
    *,
    current_block: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]] = (),
    knowledge_point_evidences: Sequence[Mapping[str, Any]] = (),
    adjacent_blocks: Sequence[Mapping[str, Any]] = (),
    active_course_id: int | None = None,
    active_parse_run_id: int | None = None,
    active_handout_version_id: int | None = None,
    course_scope: Mapping[str, Any] | None = None,
    client: QaAnswerClient | None = None,
) -> dict[str, Any]:
    candidates = build_block_scoped_qa_candidates(
        question,
        current_block=current_block,
        segments=segments,
        knowledge_point_evidences=knowledge_point_evidences,
        adjacent_blocks=adjacent_blocks,
        active_course_id=active_course_id,
        active_parse_run_id=active_parse_run_id,
        active_handout_version_id=active_handout_version_id,
    )
    answer_candidates = _relevant_candidates(question, candidates)
    has_course_scope = _has_course_scope(course_scope)
    if not answer_candidates:
        handout_contexts = _relevant_handout_contexts(
            question,
            _handout_context_candidates(current_block=current_block, adjacent_blocks=adjacent_blocks),
        )
        if handout_contexts:
            if client is not None:
                try:
                    return _normalize_unreferenced_qa_response(
                        client.generate_unreferenced_answer(
                            question,
                            context_text=handout_contexts[0].content_text,
                            evidence_tier="handout_context",
                        ),
                        evidence_tier="handout_context",
                        reason="handout_context_match",
                        handout_context=handout_contexts[0],
                    )
                except Exception as exc:
                    return _fallback_handout_context_response(
                        handout_contexts[0],
                        reason=fallback_reason_for_error(exc),
                    )
            return _fallback_handout_context_response(handout_contexts[0], reason="handout_context_match")
        if has_course_scope:
            if _question_is_course_related(question, course_scope):
                if client is not None:
                    try:
                        return _normalize_unreferenced_qa_response(
                            client.generate_unreferenced_answer(
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
            return _out_of_scope_response()
        return insufficient_evidence_response(source="fallback", reason="no_candidate_evidence")

    if client is not None:
        try:
            return _normalize_qa_response_payload(
                client.generate_answer(question, answer_candidates),
                candidates=answer_candidates,
            )
        except Exception as exc:
            return _fallback_qa_response(answer_candidates, reason=fallback_reason_for_error(exc))

    return _fallback_qa_response(answer_candidates, reason="model_unavailable")


def build_block_scoped_qa_candidates(
    question: str,
    *,
    current_block: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]] = (),
    knowledge_point_evidences: Sequence[Mapping[str, Any]] = (),
    adjacent_blocks: Sequence[Mapping[str, Any]] = (),
    active_course_id: int | None = None,
    active_parse_run_id: int | None = None,
    active_handout_version_id: int | None = None,
    max_document_segments: int = 4,
) -> list[QaEvidenceCandidate]:
    course_id = _as_positive_int(active_course_id) or _as_positive_int(_field_value(current_block, "courseId", "course_id"))
    parse_run_id = _as_positive_int(active_parse_run_id) or _as_positive_int(
        _field_value(current_block, "parseRunId", "parse_run_id")
    )
    handout_version_id = _as_positive_int(active_handout_version_id) or _as_positive_int(
        _field_value(current_block, "handoutVersionId", "handout_version_id")
    )
    block_id = _field_value(current_block, "handoutBlockId", "handout_block_id", "outlineKey", "outline_key")
    if not _block_matches_active_scope(
        current_block,
        active_course_id=course_id,
        active_parse_run_id=parse_run_id,
        active_handout_version_id=handout_version_id,
    ):
        return []

    normalized_segments = [_normalize_segment(segment, index) for index, segment in enumerate(segments, start=1)]
    segment_by_key = {segment["segmentKey"]: segment for segment in normalized_segments if segment.get("segmentKey")}
    segment_by_id = {
        int(segment["segmentId"]): segment
        for segment in normalized_segments
        if _as_positive_int(segment.get("segmentId")) is not None
    }

    candidates: list[QaEvidenceCandidate] = []
    seen: set[tuple[int, str, tuple[tuple[str, Any], ...]]] = set()

    def append(candidate: QaEvidenceCandidate | None) -> None:
        if candidate is None:
            return
        identity = qa_candidate_identity(candidate)
        if identity in seen:
            return
        seen.add(identity)
        candidates.append(candidate)

    for citation in _mapping_list(current_block.get("citations")):
        append(
            _candidate_from_citation(
                citation,
                segment_by_key=segment_by_key,
                segment_by_id=segment_by_id,
                segments=normalized_segments,
                source="current_block_ref",
                rank=len(candidates) + 1,
                fallback_content=_block_text(current_block),
                fallback_handout_block_id=block_id,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
            )
        )

    for source_segment_key in _source_segment_keys(current_block):
        segment = segment_by_key.get(_stable_key(source_segment_key))
        if segment is None:
            continue
        if segment.get("segmentType") != "video_caption":
            continue
        if not _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id):
            continue
        append(
            _candidate_from_segment(
                segment,
                source="current_block_ref",
                rank=len(candidates) + 1,
                handout_block_id=block_id,
                handout_version_id=handout_version_id,
                content_override=None,
                ref_label=None,
                locator_override=None,
            )
        )

    current_kp_keys = _current_block_knowledge_point_keys(current_block)
    for evidence in knowledge_point_evidences:
        if not isinstance(evidence, Mapping):
            continue
        if not current_kp_keys:
            continue
        if str(_field_value(evidence, "knowledgePointKey", "knowledge_point_key") or "") not in current_kp_keys:
            continue
        append(
            _candidate_from_evidence(
                evidence,
                segment_by_key=segment_by_key,
                segment_by_id=segment_by_id,
                segments=normalized_segments,
                rank=len(candidates) + 1,
                course_id=course_id,
                parse_run_id=parse_run_id,
                handout_version_id=handout_version_id,
                handout_block_id=block_id,
            )
        )

    for adjacent_block in _sorted_adjacent_blocks(adjacent_blocks, current_block=current_block):
        if handout_version_id is not None:
            adjacent_version_id = _as_positive_int(_field_value(adjacent_block, "handoutVersionId", "handout_version_id"))
            if adjacent_version_id != handout_version_id:
                continue
        if not _block_matches_active_scope(
            adjacent_block,
            active_course_id=course_id,
            active_parse_run_id=parse_run_id,
            active_handout_version_id=handout_version_id,
        ):
            continue
        for citation in _mapping_list(adjacent_block.get("citations")):
            append(
                _candidate_from_citation(
                    citation,
                    segment_by_key=segment_by_key,
                    segment_by_id=segment_by_id,
                    segments=normalized_segments,
                    source="adjacent_block",
                    rank=len(candidates) + 1,
                    fallback_content=_block_text(adjacent_block),
                    fallback_handout_block_id=_field_value(
                        adjacent_block,
                        "handoutBlockId",
                        "handout_block_id",
                        "outlineKey",
                        "outline_key",
                    ),
                    course_id=course_id,
                    parse_run_id=parse_run_id,
                    handout_version_id=handout_version_id,
                )
            )

    document_segments = [
        segment
        for segment in _rank_document_segments(normalized_segments, question)
        if _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id)
        and _relevance_score(question, str(segment.get("textContent") or "")) > 0
    ]
    for segment in document_segments[:max_document_segments]:
        append(
            _candidate_from_segment(
                segment,
                source="course_document_segment",
                rank=len(candidates) + 1,
                handout_block_id=block_id,
                handout_version_id=handout_version_id,
                content_override=None,
                ref_label=None,
                locator_override=None,
            )
        )

    return [_replace_rank(candidate, index) for index, candidate in enumerate(candidates, start=1)]


def insufficient_evidence_response(*, source: str = "fallback", reason: str = "no_candidate_evidence") -> dict[str, Any]:
    return {
        "answerMd": "当前讲义块和课程资料中的证据不足，暂时不能可靠回答这个问题。",
        "answerType": "insufficient_evidence",
        "citations": [],
        "generationMetadata": _generation_metadata(source=source, reason=reason),
    }


def normalize_qa_answer_with_refs(
    payload: Mapping[str, Any],
    candidates: Sequence[QaEvidenceCandidate],
    *,
    active_course_id: int,
    active_parse_run_id: int,
    active_handout_version_id: int,
) -> QaAnswerWithRefs:
    scoped_candidates = [
        candidate
        for candidate in candidates
        if _candidate_matches_scope(
            candidate,
            active_course_id=active_course_id,
            active_parse_run_id=active_parse_run_id,
            active_handout_version_id=active_handout_version_id,
        )
    ]
    response = _normalize_qa_response_payload(payload, candidates=scoped_candidates)
    refs = (
        []
        if response.get("answerType") == "insufficient_evidence"
        else build_qa_message_refs(
            payload,
            scoped_candidates,
            active_course_id=active_course_id,
            active_parse_run_id=active_parse_run_id,
            active_handout_version_id=active_handout_version_id,
        )
    )
    return QaAnswerWithRefs(response=response, refs=refs)


def build_qa_message_refs(
    response: Mapping[str, Any],
    candidates: Sequence[QaEvidenceCandidate],
    *,
    active_course_id: int,
    active_parse_run_id: int,
    active_handout_version_id: int,
) -> list[dict[str, Any]]:
    if (response.get("answerType") or response.get("answer_type")) == "insufficient_evidence":
        return []

    scoped_candidates = [
        candidate
        for candidate in candidates
        if _candidate_matches_scope(
            candidate,
            active_course_id=active_course_id,
            active_parse_run_id=active_parse_run_id,
            active_handout_version_id=active_handout_version_id,
        )
    ]
    candidate_by_identity = _candidate_by_identity(scoped_candidates)
    candidate_by_public_identity = _candidate_by_public_identity(scoped_candidates)
    refs: list[dict[str, Any]] = []
    seen: set[tuple[int, str, tuple[tuple[str, Any], ...]]] = set()
    for raw_citation in _mapping_list(response.get("citations")):
        has_segment_identity = _has_segment_identity(raw_citation)
        exact_identity = _citation_identity(raw_citation)
        candidate = candidate_by_identity.get(exact_identity) if exact_identity is not None else None
        if candidate is not None and has_segment_identity and not _candidate_matches_explicit_segment_identity(
            candidate, raw_citation
        ):
            candidate = None
        if candidate is None:
            if has_segment_identity:
                continue
            public_identity = _public_citation_identity(raw_citation)
            if public_identity is None:
                continue
            candidate = candidate_by_public_identity.get(public_identity)
        if candidate is None:
            continue
        identity = qa_candidate_identity(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        refs.append(_qa_message_ref_from_candidate(candidate, sort_no=len(refs) + 1))
    return refs


def qa_candidate_identity(candidate: QaEvidenceCandidate) -> tuple[int, str, tuple[tuple[str, Any], ...]]:
    if candidate.segment_id is not None:
        segment_identity = f"id:{candidate.segment_id}"
    elif candidate.segment_key:
        segment_identity = f"key:{candidate.segment_key}"
    else:
        segment_identity = f"source:{candidate.source}:{candidate.rank}"
    return (candidate.resource_id, segment_identity, _locator_tuple(candidate.locator))


def _normalize_qa_response_payload(payload: Mapping[str, Any], *, candidates: Sequence[QaEvidenceCandidate]) -> dict[str, Any]:
    answer_type = str(payload.get("answerType") or payload.get("answer_type") or "direct_answer")
    if answer_type not in {"direct_answer", "clarification", "insufficient_evidence"}:
        answer_type = "direct_answer"
    answer_md = clean_text(str(payload.get("answerMd") or payload.get("answer_md") or ""))
    if not answer_md:
        return insufficient_evidence_response(source="model", reason="empty_answer")
    if answer_type == "insufficient_evidence":
        return {
            "answerMd": answer_md,
            "answerType": answer_type,
            "citations": [],
            "generationMetadata": _generation_metadata(source="model", reason="insufficient_evidence"),
        }

    candidate_by_identity = _candidate_by_identity(candidates)
    candidate_citations_by_public_identity = _candidate_citations_by_public_identity(candidates)
    citations: list[dict[str, Any]] = []
    seen: set[tuple[int, str, tuple[tuple[str, Any], ...]]] = set()
    for raw_citation in _mapping_list(payload.get("citations")):
        has_segment_identity = _has_segment_identity(raw_citation)
        identity = _citation_identity(raw_citation)
        candidate = candidate_by_identity.get(identity) if identity is not None else None
        if candidate is not None and has_segment_identity and not _candidate_matches_explicit_segment_identity(
            candidate, raw_citation
        ):
            candidate = None
        if candidate is not None and identity is not None:
            normalized_identity = qa_candidate_identity(candidate)
            if normalized_identity in seen:
                continue
            seen.add(normalized_identity)
            citations.append(candidate.to_qa_citation())
            continue
        if has_segment_identity:
            continue

        public_identity = _public_citation_identity(raw_citation)
        if public_identity is None:
            continue
        candidate_match = candidate_citations_by_public_identity.get(public_identity)
        if candidate_match is None:
            continue
        candidate_identity, citation = candidate_match
        if candidate_identity in seen:
            continue
        seen.add(candidate_identity)
        citations.append(citation)

    if not citations:
        return insufficient_evidence_response(source="model", reason="citation_rejected")
    return {
        "answerMd": answer_md,
        "answerType": answer_type,
        "citations": citations,
        "generationMetadata": _generation_metadata(source="model", reason="model_response"),
    }


def _normalize_unreferenced_qa_response(
    payload: Mapping[str, Any],
    *,
    evidence_tier: UnreferencedEvidenceTier,
    reason: str,
    handout_context: HandoutContextCandidate | None = None,
) -> dict[str, Any]:
    answer_type = str(payload.get("answerType") or payload.get("answer_type") or "direct_answer")
    if answer_type not in {"direct_answer", "clarification"}:
        answer_type = "direct_answer"
    answer_md = clean_text(str(payload.get("answerMd") or payload.get("answer_md") or ""))
    if not answer_md:
        raise AIOutputParseError("unreferenced qa answerMd is required")
    answer_md = _ensure_unreferenced_disclosure(answer_md, evidence_tier=evidence_tier)
    return {
        "answerMd": answer_md,
        "answerType": answer_type,
        "citations": [],
        "generationMetadata": _generation_metadata(
            source="model",
            reason=reason,
            evidence_tier=evidence_tier,
            handout_context=_handout_context_metadata(handout_context) if handout_context is not None else None,
        ),
    }


def _ensure_unreferenced_disclosure(answer_md: str, *, evidence_tier: UnreferencedEvidenceTier) -> str:
    if evidence_tier == "handout_context":
        if _has_handout_context_disclosure(answer_md):
            return answer_md
        return f"依据讲义内容回答，未找到可追溯原始资料引用。\n\n{answer_md}"
    if _has_course_prior_disclosure(answer_md):
        return answer_md
    return f"课程资料和讲义中未找到直接证据，以下是基于当前课程主题的补充解释。\n\n{answer_md}"


def _has_handout_context_disclosure(answer_md: str) -> bool:
    return "讲义" in answer_md and ("未找到可追溯原始资料引用" in answer_md or "无原始资料引用" in answer_md)


def _has_course_prior_disclosure(answer_md: str) -> bool:
    return ("无直接证据" in answer_md or "未找到直接证据" in answer_md) and (
        "基于当前课程主题" in answer_md or "补充解释" in answer_md
    )


def _fallback_qa_response(candidates: Sequence[QaEvidenceCandidate], *, reason: str) -> dict[str, Any]:
    if not candidates:
        return insufficient_evidence_response(source="fallback", reason="no_candidate_evidence")
    top = candidates[0]
    answer_text = _truncate(top.content_text, 180)
    return {
        "answerMd": f"根据{top.ref_label}，{answer_text}",
        "answerType": "direct_answer",
        "citations": [top.to_qa_citation()],
        "generationMetadata": _generation_metadata(source="fallback", reason=reason),
    }


def _fallback_handout_context_response(context: HandoutContextCandidate, *, reason: str) -> dict[str, Any]:
    answer_text = _truncate(context.content_text, 220)
    return {
        "answerMd": f"依据讲义内容回答，未找到可追溯原始资料引用。\n\n{answer_text}",
        "answerType": "direct_answer",
        "citations": [],
        "generationMetadata": _generation_metadata(
            source="fallback",
            reason=reason,
            evidence_tier="handout_context",
            handout_context=_handout_context_metadata(context),
        ),
    }


def _course_scope_text(course_scope: Mapping[str, Any] | None) -> str:
    if not isinstance(course_scope, Mapping):
        return ""
    values: list[str] = []
    for key in ("title", "summary", "goalText", "goal_text"):
        value = course_scope.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    for key in ("resourceTitles", "handoutTitles", "knowledgePointNames"):
        value = course_scope.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if str(item).strip())
    return clean_text("\n".join(values))


def _has_course_scope(course_scope: Mapping[str, Any] | None) -> bool:
    return bool(_course_scope_text(course_scope))


def _question_is_course_related(question: str, course_scope: Mapping[str, Any] | None) -> bool:
    scope_text = _course_scope_text(course_scope)
    if not scope_text:
        return False
    if _question_has_out_of_scope_intent(question, course_scope):
        return False
    return _relevance_score(question, scope_text) > 0


def _question_has_out_of_scope_intent(question: str, course_scope: Mapping[str, Any] | None = None) -> bool:
    normalized = clean_text(question).lower()
    if not normalized:
        return False
    scope_text = _course_scope_text(course_scope).lower()
    for term_group in _OUT_OF_SCOPE_INTENT_TERM_GROUPS:
        if any(term in normalized for term in term_group) and not any(term in scope_text for term in term_group):
            return True
    return False


def _fallback_course_prior_response(question: str, *, reason: str) -> dict[str, Any]:
    answer = clean_text(question)
    return {
        "answerMd": (
            "课程资料和讲义中未找到直接证据，以下是基于当前课程主题的补充解释。\n\n"
            f"{answer} 可以结合当前课程中的相关概念来理解；请优先回到讲义和原始资料中的定义、例子和符号约定进行核对。"
        ),
        "answerType": "direct_answer",
        "citations": [],
        "generationMetadata": _generation_metadata(
            source="fallback",
            reason=reason,
            evidence_tier="course_prior",
        ),
    }


def _out_of_scope_response() -> dict[str, Any]:
    return {
        "answerMd": "这个问题超出了当前课程范围。请提问与当前课程内容、讲义或学习目标相关的问题。",
        "answerType": "clarification",
        "citations": [],
        "generationMetadata": _generation_metadata(
            source="fallback",
            reason="out_of_scope",
            evidence_tier="out_of_scope",
        ),
    }


def _generation_metadata(
    *,
    source: str,
    reason: str,
    evidence_tier: str = "original_evidence",
    handout_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"source": source, "reason": reason, "evidenceTier": evidence_tier}
    if handout_context:
        metadata["handoutContext"] = {
            key: value
            for key, value in handout_context.items()
            if key in {"handoutBlockId", "outlineKey", "title"} and value not in (None, "")
        }
    return metadata



def _candidate_from_evidence(
    evidence: Mapping[str, Any],
    *,
    segment_by_key: Mapping[str, Mapping[str, Any]],
    segment_by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    rank: int,
    course_id: int | None,
    parse_run_id: int | None,
    handout_version_id: int | None,
    handout_block_id: int | str | None,
) -> QaEvidenceCandidate | None:
    segment = _segment_from_ref(evidence, segment_by_key=segment_by_key, segment_by_id=segment_by_id, segments=segments)
    if segment is None or not _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id):
        return None
    return _candidate_from_segment(
        segment,
        source="knowledge_point_evidence",
        rank=rank,
        handout_block_id=handout_block_id,
        handout_version_id=handout_version_id,
        content_override=None,
        ref_label=None,
        locator_override=None,
    )


def _candidate_from_citation(
    citation: Mapping[str, Any],
    *,
    segment_by_key: Mapping[str, Mapping[str, Any]],
    segment_by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    source: QaCandidateSource,
    rank: int,
    fallback_content: str,
    fallback_handout_block_id: int | str | None,
    course_id: int | None,
    parse_run_id: int | None,
    handout_version_id: int | None,
) -> QaEvidenceCandidate | None:
    segment = _segment_from_ref(citation, segment_by_key=segment_by_key, segment_by_id=segment_by_id, segments=segments)
    if segment is None:
        return None
    if not _matches_course_parse(segment, course_id=course_id, parse_run_id=parse_run_id):
        return None

    locator = _locator_from_citation_segment(citation, segment)
    if not locator:
        return None
    return _candidate_from_segment(
        segment,
        source=source,
        rank=rank,
        handout_block_id=fallback_handout_block_id,
        handout_version_id=handout_version_id,
        content_override=fallback_content if source == "adjacent_block" else None,
        ref_label=clean_text(str(_field_value(citation, "refLabel", "ref_label") or "")) or None,
        locator_override=locator,
    )


def _candidate_from_segment(
    segment: Mapping[str, Any],
    *,
    source: QaCandidateSource,
    rank: int,
    handout_block_id: int | str | None,
    handout_version_id: int | None,
    content_override: str | None,
    ref_label: str | None,
    locator_override: Mapping[str, Any] | None,
) -> QaEvidenceCandidate | None:
    content_text = clean_text(content_override or str(segment.get("textContent") or segment.get("plainText") or ""))
    if not content_text:
        return None
    resource_id = _as_positive_int(segment.get("resourceId"))
    locator = dict(locator_override or _locator(segment))
    if resource_id is None or not locator:
        return None
    segment_key = str(segment.get("segmentKey") or "")
    return QaEvidenceCandidate(
        candidate_key=f"{source}:{segment_key or rank}:{_locator_key(locator)}",
        source=source,
        rank=rank,
        content_text=content_text,
        resource_id=resource_id,
        ref_label=ref_label or _segment_label(segment, locator=locator),
        locator=locator,
        segment_id=_as_positive_int(segment.get("segmentId")),
        segment_key=segment_key or None,
        course_id=_as_positive_int(segment.get("courseId")),
        parse_run_id=_as_positive_int(segment.get("parseRunId")),
        handout_version_id=handout_version_id,
        handout_block_id=handout_block_id,
        metadata_json={
            key: value
            for key, value in {
                "segmentType": segment.get("segmentType"),
                "resourceType": segment.get("resourceType"),
                "source": source,
            }.items()
            if value not in (None, "")
        },
    )


def _locator_from_citation_segment(citation: Mapping[str, Any], segment: Mapping[str, Any]) -> dict[str, Any]:
    segment_locator = _locator(segment)
    if not segment_locator:
        return {}

    citation_locator = _locator(citation)
    if not citation_locator:
        return segment_locator

    if "startSec" in segment_locator and "endSec" in segment_locator:
        if "startSec" not in citation_locator or "endSec" not in citation_locator:
            return segment_locator
        start_sec = _as_int(citation_locator.get("startSec"))
        end_sec = _as_int(citation_locator.get("endSec"))
        segment_start = _as_int(segment_locator.get("startSec"))
        segment_end = _as_int(segment_locator.get("endSec"))
        if (
            start_sec is None
            or end_sec is None
            or segment_start is None
            or segment_end is None
            or start_sec < segment_start
            or end_sec > segment_end
            or end_sec <= start_sec
        ):
            return {}
        return {"startSec": start_sec, "endSec": end_sec}

    return segment_locator


def _segment_from_ref(
    ref: Mapping[str, Any],
    *,
    segment_by_key: Mapping[str, Mapping[str, Any]],
    segment_by_id: Mapping[int, Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    key = _field_value(ref, "segmentKey", "segment_key")
    segment_from_key = segment_by_key.get(_stable_key(key)) if isinstance(key, str) and key.strip() else None
    segment_id = _as_positive_int(_field_value(ref, "segmentId", "segment_id"))
    segment_from_id = segment_by_id.get(segment_id) if segment_id is not None else None
    if key or segment_id is not None:
        if segment_from_key is not None and segment_from_id is not None:
            if segment_from_key.get("segmentKey") != segment_from_id.get("segmentKey"):
                return None
            return segment_from_key
        return segment_from_key or segment_from_id

    resource_id = _as_positive_int(_field_value(ref, "resourceId", "resource_id"))
    locator = _locator(ref)
    if resource_id is None or not locator:
        return None
    for segment in segments:
        if _as_positive_int(segment.get("resourceId")) != resource_id:
            continue
        if _locator(segment) == locator:
            return segment
    return None


def _candidate_by_identity(
    candidates: Sequence[QaEvidenceCandidate],
) -> dict[tuple[int, str, tuple[tuple[str, Any], ...]], QaEvidenceCandidate]:
    output: dict[tuple[int, str, tuple[tuple[str, Any], ...]], QaEvidenceCandidate] = {}
    for candidate in candidates:
        locator = _locator_tuple(candidate.locator)
        if candidate.segment_id is not None:
            output.setdefault((candidate.resource_id, f"id:{candidate.segment_id}", locator), candidate)
        if candidate.segment_key:
            output.setdefault((candidate.resource_id, f"key:{candidate.segment_key}", locator), candidate)
        output.setdefault(qa_candidate_identity(candidate), candidate)
    return output


def _candidate_citations_by_public_identity(
    candidates: Sequence[QaEvidenceCandidate],
) -> dict[tuple[int, tuple[tuple[str, Any], ...]], tuple[tuple[int, str, tuple[tuple[str, Any], ...]], dict[str, Any]]]:
    output: dict[tuple[int, tuple[tuple[str, Any], ...]], tuple[tuple[int, str, tuple[tuple[str, Any], ...]], dict[str, Any]]] = {}
    for candidate in candidates:
        public_identity = (candidate.resource_id, _locator_tuple(candidate.locator))
        output.setdefault(public_identity, (qa_candidate_identity(candidate), candidate.to_qa_citation()))
    return output


def _candidate_by_public_identity(
    candidates: Sequence[QaEvidenceCandidate],
) -> dict[tuple[int, tuple[tuple[str, Any], ...]], QaEvidenceCandidate]:
    output: dict[tuple[int, tuple[tuple[str, Any], ...]], QaEvidenceCandidate] = {}
    for candidate in candidates:
        output.setdefault((candidate.resource_id, _locator_tuple(candidate.locator)), candidate)
    return output


def _citation_identity(citation: Mapping[str, Any]) -> tuple[int, str, tuple[tuple[str, Any], ...]] | None:
    resource_id = _as_positive_int(_field_value(citation, "resourceId", "resource_id"))
    if resource_id is None:
        return None
    segment_id = _as_positive_int(_field_value(citation, "segmentId", "segment_id"))
    if segment_id is not None:
        segment_identity = f"id:{segment_id}"
    else:
        segment_key = _field_value(citation, "segmentKey", "segment_key")
        if not isinstance(segment_key, str) or not segment_key.strip():
            return None
        segment_identity = f"key:{_stable_key(segment_key)}"
    locator = _locator(citation)
    if not locator:
        return None
    return (resource_id, segment_identity, _locator_tuple(locator))


def _public_citation_identity(citation: Mapping[str, Any]) -> tuple[int, tuple[tuple[str, Any], ...]] | None:
    resource_id = _as_positive_int(_field_value(citation, "resourceId", "resource_id"))
    locator = _locator(citation)
    if resource_id is None or not locator:
        return None
    return (resource_id, _locator_tuple(locator))


def _has_segment_identity(citation: Mapping[str, Any]) -> bool:
    has_segment_id_field = "segmentId" in citation or "segment_id" in citation
    has_segment_key_field = "segmentKey" in citation or "segment_key" in citation
    return has_segment_id_field or has_segment_key_field


def _candidate_matches_explicit_segment_identity(
    candidate: QaEvidenceCandidate,
    citation: Mapping[str, Any],
) -> bool:
    if "segmentId" in citation or "segment_id" in citation:
        segment_id = _as_positive_int(_field_value(citation, "segmentId", "segment_id"))
        if segment_id is None or candidate.segment_id != segment_id:
            return False
    if "segmentKey" in citation or "segment_key" in citation:
        segment_key = _field_value(citation, "segmentKey", "segment_key")
        if not isinstance(segment_key, str) or not segment_key.strip():
            return False
        if candidate.segment_key != _stable_key(segment_key):
            return False
    return True


def _candidate_matches_scope(
    candidate: QaEvidenceCandidate,
    *,
    active_course_id: int,
    active_parse_run_id: int,
    active_handout_version_id: int,
) -> bool:
    return (
        candidate.course_id == active_course_id
        and candidate.parse_run_id == active_parse_run_id
        and candidate.handout_version_id == active_handout_version_id
    )


def _block_matches_active_scope(
    block: Mapping[str, Any],
    *,
    active_course_id: int | None,
    active_parse_run_id: int | None,
    active_handout_version_id: int | None,
) -> bool:
    course_id = _as_positive_int(_field_value(block, "courseId", "course_id"))
    parse_run_id = _as_positive_int(_field_value(block, "parseRunId", "parse_run_id"))
    handout_version_id = _as_positive_int(_field_value(block, "handoutVersionId", "handout_version_id"))
    if active_course_id is not None and course_id is not None and course_id != active_course_id:
        return False
    if active_parse_run_id is not None and parse_run_id is not None and parse_run_id != active_parse_run_id:
        return False
    if active_handout_version_id is not None and handout_version_id != active_handout_version_id:
        return False
    return True


def _qa_message_ref_from_candidate(candidate: QaEvidenceCandidate, *, sort_no: int) -> dict[str, Any]:
    ref = {
        "resourceId": candidate.resource_id,
        "segmentId": candidate.segment_id,
        "segmentKey": candidate.segment_key,
        "refType": _ref_type(candidate.locator),
        "quoteText": _truncate(candidate.content_text, 300),
        "refLabel": candidate.ref_label,
        "sortNo": sort_no,
        "rank": candidate.rank,
        "courseId": candidate.course_id,
        "parseRunId": candidate.parse_run_id,
        "handoutVersionId": candidate.handout_version_id,
        **candidate.locator,
    }
    return {key: value for key, value in ref.items() if value not in (None, "", [])}


def _ref_type(locator: Mapping[str, Any]) -> str:
    if "startSec" in locator and "endSec" in locator:
        return "video_time_range"
    if "pageNo" in locator:
        return "pdf_page"
    if "slideNo" in locator:
        return "ppt_slide"
    if "anchorKey" in locator:
        return "doc_anchor"
    return "segment"


def _current_block_knowledge_point_keys(block: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for item in _mapping_list(block.get("knowledgePoints") or block.get("knowledge_points")):
        key = _field_value(item, "knowledgePointKey", "knowledge_point_key")
        if isinstance(key, str) and key:
            keys.add(key)
    return keys


def _sorted_adjacent_blocks(
    adjacent_blocks: Sequence[Mapping[str, Any]],
    *,
    current_block: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    current_sort = _as_int(_field_value(current_block, "sortNo", "sort_no")) or 0
    return sorted(
        [block for block in adjacent_blocks if isinstance(block, Mapping)],
        key=lambda block: (
            abs((_as_int(_field_value(block, "sortNo", "sort_no")) or 0) - current_sort),
            _as_int(_field_value(block, "sortNo", "sort_no")) or 0,
        ),
    )


def _handout_context_candidates(
    *,
    current_block: Mapping[str, Any],
    adjacent_blocks: Sequence[Mapping[str, Any]],
) -> list[HandoutContextCandidate]:
    blocks = [current_block, *_sorted_adjacent_blocks(adjacent_blocks, current_block=current_block)]
    candidates: list[HandoutContextCandidate] = []
    for block in blocks:
        text = _block_text(block)
        if not text:
            continue
        candidates.append(
            HandoutContextCandidate(
                rank=len(candidates) + 1,
                content_text=text,
                handout_block_id=_field_value(block, "handoutBlockId", "handout_block_id", "blockId", "block_id"),
                outline_key=_field_value(block, "outlineKey", "outline_key"),
                title=_handout_context_title(block),
                source="current_handout_block" if block is current_block else "adjacent_handout_block",
            )
        )
    return candidates


def _relevant_handout_contexts(
    question: str,
    contexts: Sequence[HandoutContextCandidate],
) -> list[HandoutContextCandidate]:
    relevant = [context for context in contexts if _relevance_score(question, context.content_text) > 0]
    return [
        HandoutContextCandidate(
            rank=index,
            content_text=context.content_text,
            handout_block_id=context.handout_block_id,
            outline_key=context.outline_key,
            title=context.title,
            source=context.source,
        )
        for index, context in enumerate(relevant, start=1)
    ]


def _handout_context_metadata(context: HandoutContextCandidate) -> dict[str, Any]:
    return {
        "handoutBlockId": context.handout_block_id,
        "outlineKey": context.outline_key,
        "title": context.title,
    }


def _rank_document_segments(segments: Sequence[Mapping[str, Any]], question: str) -> list[Mapping[str, Any]]:
    scored: list[tuple[int, int, str, Mapping[str, Any]]] = []
    for segment in segments:
        if segment.get("segmentType") == "video_caption":
            continue
        text = str(segment.get("textContent") or "")
        if not text:
            continue
        score = _relevance_score(question, text)
        scored.append((-score, int(segment.get("orderNo") or 0), str(segment.get("segmentKey") or ""), segment))
    return [item[3] for item in sorted(scored)]


def _normalize_segment(segment: Mapping[str, Any], index: int) -> dict[str, Any]:
    clean_segment = dict(segment)
    clean_segment["segmentKey"] = _stable_key(_field_value(segment, "segmentKey", "segment_key") or f"segment-{index}")
    clean_segment["segmentType"] = str(_field_value(segment, "segmentType", "segment_type") or "")
    clean_segment["resourceType"] = str(_field_value(segment, "resourceType", "resource_type") or "")
    clean_segment["orderNo"] = _as_int(_field_value(segment, "orderNo", "order_no")) or index
    clean_segment["textContent"] = clean_text(
        str(_field_value(segment, "textContent", "text_content", "plainText", "plain_text") or "")
    )
    for camel, snake in (
        ("courseId", "course_id"),
        ("parseRunId", "parse_run_id"),
        ("resourceId", "resource_id"),
        ("segmentId", "segment_id"),
        ("pageNo", "page_no"),
        ("slideNo", "slide_no"),
        ("startSec", "start_sec"),
        ("endSec", "end_sec"),
    ):
        value = _as_int(_field_value(segment, camel, snake))
        if value is not None:
            clean_segment[camel] = value
    anchor_key = _field_value(segment, "anchorKey", "anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        clean_segment["anchorKey"] = clean_text(anchor_key)
    return clean_segment


def _matches_course_parse(segment: Mapping[str, Any], *, course_id: int | None, parse_run_id: int | None) -> bool:
    segment_course_id = _as_positive_int(segment.get("courseId"))
    segment_parse_run_id = _as_positive_int(segment.get("parseRunId"))
    if course_id is not None and segment_course_id != course_id:
        return False
    if parse_run_id is not None and segment_parse_run_id != parse_run_id:
        return False
    return True


def _block_text(block: Mapping[str, Any]) -> str:
    return clean_text(
        "\n".join(
            str(_field_value(block, key, _camel_to_snake(key)) or "")
            for key in ("title", "summary", "contentMd")
        )
    )


def _handout_context_title(block: Mapping[str, Any]) -> str:
    title = clean_text(str(_field_value(block, "title") or ""))
    heading = _first_markdown_heading(_field_value(block, "contentMd", "content_md"))
    if heading and (not title or title in heading):
        return heading
    return title or heading or "讲义块"


def _first_markdown_heading(markdown: Any) -> str:
    for line in str(markdown or "").splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            return clean_text(match.group(1))
    return ""


def _locator(payload: Mapping[str, Any]) -> dict[str, Any]:
    locators: dict[str, Any] = {}
    for key in ("pageNo", "slideNo"):
        value = _as_positive_int(_field_value(payload, key, _camel_to_snake(key)))
        if value is not None:
            locators[key] = value
    anchor_key = _field_value(payload, "anchorKey", "anchor_key")
    if isinstance(anchor_key, str) and anchor_key.strip():
        locators["anchorKey"] = clean_text(anchor_key)
    start_sec = _as_int(_field_value(payload, "startSec", "start_sec"))
    end_sec = _as_int(_field_value(payload, "endSec", "end_sec"))
    if start_sec is not None and end_sec is not None and end_sec > start_sec:
        locators["startSec"] = start_sec
        locators["endSec"] = end_sec
    return locators if _locator_group_count(locators) == 1 else {}


def _locator_group_count(locator: Mapping[str, Any]) -> int:
    groups = 0
    groups += 1 if "pageNo" in locator else 0
    groups += 1 if "slideNo" in locator else 0
    groups += 1 if "anchorKey" in locator else 0
    groups += 1 if "startSec" in locator and "endSec" in locator else 0
    return groups


def _locator_tuple(locator: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple((key, locator[key]) for key in ("pageNo", "slideNo", "anchorKey", "startSec", "endSec") if key in locator)


def _locator_key(locator: Mapping[str, Any]) -> str:
    return "-".join(f"{key}-{value}" for key, value in _locator_tuple(locator))


def _segment_label(segment: Mapping[str, Any], *, locator: Mapping[str, Any]) -> str:
    if "startSec" in locator and "endSec" in locator:
        return f"视频 {int(locator['startSec']):02d}s-{int(locator['endSec']):02d}s"
    if "pageNo" in locator:
        return f"PDF 第 {int(locator['pageNo'])} 页"
    if "slideNo" in locator:
        return f"PPT 第 {int(locator['slideNo'])} 页"
    if "anchorKey" in locator:
        title = clean_text(str(segment.get("title") or ""))
        return title or "文档片段"
    return "课程片段"


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [clean_text(str(item)) for item in value if clean_text(str(item))]


def _source_segment_keys(block: Mapping[str, Any]) -> list[str]:
    return _string_list(_field_value(block, "sourceSegmentKeys", "source_segment_keys"))


def _keywords(text: str) -> set[str]:
    normalized = clean_text(text).lower()
    tokens = set(re.findall(r"[A-Za-z0-9_]{3,}", normalized))
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    for run in cjk_runs:
        if len(run) == 1:
            tokens.add(run)
            continue
        tokens.update(run[index : index + 2] for index in range(0, len(run) - 1))
    stopwords = {"什么", "如何", "怎么", "哪些", "是否", "以及", "这个", "那个", "问题", "联系"}
    return {token for token in tokens if len(token) >= 1 and token not in stopwords}


def _relevant_candidates(question: str, candidates: Sequence[QaEvidenceCandidate]) -> list[QaEvidenceCandidate]:
    relevant = [candidate for candidate in candidates if _relevance_score(question, candidate.content_text) > 0]
    return [_replace_rank(candidate, index) for index, candidate in enumerate(relevant, start=1)]


def _relevance_score(question: str, text: str) -> int:
    keywords = _keywords(question)
    if not keywords:
        return 0
    compact = clean_text(text).lower()
    return sum(1 for keyword in keywords if keyword in compact)


def _replace_rank(candidate: QaEvidenceCandidate, rank: int) -> QaEvidenceCandidate:
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
    )


def _field_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _camel_to_snake(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _stable_key(value: Any, fallback: str = "item") -> str:
    key = re.sub(r"[^a-zA-Z0-9._:-]+", "-", str(value or "")).strip("-._:")
    if not key or not re.match(r"^[a-zA-Z0-9]", key):
        return fallback
    return key


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_positive_int(value: Any) -> int | None:
    parsed = _as_int(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _truncate(text: str, max_chars: int) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def _build_qa_prompt(question: str, candidates: Sequence[QaEvidenceCandidate], *, max_content_chars: int = 800) -> str:
    evidence = [
        {
            "candidateKey": candidate.candidate_key,
            "source": candidate.source,
            "rank": candidate.rank,
            "resourceId": candidate.resource_id,
            "segmentId": candidate.segment_id,
            "segmentKey": candidate.segment_key,
            "refLabel": candidate.ref_label,
            "locator": candidate.locator,
            "textContent": _truncate(candidate.content_text, max_content_chars),
        }
        for candidate in candidates
    ]
    return "\n".join(
        [
            f"用户问题：{clean_text(question)}",
            "请只基于 evidenceCandidates 回答，并只引用 evidenceCandidates 内的候选。",
            f"evidenceCandidates：{json.dumps(evidence, ensure_ascii=False, sort_keys=True)}",
        ]
    )


def _build_unreferenced_qa_prompt(
    question: str,
    *,
    context_text: str,
    evidence_tier: UnreferencedEvidenceTier,
    course_scope: Mapping[str, Any] | None = None,
    max_context_chars: int = 1600,
) -> str:
    payload: dict[str, Any] = {
        "question": clean_text(question),
        "evidenceTier": evidence_tier,
        "contextText": _truncate(context_text, max_context_chars),
        "requiredCitations": [],
    }
    scope_text = _course_scope_text(course_scope)
    if scope_text:
        payload["courseScope"] = _truncate(scope_text, max_context_chars)
    return "\n".join(
        [
            "请基于以下 JSON 输入回答，并保持 citations 为空数组。",
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ]
    )


def _complete_model_json(ai_service: AIService, request: JsonChatRequest, *, label: str) -> dict[str, Any]:
    result = ai_service.complete_json(request)
    if isinstance(result.parsed_json, dict):
        return result.parsed_json
    raise AIOutputParseError(f"{label} JSON must be an object")


def _scoped_vivo_ai_service(
    *,
    app_key: str,
    base_url: str,
    model: str,
    timeout_sec: float,
) -> AIService:
    return AIService(
        json_clients={
            "vivo": OpenAICompatibleJsonClient(
                OpenAICompatibleConfig(
                    api_key=app_key,
                    model=model,
                    base_url=_chat_base_url(base_url),
                    timeout_sec=timeout_sec,
                )
            )
        },
        vision_clients={},
    )


def _scoped_deepseek_ai_service(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_sec: float,
) -> AIService:
    return AIService(
        json_clients={
            "deepseek": DeepSeekLangChainJsonClient(
                DeepSeekLangChainConfig(
                    api_key=api_key,
                    model=model,
                    base_url=_deepseek_base_url(base_url),
                    timeout_sec=timeout_sec,
                )
            )
        },
        vision_clients={},
    )


def _default_ai_service_for_provider(provider: str) -> AIService | None:
    service = get_default_ai_service()
    return service if provider in service.json_clients else None


def _deepseek_base_url(base_url: str) -> str:
    return normalize_deepseek_base_url(base_url) or "https://api.deepseek.com/v1"


def _chat_base_url(base_url: str) -> str:
    clean_url = base_url.rstrip("/")
    if clean_url.endswith("/v1"):
        return clean_url
    return f"{clean_url}/v1"


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
