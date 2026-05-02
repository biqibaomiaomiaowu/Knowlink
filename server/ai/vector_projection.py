from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from server.parsers.base import clean_text


OwnerType = Literal["segment", "knowledge_point", "handout_block"]


@dataclass(frozen=True)
class VectorDocumentInput:
    owner_type: OwnerType
    owner_id: int | str
    content_text: str
    metadata_json: dict[str, Any]
    course_id: int | None = None
    parse_run_id: int | None = None
    handout_version_id: int | None = None
    resource_id: int | None = None


def segment_to_vector_document(segment: Mapping[str, Any]) -> VectorDocumentInput | None:
    content_text = clean_text(str(segment.get("plainText") or segment.get("plain_text") or segment.get("textContent") or ""))
    if not content_text:
        return None

    locator = _locator(segment)
    if not locator:
        return None

    owner_id = _owner_id(segment, id_key="segmentId", fallback_key="segmentKey")
    metadata = {
        "resourceType": _resource_type(segment),
        "segmentKey": segment.get("segmentKey") or segment.get("segment_key"),
        "segmentType": segment.get("segmentType") or segment.get("segment_type"),
        "title": clean_text(str(segment.get("title") or "")),
        "sectionPath": _section_path(segment.get("sectionPath") or segment.get("section_path")),
        **locator,
    }
    metadata = {
        key: value
        for key, value in metadata.items()
        if value not in (None, "") and (value != [] or (key == "sectionPath" and "sectionPath" in locator))
    }

    return VectorDocumentInput(
        owner_type="segment",
        owner_id=owner_id,
        content_text=content_text,
        metadata_json=metadata,
        course_id=_as_positive_int(segment.get("courseId") or segment.get("course_id")),
        parse_run_id=_as_positive_int(segment.get("parseRunId") or segment.get("parse_run_id")),
        resource_id=_as_positive_int(segment.get("resourceId") or segment.get("resource_id")),
    )


def knowledge_point_to_vector_document(
    knowledge_point: Mapping[str, Any],
    *,
    segment_relations: Sequence[Mapping[str, Any]] | None = None,
    evidences: Sequence[Mapping[str, Any]] | None = None,
) -> VectorDocumentInput | None:
    display_name = clean_text(str(knowledge_point.get("displayName") or knowledge_point.get("display_name") or ""))
    description = clean_text(str(knowledge_point.get("description") or ""))
    aliases = _aliases(knowledge_point.get("aliases"))
    content_text = clean_text("\n".join([display_name, description, "、".join(aliases)]))
    if not content_text:
        return None

    kp_key = str(
        knowledge_point.get("knowledgePointKey")
        or knowledge_point.get("knowledge_point_key")
        or knowledge_point.get("canonicalName")
        or display_name
    )
    segment_keys = _related_segment_keys(segment_relations or [], evidences or [], kp_key=kp_key)
    metadata = {
        "knowledgePointKey": kp_key,
        "canonicalName": clean_text(str(knowledge_point.get("canonicalName") or knowledge_point.get("canonical_name") or display_name)),
        "difficultyLevel": knowledge_point.get("difficultyLevel") or knowledge_point.get("difficulty_level"),
        "importanceScore": knowledge_point.get("importanceScore") or knowledge_point.get("importance_score"),
        "aliases": aliases,
        "segmentKeys": segment_keys,
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}

    return VectorDocumentInput(
        owner_type="knowledge_point",
        owner_id=_owner_id(knowledge_point, id_key="knowledgePointId", fallback_key="knowledgePointKey"),
        content_text=content_text,
        metadata_json=metadata,
        course_id=_as_positive_int(knowledge_point.get("courseId") or knowledge_point.get("course_id")),
        parse_run_id=_as_positive_int(knowledge_point.get("parseRunId") or knowledge_point.get("parse_run_id")),
    )


def handout_block_to_vector_document(block: Mapping[str, Any]) -> VectorDocumentInput | None:
    content_text = clean_text(
        "\n".join(
            [
                str(block.get("title") or ""),
                str(block.get("summary") or ""),
                str(block.get("contentMd") or block.get("content_md") or ""),
            ]
        )
    )
    if not content_text:
        return None

    citations = [citation for citation in block.get("citations", []) if isinstance(citation, Mapping)]
    knowledge_points = [
        item
        for item in block.get("knowledgePoints", []) or block.get("knowledge_points", []) or []
        if isinstance(item, Mapping)
    ]
    metadata = {
        "handoutVersionId": block.get("handoutVersionId") or block.get("handout_version_id"),
        "outlineKey": block.get("outlineKey") or block.get("outline_key"),
        "title": clean_text(str(block.get("title") or "")),
        "sourceSegmentKeys": _string_list(block.get("sourceSegmentKeys") or block.get("source_segment_keys")),
        "citationSegmentKeys": _citation_segment_keys(citations),
        "knowledgePointKeys": _knowledge_point_keys(knowledge_points),
    }
    metadata = {key: value for key, value in metadata.items() if value not in (None, "", [])}

    return VectorDocumentInput(
        owner_type="handout_block",
        owner_id=_owner_id(block, id_key="handoutBlockId", fallback_key="outlineKey"),
        content_text=content_text,
        metadata_json=metadata,
        course_id=_as_positive_int(block.get("courseId") or block.get("course_id")),
        parse_run_id=_as_positive_int(block.get("parseRunId") or block.get("parse_run_id")),
        handout_version_id=_as_positive_int(block.get("handoutVersionId") or block.get("handout_version_id")),
    )


