import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from server.ai.asr import AsrSegment
from server.ai.handout_block import generate_handout_block
from server.ai.handout_lazy import build_handout_outline_from_captions
from server.ai.knowledge_extraction import handout_block_to_knowledge_extraction
from server.ai.vector_projection import build_vector_document_inputs
from server.parsers import parse_resource


ROOT = Path(__file__).resolve().parents[2]
HANDOUT_BLOCK_VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "schemas/ai/handout_block.schema.json").read_text(encoding="utf-8"))
)
KNOWLEDGE_VALIDATOR = Draft202012Validator(
    json.loads((ROOT / "schemas/ai/knowledge_point_extraction.schema.json").read_text(encoding="utf-8"))
)


class FakeAsrClient:
    def transcribe(self, file_path):
        return [
            AsrSegment(text="今天我们学习集合的基本概念。", start_sec=0, end_sec=24),
            AsrSegment(text="集合由确定的对象组成，对象叫元素。", start_sec=24, end_sec=48),
            AsrSegment(text="接下来用文氏图理解集合之间的关系。", start_sec=48, end_sec=72),
        ]


def test_real_assets_can_build_no_db_handout_block_flow(monkeypatch):
    asset_dir = ROOT / "local_assets/first-edition/what-is-set"
    parse_inputs = [
        ("mp4", asset_dir / "knowlink-demo-main.mp4", 1),
        ("pdf", asset_dir / "knowlink-demo-handout.pdf", 2),
        ("pptx", asset_dir / "knowlink-demo-slides.pptx", 3),
        ("docx", asset_dir / "knowlink-demo-docx.docx", 4),
    ]
    if not all(path.exists() for _, path, _ in parse_inputs):
        pytest.skip("Local first-edition what-is-set assets are not available.")

    monkeypatch.setattr("server.parsers.video.get_configured_asr_client", lambda: FakeAsrClient())
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)

    all_segments = []
    for resource_type, path, resource_id in parse_inputs:
        result = parse_resource(resource_type, path)
        assert result.status == "succeeded"
        assert result.normalized_document is not None
        all_segments.extend(_enrich_segments(result.normalized_document["segments"], resource_type, resource_id))

    video_segments = [segment for segment in all_segments if segment["segmentType"] == "video_caption"]
    outline = build_handout_outline_from_captions(video_segments, max_block_duration_sec=60)
    block = generate_handout_block(outline["items"][0], all_segments)
    extraction = handout_block_to_knowledge_extraction(block, all_segments)
    vector_inputs = build_vector_document_inputs(
        segments=all_segments,
        knowledge_extraction=extraction,
        handout_block=block,
    )

    HANDOUT_BLOCK_VALIDATOR.validate(block)
    KNOWLEDGE_VALIDATOR.validate(extraction)
    assert {item.owner_type for item in vector_inputs} == {"segment", "knowledge_point", "handout_block"}
    assert all(item.content_text for item in vector_inputs)
    segment_vectors = [item for item in vector_inputs if item.owner_type == "segment"]
    assert len(segment_vectors) == len(all_segments)


def _enrich_segments(segments, resource_type: str, resource_id: int):
    enriched = []
    for index, segment in enumerate(segments, start=1):
        item = dict(segment)
        item["resourceType"] = resource_type
        item["resourceId"] = resource_id
        item["segmentId"] = resource_id * 1000 + index
        enriched.append(item)
    return enriched
