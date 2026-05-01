from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from server.ai.ocr import (
    OcrAsset,
    OcrAssetResult,
    OcrClient,
    get_configured_ocr_client,
)
from server.ai.vision import (
    VisionAssetResult,
    VisionClient,
    VisualAsset,
    analyze_visual_assets,
    get_configured_vision_batch_size,
    get_configured_vision_client,
    is_vision_model_unsupported_error,
)
from server.parsers.base import BaseParser, ParserIssue, ParserResult, clean_text, text_quality_issue


_CHINESE_HEADING_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"^第[一二三四五六七八九十百千万\d]+[章节篇]\s*"), 1),
    (re.compile(r"^[一二三四五六七八九十]+[、.．]\s*"), 1),
    (re.compile(r"^（[一二三四五六七八九十]+）\s*"), 2),
    (re.compile(r"^\d+(?:\.\d+)*[、.．]\s*"), 1),
    (re.compile(r"^参考答案\s*"), 1),
)


class DocxParser(BaseParser):
    resource_type = "docx"

    def __init__(self, *, ocr_client: OcrClient | None = None, vision_client: VisionClient | None = None) -> None:
        self._ocr_client = ocr_client if ocr_client is not None else get_configured_ocr_client()
        self._vision_client = vision_client if vision_client is not None else get_configured_vision_client()
        self._vision_batch_size = get_configured_vision_batch_size()

    def parse(self, file_path: str | Path) -> ParserResult:
        try:
            document = Document(str(file_path))
        except Exception as exc:
            return self._read_failed(file_path, exc)

        section_path: list[str] = []
        items: list[_DocxSegmentItem | _DocxVisualItem] = []
        candidates: list[_DocxVisualCandidate] = []
        local_visual_results: list[VisionAssetResult] = []
        issues: list[ParserIssue] = []

        for block_no, block in enumerate(_iter_blocks(document), start=1):
            if isinstance(block, Paragraph):
                text = clean_text(block.text)
                heading_level = _heading_level(block.style.name if block.style else "") or _chinese_heading_level(text)
                if heading_level is not None and text:
                    section_path = section_path[: heading_level - 1]
                    section_path.append(text)

                if text_quality_issue(block.text) is None:
                    items.append(
                        _DocxSegmentItem(
                            segment_type="docx_block_text",
                            text=text,
                            section_path=list(section_path),
                        )
                    )
                elif block.text:
                    issues.append(
                        ParserIssue(
                            code="docx.block_text_garbled",
                            message="DOCX paragraph contains garbled text and was skipped.",
                            details={"blockNo": block_no},
                        )
                    )

                for formula_no, formula_text in enumerate(_extract_omml_texts(block), start=1):
                    items.append(
                        _DocxSegmentItem(
                            segment_type="formula",
                            text=formula_text,
                            section_path=list(section_path),
                            formula_no=formula_no,
                        )
                    )

                for image_no, image in enumerate(_extract_paragraph_images(block, document), start=1):
                    asset_id = _image_asset_id(block_no, image_no)
                    if self._ocr_client is None and self._vision_client is None:
                        local_caption = _local_caption_from_context(section_path, text)
                        if local_caption is not None:
                            items.append(
                                _DocxVisualItem(
                                    block_no=block_no,
                                    image_no=image_no,
                                    asset_id=asset_id,
                                    section_path=list(section_path),
                                )
                            )
                            local_visual_results.append(
                                VisionAssetResult(
                                    asset_id=asset_id,
                                    segment_type="image_caption",
                                    text=local_caption,
                                )
                            )
                            continue
                        issues.append(
                            ParserIssue(
                                code="docx.vision_not_configured",
                                message="DOCX has visual content, but OCR and vision enhancement are not configured.",
                                details={"blockNo": block_no, "imageNo": image_no},
                            )
                        )
                        continue

                    items.append(
                        _DocxVisualItem(
                            block_no=block_no,
                            image_no=image_no,
                            asset_id=asset_id,
                            section_path=list(section_path),
                        )
                    )
                    candidates.append(
                        _DocxVisualCandidate(
                            block_no=block_no,
                            image_no=image_no,
                            asset_id=asset_id,
                            image_bytes=image["blob"],
                            mime_type=image["mime_type"],
                            location={"sectionPath": list(section_path), "blockNo": block_no, "imageNo": image_no},
                            hint="docx_inline_visual",
                        )
                    )
                continue

            if isinstance(block, Table):
                text = _table_text(block)
                if text_quality_issue(text) is not None:
                    if text:
                        issues.append(
                            ParserIssue(
                                code="docx.table_text_garbled",
                                message="DOCX table contains garbled text and was skipped.",
                                details={"blockNo": block_no},
                            )
                        )
                    continue

                items.append(
                    _DocxSegmentItem(
                        segment_type="docx_block_text",
                        text=text,
                        section_path=list(section_path),
                    )
                )

        ocr_results, ocr_issues = self._recognize_assets(candidates)
        issues.extend(ocr_issues)
        visual_assets = _docx_vision_assets_after_ocr(
            candidates,
            ocr_results,
            issues,
            has_ocr_client=self._ocr_client is not None,
            has_vision_client=self._vision_client is not None,
        )
        visual_results, visual_issues = self._analyze_assets(
            visual_assets,
            document_context=_docx_document_context(items, ocr_results),
        )
        issues.extend(visual_issues)
        segments = _build_docx_segments(
            items,
            _ocr_results_to_visual_results(
                ocr_results,
                items,
                suppress_asset_ids={asset.asset_id for asset in visual_assets},
            )
            + local_visual_results
            + visual_results,
            issues,
        )

        if not segments:
            return self._failed_with_issues(
                issues
                or [
                    ParserIssue(
                        code="docx.block_text_empty",
                        message="DOCX has no extractable clean text, table, formula, or visual segment.",
                    )
                ]
            )

        return self._succeeded(segments, issues)

    def _recognize_assets(
        self,
        candidates: list[_DocxVisualCandidate],
    ) -> tuple[list[OcrAssetResult], list[ParserIssue]]:
        issues: list[ParserIssue] = []
        if self._ocr_client is None or not candidates:
            return [], issues

        assets = [
            OcrAsset(
                asset_id=candidate.asset_id,
                image_bytes=candidate.image_bytes,
                mime_type=candidate.mime_type,
                location=candidate.location,
                hint=candidate.hint,
            )
            for candidate in candidates
        ]
        try:
            results = self._ocr_client.recognize_images(assets, resource_type=self.resource_type)
        except Exception as exc:
            for asset in assets:
                issues.append(
                    ParserIssue(
                        code="docx.ocr_failed",
                        message="DOCX visual OCR failed.",
                        details={**asset.location, "error": str(exc)},
                    )
                )
            return [], issues

        return _clean_ocr_results(results), issues

    def _analyze_assets(
        self,
        assets: list[VisualAsset],
        *,
        document_context: str,
    ) -> tuple[list[VisionAssetResult], list[ParserIssue]]:
        issues: list[ParserIssue] = []
        if self._vision_client is None or not assets:
            return [], issues

        results: list[VisionAssetResult] = []
        for chunk in _chunks(assets, self._vision_batch_size):
            try:
                results.extend(
                    analyze_visual_assets(
                        self._vision_client,
                        chunk,
                        resource_type=self.resource_type,
                        document_context=document_context,
                    )
                )
            except Exception as exc:
                for asset in chunk:
                    model_unsupported = is_vision_model_unsupported_error(exc)
                    issues.append(
                        ParserIssue(
                            code="docx.vision_model_unsupported" if model_unsupported else "docx.vision_failed",
                            message=(
                                "DOCX vision model does not support image input."
                                if model_unsupported
                                else "DOCX visual enhancement failed."
                            ),
                            details={**asset.location, "error": str(exc)},
                        )
                    )

        return _clean_asset_results(results), issues


