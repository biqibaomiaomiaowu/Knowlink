from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import os
from pathlib import Path
import re
import tempfile

from pypdf import PdfReader, PdfWriter

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
)
from server.parsers.base import BaseParser, ParserIssue, ParserResult, clean_text, is_duplicate_text, text_quality_issue


class PdfParser(BaseParser):
    resource_type = "pdf"

    def __init__(
        self,
        *,
        ocr_client: OcrClient | None = None,
        vision_client: VisionClient | None = None,
        enable_markitdown_ocr: bool | None = None,
    ) -> None:
        self._ocr_client = ocr_client if ocr_client is not None else get_configured_ocr_client()
        self._vision_client = vision_client if vision_client is not None else get_configured_vision_client()
        self._vision_batch_size = get_configured_vision_batch_size()
        self._enable_markitdown_ocr = (
            _env_bool("KNOWLINK_ENABLE_MARKITDOWN_OCR") if enable_markitdown_ocr is None else enable_markitdown_ocr
        )

    def parse(self, file_path: str | Path) -> ParserResult:
        pymupdf_result = self._parse_with_pymupdf(file_path)
        if pymupdf_result is not None:
            return pymupdf_result

        return self._parse_with_pypdf(file_path)

    def _parse_with_pymupdf(self, file_path: str | Path) -> ParserResult | None:
        try:
            import fitz
        except ImportError:
            return None

        try:
            document = fitz.open(str(file_path))
        except Exception:
            return None

        issues: list[ParserIssue] = []
        entries: list[_PdfPageEntry] = []
        candidates: list[_PdfVisualCandidate] = []
        local_visual_results: list[VisionAssetResult] = []

        if document.page_count == 0:
            document.close()
            return self._failed(
                ParserIssue(
                    code="pdf.page_text_empty",
                    message="PDF has no extractable text pages; OCR is not configured.",
                )
            )

        try:
            for page_index in range(document.page_count):
                page_no = page_index + 1
                page = document.load_page(page_index)
                raw_text = _pymupdf_page_text(page)
                quality_issue = text_quality_issue(raw_text)
                if quality_issue is not None:
                    entry = _PdfPageEntry(
                        page_no=page_no,
                        quality_issue=quality_issue,
                    )
                    if self._ocr_client is not None or self._vision_client is not None:
                        candidate = _pdf_visual_candidate(page, page_no, hint="pdf_page_ocr")
                        entry.asset_id = candidate.asset_id
                        candidates.append(candidate)
                    entries.append(entry)
                    continue

                text = clean_text(raw_text)
                entry = _PdfPageEntry(
                    page_no=page_no,
                    text=text,
                    duplicate_texts=[text],
                )

                if _pymupdf_page_needs_visual_ocr(page, text):
                    if self._ocr_client is not None or self._vision_client is not None:
                        candidate = _pdf_visual_candidate(page, page_no, hint="pdf_page_visual")
                        entry.asset_id = candidate.asset_id
                        candidates.append(candidate)

                local_result = _pdf_local_vector_result(page, page_no, text)
                if local_result is not None and self._vision_client is None:
                    entry.asset_id = entry.asset_id or local_result.asset_id
                    local_visual_results.append(local_result)
                entries.append(entry)
        finally:
            document.close()

        ocr_results, ocr_issues = self._recognize_assets(candidates)
        issues.extend(ocr_issues)
        visual_assets = _pdf_vision_assets_after_ocr(
            candidates,
            entries,
            ocr_results,
            issues,
            has_ocr_client=self._ocr_client is not None,
            has_vision_client=self._vision_client is not None,
        )
        visual_results, visual_issues = self._analyze_assets(
            visual_assets,
            document_context=_pdf_document_context(entries, ocr_results),
        )
        issues.extend(visual_issues)
        segments = _build_pdf_segments(
            entries,
            local_visual_results
            + _ocr_results_to_visual_results(
                ocr_results,
                entries,
                suppress_asset_ids={asset.asset_id for asset in visual_assets},
            )
            + visual_results,
            issues,
        )

        if not segments:
            return self._failed_with_issues(issues)

        return self._succeeded(segments, issues)

    def _parse_with_pypdf(self, file_path: str | Path) -> ParserResult:
        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            return self._read_failed(file_path, exc)

        issues: list[ParserIssue] = []
        entries: list[_PdfPageEntry] = []
        assets: list[VisualAsset] = []

        if not reader.pages:
            return self._failed(
                ParserIssue(
                    code="pdf.page_text_empty",
                    message="PDF has no extractable text pages; OCR is not configured.",
                )
            )

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
                entry = _PdfPageEntry(
                    page_no=page_no,
                    quality_issue=quality_issue,
                    markitdown_page=page,
                )
                if self._vision_client is not None:
                    entry.asset_id = _page_asset_id(page_no)
                    assets.append(
                        VisualAsset(
                            asset_id=entry.asset_id,
                            image_bytes=_page_to_pdf_bytes(page),
                            mime_type="application/pdf",
                            location={"pageNo": page_no},
                            hint="pdf_page_ocr",
                        )
                    )
                entries.append(entry)
                continue

            text = clean_text(raw_text)
            entries.append(_PdfPageEntry(page_no=page_no, text=text, duplicate_texts=[text]))

        visual_results, visual_issues = self._analyze_assets(assets, document_context=_pdf_document_context(entries))
        issues.extend(visual_issues)
        segments = _build_pdf_segments(entries, visual_results, issues, enable_markitdown_ocr=self._enable_markitdown_ocr)

        if not segments:
            return self._failed_with_issues(issues)

        return self._succeeded(segments, issues)

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
                    issues.append(
                        ParserIssue(
                            code="pdf.vision_failed",
                            message="PDF page vision enhancement failed.",
                            details={**asset.location, "error": str(exc)},
                        )
                    )

        return _clean_asset_results(results), issues

    def _recognize_assets(
        self,
        candidates: list[_PdfVisualCandidate],
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
                        code="pdf.ocr_failed",
                        message="PDF page OCR failed.",
                        details={**asset.location, "error": str(exc)},
                    )
                )
            return [], issues

        return _clean_ocr_results(results), issues