def build_vector_document_inputs(
    *,
    segments: Sequence[Mapping[str, Any]] = (),
    knowledge_extraction: Mapping[str, Any] | None = None,
    handout_block: Mapping[str, Any] | None = None,
) -> list[VectorDocumentInput]:
    output: list[VectorDocumentInput] = []
    for segment in segments:
        item = segment_to_vector_document(segment)
        if item is not None:
            output.append(item)

    if knowledge_extraction:
        relations = knowledge_extraction.get("segmentKnowledgePoints") or []
        evidences = knowledge_extraction.get("knowledgePointEvidences") or []
        for knowledge_point in knowledge_extraction.get("knowledgePoints") or []:
            if not isinstance(knowledge_point, Mapping):
                continue
            item = knowledge_point_to_vector_document(
                knowledge_point,
                segment_relations=relations if isinstance(relations, list) else [],
                evidences=evidences if isinstance(evidences, list) else [],
            )
            if item is not None:
                output.append(item)

    if handout_block is not None:
        item = handout_block_to_vector_document(handout_block)
        if item is not None:
            output.append(item)

    return output


def _locator(payload: Mapping[str, Any]) -> dict[str, Any]:
    locators: dict[str, Any] = {}
    resource_type = _resource_type(payload)
    docx_missing_order_no = False
    if resource_type == "docx":
        order_no = _as_positive_int(_field_value(payload, "orderNo", "order_no"))
        if order_no is not None:
            locators["sectionPath"] = _section_path(_field_value(payload, "sectionPath", "section_path"))
            locators["orderNo"] = order_no
        else:
            docx_missing_order_no = True
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

    if docx_missing_order_no:
        return {}

    groups = 0
    groups += 1 if "sectionPath" in locators or "orderNo" in locators else 0
    groups += 1 if "pageNo" in locators else 0
    groups += 1 if "slideNo" in locators else 0
    groups += 1 if "anchorKey" in locators else 0
    groups += 1 if "startSec" in locators and "endSec" in locators else 0
    return locators if groups == 1 else {}


def _owner_id(payload: Mapping[str, Any], *, id_key: str, fallback_key: str) -> int | str:
    parsed = _as_positive_int(_field_value(payload, id_key, _camel_to_snake(id_key)))
    if parsed is not None:
        return parsed
    return str(_field_value(payload, fallback_key, _camel_to_snake(fallback_key)) or "unknown")


def _resource_type(segment: Mapping[str, Any]) -> str:
    explicit = segment.get("resourceType") or segment.get("resource_type")
    if isinstance(explicit, str) and explicit:
        return explicit
    segment_type = str(segment.get("segmentType") or segment.get("segment_type") or "")
    if segment_type == "video_caption":
        return "mp4"
    if _field_value(segment, "startSec", "start_sec") is not None and _field_value(segment, "endSec", "end_sec") is not None:
        return "mp4"
    if segment_type.startswith("pdf_") or _field_value(segment, "pageNo", "page_no") is not None:
        return "pdf"
    if segment_type.startswith("ppt_") or _field_value(segment, "slideNo", "slide_no") is not None:
        return "pptx"
    return "docx"


def _section_path(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (clean_text(str(item or "")) for item in value) if item]


def _aliases(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (clean_text(str(item or "")) for item in value) if item]


def _related_segment_keys(
    relations: Sequence[Mapping[str, Any]],
    evidences: Sequence[Mapping[str, Any]],
    *,
    kp_key: str,
) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for item in [*relations, *evidences]:
        if not isinstance(item, Mapping):
            continue
        if item.get("knowledgePointKey") != kp_key:
            continue
        segment_key = item.get("segmentKey")
        if isinstance(segment_key, str) and segment_key and segment_key not in seen:
            keys.append(segment_key)
            seen.add(segment_key)
    return keys


def _citation_segment_keys(citations: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        key = citation.get("segmentKey") or citation.get("segment_key")
        if isinstance(key, str) and key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _knowledge_point_keys(knowledge_points: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for item in knowledge_points:
        key = item.get("knowledgePointKey") or item.get("knowledge_point_key")
        if isinstance(key, str) and key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (str(item or "") for item in value) if item]


def _as_positive_int(value: Any) -> int | None:
    parsed = _as_int(value)
    if parsed is None or parsed < 1:
        return None
    return parsed


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _field_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _camel_to_snake(value: str) -> str:
    output = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            output.append("_")
        output.append(char.lower())
    return "".join(output)