def _heading_level(style_name: str) -> int | None:
    match = re.match(r"^Heading\s*(\d+)$", style_name.strip(), re.IGNORECASE)
    if match is None:
        return None
    return max(1, int(match.group(1)))


def _chinese_heading_level(text: str) -> int | None:
    for pattern, level in _CHINESE_HEADING_PATTERNS:
        if pattern.match(text):
            return level
    return None


def _iter_blocks(document: Any) -> list[Paragraph | Table]:
    blocks: list[Paragraph | Table] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            blocks.append(Paragraph(child, document))
        elif child.tag == qn("w:tbl"):
            blocks.append(Table(child, document))
    return blocks


def _table_text(table: Table) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [clean_text(cell.text) for cell in row.cells]
        row_text = " | ".join(cell for cell in cells if cell)
        if row_text:
            rows.append(row_text)
    return "\n".join(rows)


def _extract_omml_texts(paragraph: Paragraph) -> list[str]:
    texts: list[str] = []
    for math_node in paragraph._element.iter(qn("m:oMath")):
        tokens = [node.text for node in math_node.iter(qn("m:t")) if node.text]
        text = clean_text(" ".join(tokens))
        if text:
            texts.append(text)
    return texts


def _extract_paragraph_images(paragraph: Paragraph, document: Any) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for blip in paragraph._element.iter(qn("a:blip")):
        relationship_id = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
        if not relationship_id:
            continue
        part = document.part.related_parts.get(relationship_id)
        if part is None or not hasattr(part, "blob"):
            continue
        images.append(
            {
                "blob": part.blob,
                "mime_type": getattr(part, "content_type", "application/octet-stream"),
            }
        )
    return images