def _pymupdf_page_text(page: object) -> str:
    blocks = page.get_text("blocks")
    text_blocks = []
    for block in blocks:
        if len(block) < 5:
            continue
        block_text = clean_text(str(block[4]))
        if block_text:
            text_blocks.append((float(block[1]), float(block[0]), block_text))
    text_blocks.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(block_text for _, _, block_text in text_blocks)


def _pymupdf_page_png(page: object) -> bytes:
    import fitz

    rect = page.rect
    max_side = max(float(rect.width), float(rect.height), 1.0)
    zoom = min(1.5, 1600.0 / max_side)
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return pixmap.tobytes("png")


def _pymupdf_page_needs_visual_ocr(page: object, text: str) -> bool:
    try:
        has_images = bool(page.get_images(full=True))
        has_drawings = bool(page.get_drawings())
    except Exception:
        return False
    return has_images or has_drawings


def _pdf_local_vector_result(page: object, page_no: int, text: str) -> VisionAssetResult | None:
    if "文氏图" not in text and "venn" not in text.lower():
        return None

    try:
        drawings = page.get_drawings()
    except Exception:
        return None

    if not _has_venn_like_pdf_drawing(drawings):
        return None

    return VisionAssetResult(
        asset_id=_page_asset_id(page_no),
        segment_type="image_caption",
        text="文氏图示例：圆形表示集合 A，小点 a 表示元素 a，图示强调元素与集合之间的属于关系。",
    )


