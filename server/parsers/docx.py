from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from server.ai.vision import VisionClient, VisionResult, get_configured_vision_client
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

    def __init__(self, *, vision_client: VisionClient | None = None) -> None:
        self._vision_client = vision_client if vision_client is not None else get_configured_vision_client()

    def parse(self, file_path: str | Path) -> ParserResult:
        try:
            document = Document(str(file_path))
        except Exception as exc:
            return self._read_failed(file_path, exc)

        order_no = 0
        section_path: list[str] = []
        segments: list[dict[str, object]] = []
        issues: list[ParserIssue] = []

        for block_no, block in enumerate(_iter_blocks(document), start=1):
            if isinstance(block, Paragraph):
                text = clean_text(block.text)
                heading_level = _heading_level(block.style.name if block.style else "") or _chinese_heading_level(text)
                if heading_level is not None and text:
                    section_path = section_path[: heading_level - 1]
                    section_path.append(text)

                if text_quality_issue(block.text) is None:
                    order_no += 1
                    segments.append(
                        {
                            "segmentKey": f"docx-b{order_no}",
                            "segmentType": "docx_block_text",
                            "orderNo": order_no,
                            "textContent": text,
                            "sectionPath": list(section_path),
                        }
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
                    order_no += 1
                    segments.append(
                        {
                            "segmentKey": f"docx-b{order_no}-formula{formula_no}",
                            "segmentType": "formula",
                            "orderNo": order_no,
                            "textContent": formula_text,
                            "sectionPath": list(section_path),
                        }
                    )

                for image_no, image in enumerate(_extract_paragraph_images(block, document), start=1):
                    if self._vision_client is None:
                        issues.append(
                            ParserIssue(
                                code="docx.vision_not_configured",
                                message="DOCX has visual content, but vision enhancement is not configured.",
                                details={"blockNo": block_no, "imageNo": image_no},
                            )
                        )
                        continue

                    try:
                        results = self._vision_client.analyze_image(
                            image["blob"],
                            mime_type=image["mime_type"],
                            resource_type=self.resource_type,
                            location={"sectionPath": list(section_path), "orderNo": order_no + 1},
                            hint="docx_inline_visual",
                        )
                    except Exception as exc:
                        issues.append(
                            ParserIssue(
                                code="docx.vision_failed",
                                message="DOCX visual enhancement failed.",
                                details={"blockNo": block_no, "imageNo": image_no, "error": str(exc)},
                            )
                        )
                        continue

                    for result_no, result in enumerate(_clean_vision_results(results), start=1):
                        order_no += 1
                        segments.append(
                            {
                                "segmentKey": _visual_segment_key(order_no, image_no, result.segment_type, result_no),
                                "segmentType": result.segment_type,
                                "orderNo": order_no,
                                "textContent": result.text,
                                "sectionPath": list(section_path),
                            }
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

                order_no += 1
                segments.append(
                    {
                        "segmentKey": f"docx-b{order_no}",
                        "segmentType": "docx_block_text",
                        "orderNo": order_no,
                        "textContent": text,
                        "sectionPath": list(section_path),
                    }
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


def _clean_vision_results(results: list[VisionResult]) -> list[VisionResult]:
    clean_results: list[VisionResult] = []
    for result in results:
        text = clean_text(result.text)
        if text and result.segment_type in ("ocr_text", "formula", "image_caption"):
            clean_results.append(VisionResult(segment_type=result.segment_type, text=text))
    return clean_results


def _visual_segment_key(order_no: int, image_no: int, segment_type: str, result_no: int) -> str:
    suffix = {
        "ocr_text": "ocr",
        "formula": "formula",
        "image_caption": "image",
    }[segment_type]
    return f"docx-b{order_no}-i{image_no}-{suffix}{result_no}"
