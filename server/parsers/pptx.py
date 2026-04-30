from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pptx import Presentation

from server.ai.vision import VisionClient, VisionResult, get_configured_vision_client
from server.parsers.base import BaseParser, ParserIssue, ParserResult, clean_text, text_quality_issue


class PptxParser(BaseParser):
    resource_type = "pptx"

    def __init__(self, *, vision_client: VisionClient | None = None) -> None:
        self._vision_client = vision_client if vision_client is not None else get_configured_vision_client()

    def parse(self, file_path: str | Path) -> ParserResult:
        try:
            presentation = Presentation(str(file_path))
        except Exception as exc:
            return self._read_failed(file_path, exc)

        issues: list[ParserIssue] = []
        segments: list[dict[str, object]] = []

        if not presentation.slides:
            return self._failed(
                ParserIssue(
                    code="pptx.slide_text_empty",
                    message="PPTX has no slides with extractable text; OCR is not configured.",
                )
            )

        order_no = 0
        for slide_no, slide in enumerate(presentation.slides, start=1):
            text_parts = list(_iter_slide_text(slide.shapes))
            raw_text = "\n".join(text_parts)
            quality_issue = text_quality_issue(raw_text)
            if quality_issue is None:
                text = clean_text(raw_text)
                order_no += 1
                segments.append(
                    {
                        "segmentKey": f"pptx-s{slide_no}",
                        "segmentType": "ppt_slide_text",
                        "orderNo": order_no,
                        "textContent": text,
                        "slideNo": slide_no,
                    }
                )
            elif quality_issue == "garbled":
                issues.append(
                    ParserIssue(
                        code="pptx.slide_text_garbled",
                        message="PPTX slide text layer contains garbled text and was skipped.",
                        details={"slideNo": slide_no},
                    )
                )

            image_no = 0
            for image in _iter_slide_images(slide.shapes):
                image_no += 1
                if self._vision_client is None:
                    issues.append(
                        ParserIssue(
                            code="pptx.vision_not_configured",
                            message="PPTX slide has visual content, but vision enhancement is not configured.",
                            details={"slideNo": slide_no, "imageNo": image_no},
                        )
                    )
                    continue

                try:
                    results = self._vision_client.analyze_image(
                        image["blob"],
                        mime_type=image["mime_type"],
                        resource_type=self.resource_type,
                        location={"slideNo": slide_no},
                        hint="pptx_shape_visual",
                    )
                except Exception as exc:
                    issues.append(
                        ParserIssue(
                            code="pptx.vision_failed",
                            message="PPTX visual enhancement failed.",
                            details={"slideNo": slide_no, "imageNo": image_no, "error": str(exc)},
                        )
                    )
                    continue

                for result_no, result in enumerate(_clean_vision_results(results), start=1):
                    order_no += 1
                    segments.append(
                        {
                            "segmentKey": _visual_segment_key(slide_no, image_no, result.segment_type, result_no),
                            "segmentType": result.segment_type,
                            "orderNo": order_no,
                            "textContent": result.text,
                            "slideNo": slide_no,
                        }
                    )

            if quality_issue == "empty" and image_no == 0:
                issues.append(
                    ParserIssue(
                        code="pptx.slide_text_empty",
                        message="PPTX slide has no extractable text or visual content.",
                        details={"slideNo": slide_no},
                    )
                )

        if not segments:
            return self._failed_with_issues(issues)

        return self._succeeded(segments, issues)


def _iter_slide_text(shapes: Iterable[object]) -> Iterable[str]:
    for shape in _sorted_shapes(shapes):
        table_text = _table_text(shape)
        if table_text:
            yield table_text

        if getattr(shape, "has_text_frame", False):
            text = clean_text(getattr(shape, "text", ""))
            if text:
                yield text

        nested_shapes = getattr(shape, "shapes", None)
        if nested_shapes is not None:
            yield from _iter_slide_text(nested_shapes)


def _iter_slide_images(shapes: Iterable[object]) -> Iterable[dict[str, Any]]:
    for shape in _sorted_shapes(shapes):
        image = getattr(shape, "image", None)
        if image is not None:
            yield {
                "blob": image.blob,
                "mime_type": image.content_type,
            }

        nested_shapes = getattr(shape, "shapes", None)
        if nested_shapes is not None:
            yield from _iter_slide_images(nested_shapes)


def _sorted_shapes(shapes: Iterable[object]) -> list[object]:
    return sorted(
        shapes,
        key=lambda shape: (
            int(getattr(shape, "top", 0) or 0),
            int(getattr(shape, "left", 0) or 0),
        ),
    )


def _table_text(shape: object) -> str:
    if not getattr(shape, "has_table", False):
        return ""

    rows: list[str] = []
    for row in shape.table.rows:
        cells = [clean_text(cell.text) for cell in row.cells]
        row_text = " | ".join(cell for cell in cells if cell)
        if row_text:
            rows.append(row_text)
    return "\n".join(rows)


def _clean_vision_results(results: list[VisionResult]) -> list[VisionResult]:
    clean_results: list[VisionResult] = []
    for result in results:
        text = clean_text(result.text)
        if text and result.segment_type in ("ocr_text", "formula", "image_caption"):
            clean_results.append(VisionResult(segment_type=result.segment_type, text=text))
    return clean_results


def _visual_segment_key(slide_no: int, image_no: int, segment_type: str, result_no: int) -> str:
    suffix = {
        "ocr_text": "ocr",
        "formula": "formula",
        "image_caption": "image",
    }[segment_type]
    return f"pptx-s{slide_no}-i{image_no}-{suffix}{result_no}"
