import json
from io import BytesIO
from pathlib import Path

from docx import Document
from jsonschema import Draft202012Validator
import pytest
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from server.ai.vision import VisionResult
from server.parsers import DocxParser, ParserResult, PdfParser, PptxParser, SrtParser, VideoParser, parse_resource


ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DOCUMENT_SCHEMA = json.loads(
    (ROOT / "schemas/parse/normalized_document.schema.json").read_text(encoding="utf-8")
)
NORMALIZED_DOCUMENT_VALIDATOR = Draft202012Validator(NORMALIZED_DOCUMENT_SCHEMA)
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
    b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


def assert_valid_normalized_document(payload: dict[str, object] | None) -> dict[str, object]:
    assert payload is not None
    NORMALIZED_DOCUMENT_VALIDATOR.validate(payload)
    return payload


def issue_codes(result) -> list[str]:
    return [issue.code for issue in result.issues]


class FakeVisionClient:
    def __init__(self, results: list[VisionResult]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    def analyze_image(self, image_bytes, *, mime_type, resource_type, location, hint=None):
        self.calls.append(
            {
                "image_bytes": image_bytes,
                "mime_type": mime_type,
                "resource_type": resource_type,
                "location": location,
                "hint": hint,
            }
        )
        return self.results


def create_text_pdf(path: Path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )

    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = StreamObject()
    content._data = f"BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    page[NameObject("/Contents")] = writer._add_object(content)

    with path.open("wb") as file:
        writer.write(file)


def create_blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as file:
        writer.write(file)


def test_pdf_parser_extracts_page_text_and_validates_schema(tmp_path: Path):
    pdf_path = tmp_path / "text.pdf"
    create_text_pdf(pdf_path, "PDF Parser Text")

    result = PdfParser().parse(pdf_path)

    assert result.status == "succeeded"
    document = assert_valid_normalized_document(result.normalized_document)
    assert document["resourceType"] == "pdf"
    assert document["segments"] == [
        {
            "segmentKey": "pdf-p1",
            "segmentType": "pdf_page_text",
            "orderNo": 1,
            "textContent": "PDF Parser Text",
            "pageNo": 1,
        }
    ]


def test_pdf_parser_reports_empty_text_page(tmp_path: Path):
    pdf_path = tmp_path / "blank.pdf"
    create_blank_pdf(pdf_path)

    result = PdfParser().parse(pdf_path)

    assert result.status == "failed"
    assert result.normalized_document is None
    assert issue_codes(result) == ["pdf.page_text_empty"]


def test_pdf_parser_uses_ocr_fallback_for_garbled_page(monkeypatch, tmp_path: Path):
    class FakePage:
        def extract_text(self):
            return "bad\uffff\x00\x01\x19text"

    class FakeReader:
        pages = [FakePage()]

    monkeypatch.setattr("server.parsers.pdf.PdfReader", lambda _: FakeReader())
    pdf_path = tmp_path / "garbled.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    vision_client = FakeVisionClient([VisionResult(segment_type="ocr_text", text="OCR clean text")])

    result = PdfParser(vision_client=vision_client).parse(pdf_path)

    assert result.status == "succeeded"
    document = assert_valid_normalized_document(result.normalized_document)
    assert vision_client.calls[0]["location"] == {"pageNo": 1}
    assert document["segments"] == [
        {
            "segmentKey": "pdf-p1-ocr1",
            "segmentType": "ocr_text",
            "orderNo": 1,
            "textContent": "OCR clean text",
            "pageNo": 1,
        }
    ]
    assert "\uffff" not in document["segments"][0]["textContent"]
    assert "\x00" not in document["segments"][0]["textContent"]


def test_pdf_parser_does_not_emit_garbled_text_when_ocr_is_not_configured(monkeypatch, tmp_path: Path):
    class FakePage:
        def extract_text(self):
            return "bad\uffff\x00\x01\x19text"

    class FakeReader:
        pages = [FakePage()]

    monkeypatch.setattr("server.parsers.pdf.PdfReader", lambda _: FakeReader())
    pdf_path = tmp_path / "garbled.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    result = PdfParser().parse(pdf_path)

    assert result.status == "failed"
    assert result.normalized_document is None
    assert issue_codes(result) == ["pdf.page_text_garbled"]


def test_pptx_parser_extracts_slide_text_and_validates_schema(tmp_path: Path):
    pptx_path = tmp_path / "deck.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    textbox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    textbox.text = "Slide Title\nSlide body"
    presentation.save(pptx_path)

    result = PptxParser().parse(pptx_path)

    assert result.status == "succeeded"
    document = assert_valid_normalized_document(result.normalized_document)
    assert document["resourceType"] == "pptx"
    assert document["segments"][0]["segmentKey"] == "pptx-s1"
    assert document["segments"][0]["segmentType"] == "ppt_slide_text"
    assert document["segments"][0]["slideNo"] == 1
    assert document["segments"][0]["textContent"] == "Slide Title\nSlide body"


def test_pptx_parser_reports_empty_slide(tmp_path: Path):
    pptx_path = tmp_path / "blank.pptx"
    presentation = Presentation()
    presentation.slides.add_slide(presentation.slide_layouts[6])
    presentation.save(pptx_path)

    result = PptxParser().parse(pptx_path)

    assert result.status == "failed"
    assert result.normalized_document is None
    assert issue_codes(result) == ["pptx.slide_text_empty"]


def test_pptx_parser_extracts_image_formula_with_slide_location(tmp_path: Path):
    pptx_path = tmp_path / "formula.pptx"
    image_path = tmp_path / "formula.png"
    image_path.write_bytes(PNG_BYTES)
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_picture(str(image_path), Inches(1), Inches(1), width=Inches(1))
    presentation.save(pptx_path)
    vision_client = FakeVisionClient([VisionResult(segment_type="formula", text="E = mc^2")])

    result = PptxParser(vision_client=vision_client).parse(pptx_path)

    assert result.status == "succeeded"
    document = assert_valid_normalized_document(result.normalized_document)
    assert vision_client.calls[0]["location"] == {"slideNo": 1}
    assert document["segments"] == [
        {
            "segmentKey": "pptx-s1-i1-formula1",
            "segmentType": "formula",
            "orderNo": 1,
            "textContent": "E = mc^2",
            "slideNo": 1,
        }
    ]


def test_docx_parser_extracts_heading_section_path_and_validates_schema(tmp_path: Path):
    docx_path = tmp_path / "document.docx"
    document = Document()
    document.add_heading("Chapter 1", level=1)
    document.add_paragraph("First paragraph")
    document.add_heading("Section 1.1", level=2)
    document.add_paragraph("Second paragraph")
    document.save(docx_path)

    result = DocxParser().parse(docx_path)

    assert result.status == "succeeded"
    normalized = assert_valid_normalized_document(result.normalized_document)
    segments = normalized["segments"]
    assert segments[0]["segmentType"] == "docx_block_text"
    assert segments[0]["sectionPath"] == ["Chapter 1"]
    assert segments[1]["textContent"] == "First paragraph"
    assert segments[1]["sectionPath"] == ["Chapter 1"]
    assert segments[3]["textContent"] == "Second paragraph"
    assert segments[3]["sectionPath"] == ["Chapter 1", "Section 1.1"]


def test_docx_parser_uses_chinese_heading_heuristic_and_extracts_table(tmp_path: Path):
    docx_path = tmp_path / "table.docx"
    document = Document()
    document.add_paragraph("一、函数极限")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "概念"
    table.cell(0, 1).text = "定义"
    table.cell(1, 0).text = "极限"
    table.cell(1, 1).text = "趋近时的稳定趋势"
    document.save(docx_path)

    result = DocxParser().parse(docx_path)

    assert result.status == "succeeded"
    document_payload = assert_valid_normalized_document(result.normalized_document)
    segments = document_payload["segments"]
    assert segments[0]["sectionPath"] == ["一、函数极限"]
    assert segments[1] == {
        "segmentKey": "docx-b2",
        "segmentType": "docx_block_text",
        "orderNo": 2,
        "textContent": "概念 | 定义\n极限 | 趋近时的稳定趋势",
        "sectionPath": ["一、函数极限"],
    }


def test_docx_parser_extracts_image_caption_with_section_path(tmp_path: Path):
    docx_path = tmp_path / "image.docx"
    document = Document()
    document.add_heading("图表章节", level=1)
    document.add_picture(BytesIO(PNG_BYTES), width=Inches(1))
    document.save(docx_path)
    vision_client = FakeVisionClient([VisionResult(segment_type="image_caption", text="函数变化趋势图")])

    result = DocxParser(vision_client=vision_client).parse(docx_path)

    assert result.status == "succeeded"
    document_payload = assert_valid_normalized_document(result.normalized_document)
    assert vision_client.calls[0]["location"]["sectionPath"] == ["图表章节"]
    assert document_payload["segments"][1] == {
        "segmentKey": "docx-b2-i1-image1",
        "segmentType": "image_caption",
        "orderNo": 2,
        "textContent": "函数变化趋势图",
        "sectionPath": ["图表章节"],
    }


def test_srt_parser_extracts_captions_and_validates_schema(tmp_path: Path):
    srt_path = tmp_path / "captions.srt"
    srt_path.write_text(
        "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:03,000",
                "First caption",
                "",
                "2",
                "00:00:04.250 --> 00:00:05.750",
                "Second",
                "caption",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = parse_resource("srt", srt_path)

    assert isinstance(result, ParserResult)
    assert result.status == "succeeded"
    document = assert_valid_normalized_document(result.normalized_document)
    assert document["resourceType"] == "srt"
    assert document["segments"] == [
        {
            "segmentKey": "srt-c1",
            "segmentType": "video_caption",
            "orderNo": 1,
            "textContent": "First caption",
            "startSec": 1,
            "endSec": 3,
        },
        {
            "segmentKey": "srt-c2",
            "segmentType": "video_caption",
            "orderNo": 2,
            "textContent": "Second\ncaption",
            "startSec": 4,
            "endSec": 6,
        },
    ]


def test_srt_parser_rejects_empty_or_invalid_timeline(tmp_path: Path):
    empty_srt_path = tmp_path / "empty.srt"
    empty_srt_path.write_text("", encoding="utf-8")
    empty_result = SrtParser().parse(empty_srt_path)
    assert empty_result.status == "failed"
    assert issue_codes(empty_result) == ["srt.caption_empty"]

    invalid_srt_path = tmp_path / "invalid.srt"
    invalid_srt_path.write_text(
        "1\n00:00:03,000 --> 00:00:01,000\nBad timeline\n",
        encoding="utf-8",
    )
    invalid_result = SrtParser().parse(invalid_srt_path)
    assert invalid_result.status == "failed"
    assert issue_codes(invalid_result) == ["srt.timeline_invalid"]


def test_mp4_parser_returns_asr_not_configured_issue(tmp_path: Path):
    video_path = tmp_path / "lecture.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    result = VideoParser().parse(video_path)

    assert result.status == "failed"
    assert result.normalized_document is None
    assert issue_codes(result) == ["mp4.asr_not_configured"]