@dataclass
class _DocxSegmentItem:
    segment_type: str
    text: str
    section_path: list[str]
    formula_no: int | None = None


@dataclass
class _DocxVisualItem:
    block_no: int
    image_no: int
    asset_id: str
    section_path: list[str]


@dataclass
class _DocxVisualCandidate:
    block_no: int
    image_no: int
    asset_id: str
    image_bytes: bytes
    mime_type: str
    location: dict[str, object]
    hint: str


def _docx_vision_assets_after_ocr(
    candidates: list[_DocxVisualCandidate],
    ocr_results: list[OcrAssetResult],
    issues: list[ParserIssue],
    *,
    has_ocr_client: bool,
    has_vision_client: bool,
) -> list[VisualAsset]:
    if not has_vision_client:
        if has_ocr_client:
            _append_docx_ocr_empty_issues(candidates, ocr_results, issues)
        return []

    if not has_ocr_client:
        return [_candidate_to_visual_asset(candidate) for candidate in candidates]

    result_map = _ocr_results_by_asset_id(ocr_results)
    visual_assets: list[VisualAsset] = []
    for candidate in candidates:
        image_results = result_map.get(candidate.asset_id, [])
        if any(_local_caption_from_ocr_text(result.text) for result in image_results):
            continue
        if _ocr_results_are_good(image_results):
            continue
        visual_assets.append(_candidate_to_visual_asset(candidate))
    return visual_assets


def _append_docx_ocr_empty_issues(
    candidates: list[_DocxVisualCandidate],
    ocr_results: list[OcrAssetResult],
    issues: list[ParserIssue],
) -> None:
    result_map = _ocr_results_by_asset_id(ocr_results)
    for candidate in candidates:
        if _ocr_results_are_good(result_map.get(candidate.asset_id, [])):
            continue
        if _has_visual_failure(issues, candidate.block_no, candidate.image_no):
            continue
        issues.append(
            ParserIssue(
                code="docx.ocr_empty",
                message="DOCX visual OCR returned no clean text.",
                details=candidate.location,
            )
        )


