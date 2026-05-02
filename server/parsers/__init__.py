from pathlib import Path

from server.parsers.base import BaseParser, ParserIssue, ParserResult, ParserScaffold
from server.parsers.docx import DocxParser
from server.parsers.mineru import MineruPrecisionClient
from server.parsers.normalize import NormalizeParserOutput
from server.parsers.pdf import PdfParser
from server.parsers.pptx import PptxParser
from server.parsers.srt import SrtParser
from server.parsers.video import VideoParser


_PARSER_TYPES: dict[str, type[BaseParser]] = {
    "pdf": PdfParser,
    "pptx": PptxParser,
    "docx": DocxParser,
    "srt": SrtParser,
    "mp4": VideoParser,
}


def get_parser(resource_type: str) -> BaseParser:
    parser_type = _PARSER_TYPES.get(resource_type.strip().lower())
    if parser_type is None:
        raise ValueError(f"unsupported parser resource type: {resource_type}")
    return parser_type()


def parse_resource(resource_type: str, file_path: str | Path) -> ParserResult:
    return get_parser(resource_type).parse(file_path)

__all__ = [
    "BaseParser",
    "DocxParser",
    "MineruPrecisionClient",
    "ParserIssue",
    "ParserResult",
    "NormalizeParserOutput",
    "ParserScaffold",
    "PdfParser",
    "PptxParser",
    "SrtParser",
    "VideoParser",
    "get_parser",
    "parse_resource",
]
