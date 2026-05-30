from __future__ import annotations

from typing import Any


def test_orchestrator_uses_far_ready_handout_block_as_unreferenced_context():
    from server.ai.qa_orchestrator import QaOrchestrator

    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="当前块只讲候选键。"),
        ready_blocks=[
            _handout_block(block_id=4007, sort_no=7, title="数据库键", content="superkey 是能唯一标识元组的属性集合。")
        ],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(original_segments=[]),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("什么是 superkey？", context)

    assert result.response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert result.response["citations"] == []
    assert result.refs == []


def test_orchestrator_uses_far_original_segment_with_active_course_and_parse_scope():
    from server.ai.qa_orchestrator import QaOrchestrator

    active_course_id = 101
    active_parse_run_id = 9001
    off_course_segment_key = "video-superkey-off-course"
    off_parse_run_segment_key = "video-superkey-off-parse-run"
    valid_segment_key = "video-superkey-7"
    far_segment = _course_segment(
        course_id=active_course_id,
        parse_run_id=active_parse_run_id,
        segment_key=valid_segment_key,
        text="老师在这里说明 superkey 是能够唯一标识关系中元组的属性集合。",
        start_sec=420,
        end_sec=455,
    )
    context = _qa_context(
        active_course_id=active_course_id,
        active_parse_run_id=active_parse_run_id,
        current_block=_handout_block(block_id=4002, sort_no=2, content="当前块只讲候选键。"),
        ready_blocks=[_handout_block(block_id=4007, sort_no=7, content="superkey 是唯一标识元组的属性集合。")],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(
            original_segments=[
                _course_segment(
                    course_id=202,
                    parse_run_id=active_parse_run_id,
                    segment_key=off_course_segment_key,
                    text="另一个课程的 superkey 命中不能进入当前 QA。",
                    start_sec=300,
                    end_sec=330,
                ),
                _course_segment(
                    course_id=active_course_id,
                    parse_run_id=8001,
                    segment_key=off_parse_run_segment_key,
                    text="旧解析版本的 superkey 命中不能进入当前 QA。",
                    start_sec=360,
                    end_sec=390,
                ),
                far_segment,
            ]
        ),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("什么是 superkey？", context)

    assert result.response["generationMetadata"]["evidenceTier"] == "original_evidence"
    assert result.response["citations"]
    assert result.refs
    assert all(ref["courseId"] == active_course_id for ref in result.refs)
    assert all(ref["parseRunId"] == active_parse_run_id for ref in result.refs)
    assert {ref["segmentKey"] for ref in result.refs} == {valid_segment_key}
    assert all("segmentKey" not in citation for citation in result.response["citations"])
    assert off_course_segment_key not in {ref["segmentKey"] for ref in result.refs}
    assert off_parse_run_segment_key not in {ref["segmentKey"] for ref in result.refs}


def test_orchestrator_uses_runtime_hybrid_segment_search_and_preserves_active_handout_scope_for_refs():
    from server.ai.qa_orchestrator import QaOrchestrator
    from server.ai.qa_types import LexicalSearchHit

    repo = _FakeHybridRetrievalRepository(
        lexical_segments=[
            LexicalSearchHit(
                identity_key="segment:8801",
                score=4.0,
                text="superkey uniquely identifies a tuple in a relation.",
                segment_key="video-superkey-hybrid",
                resource_id=501,
                owner_type="segment",
                segment_id=8801,
                course_id=101,
                parse_run_id=9001,
                handout_version_id=None,
                locator={"startSec": 420, "endSec": 455},
            )
        ]
    )
    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="current block only talks about candidate keys."),
        ready_blocks=[],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=repo,
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what is superkey?", context)

    assert repo.lexical_segment_calls == 1
    assert result.response["generationMetadata"]["evidenceTier"] == "original_evidence"
    assert {ref["segmentKey"] for ref in result.refs} == {"video-superkey-hybrid"}
    assert {ref["handoutVersionId"] for ref in result.refs} == {7001}


