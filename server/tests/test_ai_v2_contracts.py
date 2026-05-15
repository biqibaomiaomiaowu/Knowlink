from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

from server.ai import v2
from server.ai.v2.graph import AIGraphDraft, AIGraphEdge, AIGraphNode
from server.ai.v2.grading import AIGradingCriterion, AIGradingRequest
from server.ai.v2.parsing import ParsingEnhancementRequest, ParsingEnhancementResult
from server.ai.v2.streaming import AIStreamEnvelope, StreamEventSink
from server.ai.v2.video_frames import (
    VideoFrameCandidate,
    VideoFrameExtractionRequest,
    VideoFrameExtractionResult,
)


V2_MODULE_PATHS = [
    Path("server/ai/v2/__init__.py"),
    Path("server/ai/v2/graph.py"),
    Path("server/ai/v2/grading.py"),
    Path("server/ai/v2/parsing.py"),
    Path("server/ai/v2/streaming.py"),
    Path("server/ai/v2/video_frames.py"),
]


def test_graph_contract_dataclasses_can_be_constructed() -> None:
    node = AIGraphNode(key="concept-1", kind="concept", metadata={"title": "Intro"})
    edge = AIGraphEdge(
        source_key="concept-1",
        target_key="concept-2",
        relation="prerequisite",
        metadata={"weight": 0.8},
    )
    draft = AIGraphDraft(nodes=[node], edges=[edge])

    assert draft.nodes == [node]
    assert draft.edges == [edge]


def test_grading_contract_dataclasses_can_be_constructed() -> None:
    criterion = AIGradingCriterion(key="accuracy", label="Accuracy", max_score=10)
    request = AIGradingRequest(
        answer_text="Paris is the capital of France.",
        criteria=[criterion],
        metadata={"locale": "en-US"},
    )

    assert request.answer_text.startswith("Paris")
    assert request.criteria == [criterion]


def test_streaming_contract_dataclass_and_protocol() -> None:
    event = AIStreamEnvelope(kind="token", text="hello", payload={"index": 1})
    emit_hints = get_type_hints(StreamEventSink.emit)

    assert event.kind == "token"
    assert event.text == "hello"
    assert event.payload == {"index": 1}
    assert emit_hints["event"] is AIStreamEnvelope
    assert emit_hints["return"] is type(None)


def test_parsing_contract_dataclasses_can_be_constructed() -> None:
    request = ParsingEnhancementRequest(
        resource_id="res_1",
        segment_text="raw segment",
        context="neighboring content",
        metadata={"source": "pdf"},
    )
    result = ParsingEnhancementResult(
        enhanced_text="enhanced segment",
        confidence=0.91,
        issues=("low_contrast",),
    )

    assert request.context == "neighboring content"
    assert result.confidence == 0.91
    assert result.issues == ("low_contrast",)


def test_video_frame_contract_dataclasses_can_be_constructed() -> None:
    frame = VideoFrameCandidate(timestamp_sec=12.5, image_bytes=b"png")
    request = VideoFrameExtractionRequest(
        video_path=Path("/tmp/input.mp4"),
        sample_interval_sec=5,
        max_frames=3,
        metadata={"strategy": "uniform"},
    )
    result = VideoFrameExtractionResult(frames=[frame])

    assert frame.mime_type == "image/png"
    assert request.video_path == Path("/tmp/input.mp4")
    assert result.frames == [frame]
    assert result.issues == ()


@pytest.mark.parametrize(
    "instance, field_name, value",
    [
        (AIGraphNode(key="node", kind="concept"), "key", "other"),
        (AIGraphEdge(source_key="a", target_key="b", relation="rel"), "relation", "other"),
        (AIGraphDraft(nodes=(), edges=()), "nodes", ()),
        (AIGradingCriterion(key="score", label="Score", max_score=1), "max_score", 2),
        (AIGradingRequest(answer_text="answer", criteria=()), "answer_text", "other"),
        (AIStreamEnvelope(kind="token"), "kind", "done"),
        (ParsingEnhancementRequest(resource_id="r", segment_text="text"), "context", "other"),
        (ParsingEnhancementResult(enhanced_text="text", confidence=1), "confidence", 0),
        (VideoFrameCandidate(timestamp_sec=0, image_bytes=b""), "mime_type", "image/jpeg"),
        (
            VideoFrameExtractionRequest(video_path="video.mp4", sample_interval_sec=1, max_frames=1),
            "max_frames",
            2,
        ),
        (VideoFrameExtractionResult(frames=()), "issues", ("issue",)),
    ],
)
def test_contract_dataclasses_are_frozen(instance: object, field_name: str, value: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, field_name, value)


@pytest.mark.parametrize(
    "factory, attribute",
    [
        (lambda: AIGraphNode(key="node", kind="concept"), "metadata"),
        (lambda: AIGraphEdge(source_key="a", target_key="b", relation="rel"), "metadata"),
        (lambda: AIGradingRequest(answer_text="answer", criteria=()), "metadata"),
        (lambda: AIStreamEnvelope(kind="token"), "payload"),
        (lambda: ParsingEnhancementRequest(resource_id="r", segment_text="text"), "metadata"),
        (lambda: VideoFrameCandidate(timestamp_sec=0, image_bytes=b""), "metadata"),
        (
            lambda: VideoFrameExtractionRequest(
                video_path="video.mp4",
                sample_interval_sec=1,
                max_frames=1,
            ),
            "metadata",
        ),
    ],
)
def test_mutable_defaults_are_not_shared(factory: object, attribute: str) -> None:
    first = factory()
    second = factory()

    getattr(first, attribute)["request_id"] = "first"

    assert getattr(second, attribute) == {}


def test_init_exports_v2_contract_types() -> None:
    expected_exports = {
        "AIGraphDraft",
        "AIGraphEdge",
        "AIGraphNode",
        "AIGradingCriterion",
        "AIGradingRequest",
        "AIStreamEnvelope",
        "ParsingEnhancementRequest",
        "ParsingEnhancementResult",
        "StreamEventSink",
        "VideoFrameCandidate",
        "VideoFrameExtractionRequest",
        "VideoFrameExtractionResult",
    }

    assert set(v2.__all__) == expected_exports
    for name in expected_exports:
        assert getattr(v2, name) is globals()[name]


def test_sequence_annotations_are_preserved_for_collection_contracts() -> None:
    graph_hints = get_type_hints(AIGraphDraft)
    grading_hints = get_type_hints(AIGradingRequest)
    video_hints = get_type_hints(VideoFrameExtractionResult)

    assert get_args(graph_hints["nodes"])[0] is AIGraphNode
    assert get_args(graph_hints["edges"])[0] is AIGraphEdge
    assert get_args(grading_hints["criteria"])[0] is AIGradingCriterion
    assert get_args(video_hints["frames"])[0] is VideoFrameCandidate


def test_v2_contract_modules_do_not_import_business_services_or_providers() -> None:
    forbidden_modules = (
        "server.ai.service",
        "server.ai.pipelines",
        "server.ai.providers",
        "server.services",
    )

    for path in V2_MODULE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)

        assert not any(
            imported_module == forbidden_module or imported_module.startswith(f"{forbidden_module}.")
            for imported_module in imported_modules
            for forbidden_module in forbidden_modules
        ), f"{path} imports business/service/provider module: {imported_modules}"
