from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter

from server.ai.vision import VisionClient, VisionResult, get_configured_vision_client
from server.parsers.base import BaseParser, ParserIssue, ParserResult, clean_text, text_quality_issue


class PdfParser(BaseParser):
    resource_type = "pdf"

    def __init__(
        self,
        *,
        vision_client: VisionClient | None = None,
        enable_markitdown_ocr: bool | None = None,
    ) -> None:
        self._vision_client = vision_client if vision_client is not None else get_configured_vision_client()
        self._enable_markitdown_ocr = (
            _env_bool("KNOWLINK_ENABLE_MARKITDOWN_OCR") if enable_markitdown_ocr is None else enable_markitdown_ocr
        )

    def parse(self, file_path: str | Path) -> ParserResult:
        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            return self._read_failed(file_path, exc)

        issues: list[ParserIssue] = []
        segments: list[dict[str, object]] = []

        if not reader.pages:
            return self._failed(
                ParserIssue(
                    code="pdf.page_text_empty",
                    message="PDF has no extractable text pages; OCR is not configured.",
                )
            )

        order_no = 0
        for page_no, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text()
            except Exception as exc:
                issues.append(
                    ParserIssue(
                        code="pdf.page_read_failed",
                        message="PDF page text layer cannot be read.",
                        details={"pageNo": page_no, "error": str(exc)},
                    )
                )
                continue

            quality_issue = text_quality_issue(raw_text)
            if quality_issue is not None:
                enhanced_results, enhanced_issues = self._enhance_page(page, page_no)
                issues.extend(enhanced_issues)
                if enhanced_results:
                    for index, result in enumerate(enhanced_results, start=1):
                        text = clean_text(result.text)
                        if not text:
                            continue
                        order_no += 1
                        segments.append(
                            {
                                "segmentKey": _visual_segment_key(page_no, result.segment_type, index),
                                "segmentType": result.segment_type,
                                "orderNo": order_no,
                                "textContent": text,
                                "pageNo": page_no,
                            }
                        )
                    continue

                issues.append(
                    ParserIssue(
                        code="pdf.page_text_empty" if quality_issue == "empty" else "pdf.page_text_garbled",
                        message="PDF page needs OCR, but no clean OCR result is configured.",
                        details={"pageNo": page_no},
                    )
                )
                continue

            text = clean_text(raw_text)
            order_no += 1
            segments.append(
                {
                    "segmentKey": f"pdf-p{page_no}",
                    "segmentType": "pdf_page_text",
                    "orderNo": order_no,
                    "textContent": text,
                    "pageNo": page_no,
                }
            )

        if not segments:
            return self._failed_with_issues(issues)

        return self._succeeded(segments, issues)

    def _enhance_page(self, page: object, page_no: int) -> tuple[list[VisionResult], list[ParserIssue]]:
        issues: list[ParserIssue] = []

        if self._vision_client is not None:
            try:
                results = self._vision_client.analyze_image(
                    _page_to_pdf_bytes(page),
                    mime_type="application/pdf",
                    resource_type=self.resource_type,
                    location={"pageNo": page_no},
                    hint="pdf_page_ocr",
                )
            except Exception as exc:
                issues.append(
                    ParserIssue(
                        code="pdf.vision_failed",
                        message="PDF page vision enhancement failed.",
                        details={"pageNo": page_no, "error": str(exc)},
                    )
                )
            else:
                clean_results = _clean_vision_results(results)
                if clean_results:
                    return clean_results, issues

        if self._enable_markitdown_ocr:
            try:
                text = _markitdown_page_text(page)
            except ImportError as exc:
                issues.append(
                    ParserIssue(
                        code="pdf.markitdown_unavailable",
                        message="MarkItDown OCR fallback is enabled but MarkItDown is not installed.",
                        details={"pageNo": page_no, "error": str(exc)},
                    )
                )
            except Exception as exc:
                issues.append(
                    ParserIssue(
                        code="pdf.markitdown_failed",
                        message="MarkItDown OCR fallback failed for this PDF page.",
                        details={"pageNo": page_no, "error": str(exc)},
                    )
                )
            else:
                text = clean_text(text)
                if text:
                    return [VisionResult(segment_type="ocr_text", text=text)], issues

        return [], issues


def _clean_vision_results(results: list[VisionResult]) -> list[VisionResult]:
    clean_results: list[VisionResult] = []
    for result in results:
        text = clean_text(result.text)
        if text and result.segment_type in ("ocr_text", "formula", "image_caption"):
            clean_results.append(VisionResult(segment_type=result.segment_type, text=text))
    return clean_results


def _page_to_pdf_bytes(page: object) -> bytes:
    writer = PdfWriter()
    buffer = BytesIO()
    try:
        writer.add_page(page)
        writer.write(buffer)
    except Exception:
        return b""
    return buffer.getvalue()


def _markitdown_page_text(page: object) -> str:
    from markitdown import MarkItDown

    page_pdf = _page_to_pdf_bytes(page)
    if not page_pdf:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as file:
        file.write(page_pdf)
        tmp_path = file.name

    try:
        result = MarkItDown().convert(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return getattr(result, "text_content", "") or ""


def _env_bool(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _visual_segment_key(page_no: int, segment_type: str, index: int) -> str:
    suffix = {
        "ocr_text": "ocr",
        "formula": "formula",
        "image_caption": "image",
    }[segment_type]
    return f"pdf-p{page_no}-{suffix}{index}"