def test_orchestrator_keeps_semantic_only_original_hits_without_literal_overlap():
    from server.ai.qa_orchestrator import QaOrchestrator
    from server.ai.qa_types import VectorSearchHit

    repo = _FakeHybridRetrievalRepository(
        vector_segments=[
            VectorSearchHit(
                identity_key="segment:8802",
                score=0.92,
                text="A minimal attribute set can identify one tuple in a relation.",
                segment_key="video-superkey-semantic",
                resource_id=501,
                owner_type="segment",
                segment_id=8802,
                course_id=101,
                parse_run_id=9001,
                handout_version_id=None,
                locator={"startSec": 460, "endSec": 490},
            )
        ]
    )
    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="current block only talks about candidate keys."),
        ready_blocks=[],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=repo,
        embedding_client=_FakeEmbeddingClient(),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what is superkey?", context)

    assert repo.vector_segment_calls == 1
    assert result.response["generationMetadata"]["evidenceTier"] == "original_evidence"
    assert {ref["segmentKey"] for ref in result.refs} == {"video-superkey-semantic"}


def test_orchestrator_wrong_query_embedding_dimension_falls_back_to_lexical_search():
    from server.ai.qa_orchestrator import QaOrchestrator
    from server.ai.qa_types import LexicalSearchHit, VectorSearchHit

    repo = _FakeHybridRetrievalRepository(
        vector_segments=[
            VectorSearchHit(
                identity_key="segment:should-not-query",
                score=0.99,
                text="This vector result should not be requested.",
                segment_key="bad-vector",
                resource_id=501,
                owner_type="segment",
                segment_id=8803,
                course_id=101,
                parse_run_id=9001,
                locator={"startSec": 1, "endSec": 2},
            )
        ],
        lexical_segments=[
            LexicalSearchHit(
                identity_key="segment:8804",
                score=4.0,
                text="superkey uniquely identifies tuples.",
                segment_key="video-superkey-lexical",
                resource_id=501,
                owner_type="segment",
                segment_id=8804,
                course_id=101,
                parse_run_id=9001,
                locator={"startSec": 500, "endSec": 530},
            )
        ],
    )
    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="current block only talks about candidate keys."),
        ready_blocks=[],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=repo,
        embedding_client=_WrongDimEmbeddingClient(),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what is superkey?", context)

    assert repo.vector_segment_calls == 0
    assert repo.lexical_segment_calls == 1
    assert {ref["segmentKey"] for ref in result.refs} == {"video-superkey-lexical"}


def test_orchestrator_uses_runtime_hybrid_handout_search_when_context_ready_blocks_are_empty():
    from server.ai.qa_orchestrator import QaOrchestrator
    from server.ai.qa_types import LexicalSearchHit

    repo = _FakeHybridRetrievalRepository(
        lexical_handouts=[
            LexicalSearchHit(
                identity_key="handout:4007",
                score=5.0,
                text="A later handout block explains superkey as a unique identifier.",
                owner_type="handout_block",
                handout_block_id=4007,
                course_id=101,
                parse_run_id=9001,
                handout_version_id=7001,
                metadata_json={"outlineKey": "outline-7", "title": "Database keys"},
            )
        ]
    )
    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="current block only talks about candidate keys."),
        ready_blocks=[],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=repo,
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what is superkey?", context)

    assert repo.lexical_handout_calls == 1
    assert result.response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert result.response["generationMetadata"]["handoutContext"]["handoutBlockId"] == 4007
    assert result.response["citations"] == []
    assert result.refs == []