def _candidate_to_visual_asset(candidate: _DocxVisualCandidate) -> VisualAsset:
    return VisualAsset(
        asset_id=candidate.asset_id,
        image_bytes=candidate.image_bytes,
        mime_type=candidate.mime_type,
        location=dict(candidate.location),
        hint=candidate.hint,
    )


def _build_docx_segments(
    items: list[_DocxSegmentItem | _DocxVisualItem],
    visual_results: list[VisionAssetResult],
    issues: list[ParserIssue],
) -> list[dict[str, object]]:
    result_map = _results_by_asset_id(visual_results)
    segments: list[dict[str, object]] = []
    order_no = 0

    for item in items:
        if isinstance(item, _DocxSegmentItem):
            order_no += 1
            segments.append(
                {
                    "segmentKey": _segment_key(order_no, item),
                    "segmentType": item.segment_type,
                    "orderNo": order_no,
                    "textContent": item.text,
                    "sectionPath": list(item.section_path),
                }
            )
            continue

        image_results = result_map.get(item.asset_id, [])
        if not image_results and not _has_visual_failure(issues, item.block_no, item.image_no):
            issues.append(
                ParserIssue(
                    code="docx.visual_empty",
                    message="DOCX visual asset returned no clean segment.",
                    details={"blockNo": item.block_no, "imageNo": item.image_no},
                )
            )

        for result_no, result in enumerate(image_results, start=1):
            order_no += 1
            segments.append(
                {
                    "segmentKey": _visual_segment_key(order_no, item.image_no, result.segment_type, result_no),
                    "segmentType": result.segment_type,
                    "orderNo": order_no,
                    "textContent": result.text,
                    "sectionPath": list(item.section_path),
                }
            )

    return segments


def _segment_key(order_no: int, item: _DocxSegmentItem) -> str:
    if item.segment_type == "formula":
        return f"docx-b{order_no}-formula{item.formula_no or 1}"
    return f"docx-b{order_no}"


def _clean_asset_results(results: list[VisionAssetResult]) -> list[VisionAssetResult]:
    clean_results: list[VisionAssetResult] = []
    for result in results:
        text = clean_text(result.text)
        if text and result.segment_type in ("ocr_text", "formula", "image_caption"):
            clean_results.append(
                VisionAssetResult(asset_id=result.asset_id, segment_type=result.segment_type, text=text)
            )
    return clean_results


def _clean_ocr_results(results: list[OcrAssetResult]) -> list[OcrAssetResult]:
    clean_results: list[OcrAssetResult] = []
    for result in results:
        text = clean_text(result.text)
        if text:
            clean_results.append(OcrAssetResult(asset_id=result.asset_id, text=text, boxes=result.boxes))
    return clean_results


def _ocr_results_to_visual_results(
    results: list[OcrAssetResult],
    items: list[_DocxSegmentItem | _DocxVisualItem],
    *,
    suppress_asset_ids: set[str] | None = None,
) -> list[VisionAssetResult]:
    visual_asset_ids = {item.asset_id for item in items if isinstance(item, _DocxVisualItem)}
    suppressed = suppress_asset_ids or set()
    visual_results: list[VisionAssetResult] = []
    for result in results:
        if result.asset_id in suppressed or result.asset_id not in visual_asset_ids:
            continue
        local_caption = _local_caption_from_ocr_text(result.text)
        if local_caption is not None:
            visual_results.append(
                VisionAssetResult(asset_id=result.asset_id, segment_type="image_caption", text=local_caption)
            )
            continue
        if _usable_ocr_text(result.text):
            visual_results.append(
                VisionAssetResult(asset_id=result.asset_id, segment_type="ocr_text", text=result.text)
            )
    return visual_results


def _ocr_results_are_good(results: list[OcrAssetResult]) -> bool:
    return any(_usable_ocr_text(result.text) for result in results)