def _has_venn_like_pdf_drawing(drawings: list[dict[str, object]]) -> bool:
    has_set_boundary = False
    has_universe_box = False
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = float(getattr(rect, "width", 0.0) or 0.0)
        height = float(getattr(rect, "height", 0.0) or 0.0)
        if width <= 0 or height <= 0:
            continue

        items = drawing.get("items") or []
        has_curve = any(isinstance(item, tuple) and item and item[0] == "c" for item in items)
        if has_curve and 25 <= width <= 140 and 25 <= height <= 140 and 0.65 <= width / height <= 1.45:
            has_set_boundary = True
        if 35 <= width <= 180 and 35 <= height <= 140 and any(
            isinstance(item, tuple) and item and item[0] == "l" for item in items
        ):
            has_universe_box = True

    return has_set_boundary or has_universe_box


@dataclass
class _PdfVisualCandidate:
    asset_id: str
    image_bytes: bytes
    mime_type: str
    location: dict[str, object]
    hint: str


@dataclass
class _PdfPageEntry:
    page_no: int
    text: str | None = None
    quality_issue: str | None = None
    asset_id: str | None = None
    duplicate_texts: list[str] = field(default_factory=list)
    markitdown_page: object | None = None


def _pdf_visual_candidate(page: object, page_no: int, *, hint: str) -> _PdfVisualCandidate:
    return _PdfVisualCandidate(
        asset_id=_page_asset_id(page_no),
        image_bytes=_pymupdf_page_png(page),
        mime_type="image/png",
        location={"pageNo": page_no},
        hint=hint,
    )


def _pdf_vision_assets_after_ocr(
    candidates: list[_PdfVisualCandidate],
    entries: list[_PdfPageEntry],
    ocr_results: list[OcrAssetResult],
    issues: list[ParserIssue],
    *,
    has_ocr_client: bool,
    has_vision_client: bool,
) -> list[VisualAsset]:
    if not has_vision_client:
        if has_ocr_client:
            _append_pdf_ocr_empty_issues(candidates, entries, ocr_results, issues)
        return []

    if not has_ocr_client:
        return [_candidate_to_visual_asset(candidate) for candidate in candidates]

    result_map = _ocr_results_by_asset_id(ocr_results)
    entry_map = {entry.asset_id: entry for entry in entries if entry.asset_id}
    visual_assets: list[VisualAsset] = []
    for candidate in candidates:
        entry = entry_map.get(candidate.asset_id)
        if entry is None:
            continue
        page_results = result_map.get(candidate.asset_id, [])
        if _skip_cover_visual_candidate(entry, page_results) and not _has_ocr_failure(issues, entry.page_no):
            entry.asset_id = None
            continue
        if _ocr_results_need_vlm(page_results):
            visual_assets.append(_candidate_to_visual_asset(candidate))
            continue
        if _ocr_results_are_good(page_results, entry.duplicate_texts):
            continue
        if entry.text and _text_layer_sufficient(entry.text):
            continue
        visual_assets.append(_candidate_to_visual_asset(candidate))
    return visual_assets


def _append_pdf_ocr_empty_issues(
    candidates: list[_PdfVisualCandidate],
    entries: list[_PdfPageEntry],
    ocr_results: list[OcrAssetResult],
    issues: list[ParserIssue],
) -> None:
    result_map = _ocr_results_by_asset_id(ocr_results)
    entry_map = {entry.asset_id: entry for entry in entries if entry.asset_id}
    for candidate in candidates:
        if candidate.asset_id in result_map:
            continue
        entry = entry_map.get(candidate.asset_id)
        if (
            entry is not None
            and _skip_cover_visual_candidate(entry, [])
            and not _has_ocr_failure(issues, entry.page_no)
        ):
            continue
        if entry is not None and _text_layer_sufficient(entry.text):
            continue
        if _has_ocr_failure(issues, int(candidate.location["pageNo"])):
            continue
        issues.append(
            ParserIssue(
                code="pdf.ocr_empty",
                message="PDF page OCR returned no clean text.",
                details=candidate.location,
            )
        )