def test_orchestrator_keeps_semantic_only_handout_hits_without_literal_overlap():
    from server.ai.qa_orchestrator import QaOrchestrator
    from server.ai.qa_types import VectorSearchHit

    repo = _FakeHybridRetrievalRepository(
        vector_handouts=[
            VectorSearchHit(
                identity_key="handout:4010",
                score=0.91,
                text="A later note describes an attribute set that identifies each tuple.",
                owner_type="handout_block",
                handout_block_id=4010,
                course_id=101,
                parse_run_id=9001,
                handout_version_id=7001,
                metadata_json={"outlineKey": "outline-10", "title": "Keys"},
            )
        ]
    )
    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="current block only talks about candidate keys."),
        ready_blocks=[],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=repo,
        embedding_client=_FakeEmbeddingClient(),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what is superkey?", context)

    assert repo.vector_handout_calls == 1
    assert result.response["generationMetadata"]["evidenceTier"] == "handout_context"
    assert result.response["generationMetadata"]["handoutContext"]["handoutBlockId"] == 4010


def test_orchestrator_source_fact_question_does_not_fall_back_to_course_prior_without_original_evidence():
    from server.ai.qa_orchestrator import QaOrchestrator

    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="当前块只讲候选键。"),
        ready_blocks=[
            _handout_block(block_id=4007, sort_no=7, title="数据库键", content="superkey 是能唯一标识元组的属性集合。")
        ],
        course_scope={
            "title": "数据库系统",
            "goalText": "理解候选键、superkey 和函数依赖。",
            "knowledgePointNames": ["superkey", "候选键"],
        },
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(original_segments=[]),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("老师视频里第几分钟讲了 superkey？", context)

    assert result.response["generationMetadata"]["evidenceTier"] != "course_prior"
    assert result.response["citations"] == []
    assert result.refs == []


def test_orchestrator_current_exact_original_evidence_wins_before_far_course_wide_hit():
    from server.ai.qa_orchestrator import QaOrchestrator

    current_exact_segment_key = "video-current-superkey"
    far_segment_key = "video-far-superkey"
    context = _qa_context(
        current_block=_handout_block(
            block_id=4002,
            sort_no=2,
            content="当前块精确说明 superkey 是唯一标识元组的属性集合。",
            citations=[
                {
                    "resourceId": 501,
                    "segmentKey": current_exact_segment_key,
                    "startSec": 120,
                    "endSec": 150,
                    "refLabel": "视频 120s-150s",
                }
            ],
        ),
        current_segments=[
            _course_segment(
                segment_key=current_exact_segment_key,
                text="当前块原始字幕精确说明 superkey 是唯一标识元组的属性集合。",
                start_sec=120,
                end_sec=150,
            )
        ],
        ready_blocks=[_handout_block(block_id=4007, sort_no=7, content="远端块也提到了 superkey。")],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(
            original_segments=[
                _course_segment(
                    segment_key=far_segment_key,
                    text="远端课程级命中同样提到了 superkey。",
                    start_sec=420,
                    end_sec=455,
                )
            ]
        ),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("什么是 superkey？", context)

    assert result.response["generationMetadata"]["evidenceTier"] == "original_evidence"
    assert result.refs
    assert result.response["citations"]
    assert all(ref["segmentKey"] == current_exact_segment_key for ref in result.refs)
    assert all("segmentKey" not in citation for citation in result.response["citations"])
    assert far_segment_key not in {ref["segmentKey"] for ref in result.refs}


def test_orchestrator_unrelated_current_exact_does_not_block_relevant_far_original_evidence():
    from server.ai.qa_orchestrator import QaOrchestrator

    current_exact_segment_key = "video-current-topic"
    far_segment_key = "video-far-superkey"
    context = _qa_context(
        current_block=_handout_block(
            block_id=4002,
            sort_no=2,
            content="current block has an exact original citation",
            citations=[
                {
                    "resourceId": 501,
                    "segmentKey": current_exact_segment_key,
                    "startSec": 120,
                    "endSec": 150,
                    "refLabel": "瑙嗛 120s-150s",
                }
            ],
        ),
        current_segments=[
            _course_segment(
                segment_key=current_exact_segment_key,
                text="superkey uniquely identifies a tuple in a relation.",
                start_sec=120,
                end_sec=150,
            )
        ],
        ready_blocks=[],
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(
            original_segments=[
                _course_segment(
                    segment_key=far_segment_key,
                    text="superkey appears in the far source minute.",
                    start_sec=420,
                    end_sec=455,
                )
            ]
        ),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what source minute mentions superkey?", context)

    assert result.response["generationMetadata"]["evidenceTier"] == "original_evidence"
    assert {ref["segmentKey"] for ref in result.refs} == {far_segment_key}
    assert all("segmentKey" not in citation for citation in result.response["citations"])


def test_orchestrator_empty_ready_blocks_does_not_fallback_to_current_handout_context():
    from server.ai.qa_orchestrator import QaOrchestrator

    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="only-current-handout-token"),
        ready_blocks=[],
        course_scope={"title": "unrelated course scope", "knowledgePointNames": []},
    )
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(original_segments=[]),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("only-current-handout-token", context)

    assert result.response["generationMetadata"]["evidenceTier"] != "handout_context"
    assert result.response["citations"] == []
    assert result.refs == []