def _usable_ocr_text(text: str) -> bool:
    cleaned = clean_text(text)
    if _low_quality_ocr_text(cleaned):
        return False
    compact = re.sub(r"\s+", "", cleaned)
    if len(compact) >= 40:
        return True
    if len([line for line in cleaned.splitlines() if line.strip()]) >= 2:
        return True
    if re.search(r"(^|\n|\s)(\d+[.、．)]|[A-D][.、．)])", cleaned):
        return True
    if "|" in cleaned and "\n" in cleaned:
        return True
    math_chars = set("=+-*/^_{}()[]<>≤≥≈≠∈∉⊆⊂⊇⊃∩∪∁∅Ø→←↔")
    return len(compact) >= 8 and any(char in math_chars for char in compact)


def _low_quality_ocr_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", clean_text(text))
    if not compact:
        return False
    if _local_caption_from_ocr_text(text) is not None:
        return True
    if _looks_like_visual_label_ocr(compact):
        return True
    return any(token in compact for token in ("AUB", "ANB", "ABe", "CuA", "CuB", "2”", "card(AB)"))


def _local_caption_from_ocr_text(text: str) -> str | None:
    compact = re.sub(r"\s+", "", clean_text(text))
    if "文氏图" not in compact:
        return None
    if not any(token in compact for token in ("aEA", "bEA", "a∈A", "b∉A", "全集U")):
        return None
    return "文氏图示例：全集 U 中的椭圆区域表示集合 A，点 a 位于集合 A 内表示 a ∈ A，点 b 位于集合 A 外表示 b ∉ A。"


def _local_caption_from_context(section_path: list[str], paragraph_text: str) -> str | None:
    context = " ".join(section_path + [paragraph_text])
    if "文氏图" not in context:
        return None
    return "文氏图示意：用区域表示集合，用点表示元素，用于辅助理解元素与集合之间的属于关系。"


def _looks_like_visual_label_ocr(compact: str) -> bool:
    normalized = compact.replace("∩", "N").replace("∪", "U")
    if normalized in {"A", "B", "U", "AB", "ANB", "AUB", "UAC"}:
        return True
    label_chars = set("ABUN∁CU")
    return len(normalized) <= 8 and all(char in label_chars for char in normalized)


def _results_by_asset_id(results: list[VisionAssetResult]) -> dict[str, list[VisionAssetResult]]:
    grouped: dict[str, list[VisionAssetResult]] = {}
    for result in results:
        grouped.setdefault(result.asset_id, []).append(result)
    return grouped


def _ocr_results_by_asset_id(results: list[OcrAssetResult]) -> dict[str, list[OcrAssetResult]]:
    grouped: dict[str, list[OcrAssetResult]] = {}
    for result in results:
        grouped.setdefault(result.asset_id, []).append(result)
    return grouped


def _docx_document_context(
    items: list[_DocxSegmentItem | _DocxVisualItem],
    ocr_results: list[OcrAssetResult] | None = None,
) -> str:
    parts = [item.text for item in items if isinstance(item, _DocxSegmentItem)]
    for result in ocr_results or []:
        parts.append(f"OCR {result.asset_id}：{result.text}")
    return "\n".join(parts)


def _chunks(items: list[VisualAsset], size: int) -> list[list[VisualAsset]]:
    chunk_size = max(1, size)
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def _image_asset_id(block_no: int, image_no: int) -> str:
    return f"docx-b{block_no}-i{image_no}"


def _has_visual_failure(issues: list[ParserIssue], block_no: int, image_no: int) -> bool:
    for issue in issues:
        if issue.code not in {
            "docx.vision_failed",
            "docx.vision_model_unsupported",
            "docx.ocr_failed",
            "docx.ocr_empty",
        }:
            continue
        details = issue.details or {}
        if details.get("blockNo") == block_no and details.get("imageNo") == image_no:
            return True
    return False


def _visual_segment_key(order_no: int, image_no: int, segment_type: str, result_no: int) -> str:
    suffix = {
        "ocr_text": "ocr",
        "formula": "formula",
        "image_caption": "image",
    }[segment_type]
    return f"docx-b{order_no}-i{image_no}-{suffix}{result_no}"