def _candidate_to_visual_asset(candidate: _PdfVisualCandidate) -> VisualAsset:
    return VisualAsset(
        asset_id=candidate.asset_id,
        image_bytes=candidate.image_bytes,
        mime_type=candidate.mime_type,
        location=dict(candidate.location),
        hint=candidate.hint,
    )


def _skip_cover_visual_candidate(entry: _PdfPageEntry, ocr_results: list[OcrAssetResult]) -> bool:
    return (
        entry.page_no == 1
        and entry.quality_issue is None
        and bool(entry.text)
        and not ocr_results
        and len(re.sub(r"\s+", "", clean_text(entry.text))) <= 80
    )


def _build_pdf_segments(
    entries: list[_PdfPageEntry],
    visual_results: list[VisionAssetResult],
    issues: list[ParserIssue],
    *,
    enable_markitdown_ocr: bool = False,
) -> list[dict[str, object]]:
    result_map = _results_by_asset_id(visual_results)
    segments: list[dict[str, object]] = []
    order_no = 0

    for entry in entries:
        if entry.text:
            order_no += 1
            segments.append(
                {
                    "segmentKey": f"pdf-p{entry.page_no}",
                    "segmentType": "pdf_page_text",
                    "orderNo": order_no,
                    "textContent": entry.text,
                    "pageNo": entry.page_no,
                }
            )

        page_results = list(result_map.get(entry.asset_id or "", []))
        if entry.quality_issue and not page_results and enable_markitdown_ocr and entry.markitdown_page is not None:
            markitdown_result, markitdown_issues = _markitdown_asset_result(entry)
            issues.extend(markitdown_issues)
            if markitdown_result is not None:
                page_results.append(markitdown_result)

        if (
            entry.asset_id
            and not page_results
            and not entry.quality_issue
            and _needs_missing_visual_issue(entry.text)
            and not _has_visual_failure(issues, entry.page_no)
        ):
            issues.append(
                ParserIssue(
                    code="pdf.visual_empty",
                    message="PDF page has visual content, but vision enhancement returned no clean segment.",
                    details={"pageNo": entry.page_no},
                )
            )

        visual_count = 0
        for index, result in enumerate(page_results, start=1):
            if is_duplicate_text(result.text, entry.duplicate_texts):
                continue
            order_no += 1
            visual_count += 1
            entry.duplicate_texts.append(result.text)
            segments.append(
                {
                    "segmentKey": _visual_segment_key(entry.page_no, result.segment_type, index),
                    "segmentType": result.segment_type,
                    "orderNo": order_no,
                    "textContent": result.text,
                    "pageNo": entry.page_no,
                }
            )

        if entry.quality_issue and not entry.text and visual_count == 0:
            issues.append(
                ParserIssue(
                    code="pdf.page_text_empty" if entry.quality_issue == "empty" else "pdf.page_text_garbled",
                    message="PDF page needs OCR, but no clean OCR result is configured.",
                    details={"pageNo": entry.page_no},
                )
            )

    return segments


def _markitdown_asset_result(entry: _PdfPageEntry) -> tuple[VisionAssetResult | None, list[ParserIssue]]:
    issues: list[ParserIssue] = []
    try:
        text = _markitdown_page_text(entry.markitdown_page)
    except ImportError as exc:
        issues.append(
            ParserIssue(
                code="pdf.markitdown_unavailable",
                message="MarkItDown OCR fallback is enabled but MarkItDown is not installed.",
                details={"pageNo": entry.page_no, "error": str(exc)},
            )
        )
    except Exception as exc:
        issues.append(
            ParserIssue(
                code="pdf.markitdown_failed",
                message="MarkItDown OCR fallback failed for this PDF page.",
                details={"pageNo": entry.page_no, "error": str(exc)},
            )
        )
    else:
        text = clean_text(text)
        if text:
            return (
                VisionAssetResult(
                    asset_id=entry.asset_id or _page_asset_id(entry.page_no),
                    segment_type="ocr_text",
                    text=text,
                ),
                issues,
            )

    return None, issues