def test_orchestrator_rejects_unscoped_course_wide_original_hits():
    from server.ai.qa_orchestrator import QaOrchestrator

    context = _qa_context(
        current_block=_handout_block(block_id=4002, sort_no=2, content="current block has no original evidence"),
        ready_blocks=[],
    )
    unscoped_segment = _course_segment(
        segment_key="video-unscoped-superkey",
        text="superkey appears in an unscoped segment.",
        start_sec=420,
        end_sec=455,
    )
    unscoped_segment.pop("courseId")
    unscoped_segment.pop("parseRunId")
    orchestrator = QaOrchestrator(
        retrieval_repository=_FakeCourseWideRetrievalRepository(original_segments=[unscoped_segment]),
        answer_client=_DeterministicAnswerClient(),
    )

    result = orchestrator.answer("what source minute mentions superkey?", context)

    assert result.response["answerType"] == "insufficient_evidence"
    assert result.response["generationMetadata"]["reason"] == "source_fact_without_original_evidence"
    assert result.response["citations"] == []
    assert result.refs == []


class _FakeCourseWideRetrievalRepository:
    def __init__(self, *, original_segments: list[dict[str, Any]]) -> None:
        self.original_segments = original_segments

    def search_course_wide_original_segments(self, **_: Any) -> list[dict[str, Any]]:
        return self.original_segments

    def search_original_segments(self, **_: Any) -> list[dict[str, Any]]:
        return self.original_segments

    def retrieve_original_evidence(self, **_: Any) -> list[dict[str, Any]]:
        return self.original_segments


class _FakeHybridRetrievalRepository:
    def __init__(
        self,
        *,
        vector_segments: list[Any] | None = None,
        lexical_segments: list[Any] | None = None,
        vector_handouts: list[Any] | None = None,
        lexical_handouts: list[Any] | None = None,
    ) -> None:
        self.vector_segments = vector_segments or []
        self.lexical_segments = lexical_segments or []
        self.vector_handouts = vector_handouts or []
        self.lexical_handouts = lexical_handouts or []
        self.vector_segment_calls = 0
        self.lexical_segment_calls = 0
        self.vector_handout_calls = 0
        self.lexical_handout_calls = 0

    def search_vector_segments(self, *_: Any) -> list[Any]:
        self.vector_segment_calls += 1
        return self.vector_segments

    def search_lexical_segments(self, *_: Any) -> list[Any]:
        self.lexical_segment_calls += 1
        return self.lexical_segments

    def search_vector_handout_blocks(self, *_: Any) -> list[Any]:
        self.vector_handout_calls += 1
        return self.vector_handouts

    def search_lexical_handout_blocks(self, *_: Any) -> list[Any]:
        self.lexical_handout_calls += 1
        return self.lexical_handouts

    def search_course_wide_original_segments(self, **_: Any) -> list[dict[str, Any]]:
        return []


class _FakeEmbeddingClient:
    def embed_texts(self, sentences):
        return [[0.01] * 1536 for _sentence in sentences]


class _WrongDimEmbeddingClient:
    def embed_texts(self, sentences):
        return [[0.01, 0.02] for _sentence in sentences]


class _DeterministicAnswerClient:
    def generate_answer(self, question: str, candidates: list[Any]) -> dict[str, Any]:
        candidate = candidates[0]
        resource_id = _field(candidate, "resource_id", "resourceId")
        ref_label = _field(candidate, "ref_label", "refLabel") or "视频 00s-30s"
        citation = {"resourceId": resource_id, "refLabel": ref_label}
        for key in ("segmentKey", "pageNo", "slideNo", "anchorKey", "startSec", "endSec"):
            value = _field(candidate, key, _camel_to_snake(key))
            if value is not None:
                citation[key] = value
        return {
            "answerMd": f"基于原始证据回答：{question}",
            "answerType": "direct_answer",
            "citations": [citation],
        }

    def generate_unreferenced_answer(
        self,
        question: str,
        *,
        context_text: str,
        evidence_tier: str,
        course_scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "answerMd": f"依据讲义内容回答，未找到可追溯原始资料引用。\n\n{context_text}",
            "answerType": "direct_answer",
            "citations": [],
        }


def _qa_context(
    *,
    current_block: dict[str, Any],
    ready_blocks: list[dict[str, Any]],
    current_segments: list[dict[str, Any]] | None = None,
    active_course_id: int = 101,
    active_parse_run_id: int = 9001,
    active_handout_version_id: int = 7001,
    course_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "activeCourseId": active_course_id,
        "activeParseRunId": active_parse_run_id,
        "activeHandoutVersionId": active_handout_version_id,
        "currentBlock": current_block,
        "readyBlocks": ready_blocks,
        "currentSegments": current_segments or [],
        "courseScope": course_scope
        or {
            "title": "数据库系统",
            "goalText": "理解候选键、superkey 和函数依赖。",
            "knowledgePointNames": ["superkey", "候选键"],
        },
    }


def _handout_block(
    *,
    block_id: int,
    sort_no: int,
    content: str,
    title: str = "数据库键",
    citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "courseId": 101,
        "parseRunId": 9001,
        "handoutVersionId": 7001,
        "handoutBlockId": block_id,
        "outlineKey": f"outline-{sort_no}",
        "sortNo": sort_no,
        "title": title,
        "summary": content,
        "contentMd": f"## {title}\n\n{content}",
        "sourceSegmentKeys": [citation["segmentKey"] for citation in citations or [] if "segmentKey" in citation],
        "knowledgePoints": [{"knowledgePointKey": "kp-superkey", "displayName": "superkey"}],
        "citations": citations or [],
    }


def _course_segment(
    *,
    segment_key: str,
    text: str,
    start_sec: int,
    end_sec: int,
    course_id: int = 101,
    parse_run_id: int = 9001,
    resource_id: int = 501,
) -> dict[str, Any]:
    return {
        "courseId": course_id,
        "parseRunId": parse_run_id,
        "resourceId": resource_id,
        "segmentId": sum(ord(char) for char in segment_key),
        "resourceType": "mp4",
        "segmentKey": segment_key,
        "segmentType": "video_caption",
        "textContent": text,
        "startSec": start_sec,
        "endSec": end_sec,
        "refLabel": f"视频 {start_sec}s-{end_sec}s",
    }


def _field(candidate: Any, *names: str) -> Any:
    for name in names:
        if isinstance(candidate, dict) and name in candidate:
            return candidate[name]
        if hasattr(candidate, name):
            return getattr(candidate, name)
    locator = _field(candidate, "locator")
    if isinstance(locator, dict):
        for name in names:
            if name in locator:
                return locator[name]
    return None


def _camel_to_snake(value: str) -> str:
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in value).lstrip("_")