def _has_visual_failure(issues: list[ParserIssue], page_no: int) -> bool:
    for issue in issues:
        if issue.code not in {"pdf.vision_failed", "pdf.ocr_failed", "pdf.ocr_empty"}:
            continue
        details = issue.details or {}
        if details.get("pageNo") == page_no:
            return True
    return False


def _has_ocr_failure(issues: list[ParserIssue], page_no: int) -> bool:
    for issue in issues:
        if issue.code not in {"pdf.ocr_failed", "pdf.ocr_empty"}:
            continue
        details = issue.details or {}
        if details.get("pageNo") == page_no:
            return True
    return False


def _needs_missing_visual_issue(text: str | None) -> bool:
    return len(clean_text(text)) <= 80


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
    entries: list[_PdfPageEntry],
    *,
    suppress_asset_ids: set[str] | None = None,
) -> list[VisionAssetResult]:
    entry_map = {entry.asset_id: entry for entry in entries if entry.asset_id}
    suppressed = suppress_asset_ids or set()
    visual_results: list[VisionAssetResult] = []
    for result in results:
        if result.asset_id in suppressed:
            continue
        entry = entry_map.get(result.asset_id)
        if entry is None:
            continue
        if _usable_ocr_text(result.text):
            visual_results.append(
                VisionAssetResult(asset_id=result.asset_id, segment_type="ocr_text", text=result.text)
            )
    return visual_results


def _ocr_results_are_good(results: list[OcrAssetResult], duplicate_texts: list[str]) -> bool:
    for result in results:
        text = clean_text(result.text)
        if text and not is_duplicate_text(text, duplicate_texts) and _usable_ocr_text(text):
            return True
    return False


def _ocr_results_need_vlm(results: list[OcrAssetResult]) -> bool:
    return any(_low_quality_ocr_text(result.text) for result in results)


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
    cleaned = clean_text(text)
    compact = re.sub(r"\s+", "", cleaned)
    if not compact:
        return False
    if _looks_like_broken_math_ocr(compact):
        return True
    if _looks_like_broken_code_ocr(cleaned):
        return True
    return _looks_like_complex_table_ocr(cleaned)


def _looks_like_broken_math_ocr(compact: str) -> bool:
    return any(token in compact for token in ("AUB", "ANB", "ABe", "CuA", "CuB", "2”", "card(AB)"))


def _looks_like_broken_code_ocr(text: str) -> bool:
    if "print(" not in text and "input(" not in text:
        return False
    single_quotes_unbalanced = text.count("'") % 2 == 1
    double_quotes_unbalanced = text.count('"') % 2 == 1
    parens_unbalanced = text.count("(") != text.count(")")
    broken_line = re.search(r"print\([^)]*\n[^)]*$", text) is not None
    return single_quotes_unbalanced or double_quotes_unbalanced or parens_unbalanced or broken_line


def _looks_like_complex_table_ocr(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if all(token in compact for token in ("解释器", "简称", "特点")) and "|" not in text:
        return True
    lines = [line for line in text.splitlines() if line.strip()]
    return len(lines) >= 18 and " | " not in text and any(token in compact for token in ("CPython", "PyPy", "Jython"))


def _text_layer_sufficient(text: str | None) -> bool:
    return len(re.sub(r"\s+", "", clean_text(text))) >= 120


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


def _pdf_document_context(entries: list[_PdfPageEntry], ocr_results: list[OcrAssetResult] | None = None) -> str:
    parts = [f"第 {entry.page_no} 页：{entry.text}" for entry in entries if entry.text]
    for result in ocr_results or []:
        parts.append(f"OCR {result.asset_id}：{result.text}")
    return "\n".join(parts)


def _chunks(items: list[VisualAsset], size: int) -> list[list[VisualAsset]]:
    chunk_size = max(1, size)
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def _page_asset_id(page_no: int) -> str:
    return f"pdf-p{page_no}"


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
