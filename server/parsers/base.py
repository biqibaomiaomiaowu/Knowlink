from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ParserStatus = Literal["succeeded", "failed", "skipped"]
NormalizedDocument = dict[str, Any]
NormalizedSegment = dict[str, Any]

_GARBLED_TEXT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd\uffff]")
_PURE_DOT_LINE_RE = re.compile(r"^[.\-_=~·•。…\s]{4,}$")
_PURE_NOISE_LINE_RE = re.compile(r"^[^\w\u4e00-\u9fff]{4,}$", re.UNICODE)
_REPEATED_SYMBOL_LINE_RE = re.compile(r"^(.)\1{3,}$")
_USEFUL_MATH_CHARS = set("=+-*/^_()[]{}<>≤≥≈≠∫∑∏√π∞→←↔")


@dataclass(frozen=True)
class ParserIssue:
    code: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True)
class ParserResult:
    resource_type: str
    status: ParserStatus
    normalized_document: NormalizedDocument | None = None
    issues: list[ParserIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceType": self.resource_type,
            "status": self.status,
            "normalizedDocument": self.normalized_document,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class BaseParser:
    resource_type: str

    def parse(self, file_path: str | Path) -> ParserResult:
        raise NotImplementedError

    def _succeeded(
        self,
        segments: list[NormalizedSegment],
        issues: list[ParserIssue] | None = None,
    ) -> ParserResult:
        clean_segments = _clean_segments(segments)
        if not clean_segments:
            return self._failed_with_issues(
                (issues or [])
                + [
                    ParserIssue(
                        code=f"{self.resource_type}.segment_empty_after_cleaning",
                        message="Parser produced no clean normalized segments.",
                    )
                ]
            )

        return ParserResult(
            resource_type=self.resource_type,
            status="succeeded",
            normalized_document={
                "resourceType": self.resource_type,
                "segments": clean_segments,
            },
            issues=issues or [],
        )

    def _failed(self, issue: ParserIssue) -> ParserResult:
        return ParserResult(
            resource_type=self.resource_type,
            status="failed",
            normalized_document=None,
            issues=[issue],
        )

    def _failed_with_issues(self, issues: list[ParserIssue]) -> ParserResult:
        return ParserResult(
            resource_type=self.resource_type,
            status="failed",
            normalized_document=None,
            issues=issues,
        )

    def _read_failed(self, file_path: str | Path, exc: Exception) -> ParserResult:
        return self._failed(
            ParserIssue(
                code=f"{self.resource_type}.read_failed",
                message="Parser cannot read the resource file.",
                details={"path": str(file_path), "error": str(exc)},
            )
        )


def clean_text(text: str | None) -> str:
    if text is None:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    normalized = _GARBLED_TEXT_RE.sub("", normalized)
    lines = [line.strip() for line in normalized.split("\n")]
    return "\n".join(line for line in lines if line and not _is_noise_line(line))


def text_quality_issue(text: str | None) -> Literal["empty", "garbled"] | None:
    if text is None:
        return "empty"
    if _GARBLED_TEXT_RE.search(text):
        return "garbled"
    cleaned = clean_text(text)
    if not cleaned:
        return "empty"
    if _looks_like_garbled_text(cleaned):
        return "garbled"
    return None


def has_garbled_text(text: str | None) -> bool:
    return _GARBLED_TEXT_RE.search(text or "") is not None


def _clean_segments(segments: list[NormalizedSegment]) -> list[NormalizedSegment]:
    clean_segments: list[NormalizedSegment] = []
    for segment in segments:
        text = clean_text(str(segment.get("textContent", "")))
        if not text or has_garbled_text(text):
            continue

        clean_segment = dict(segment)
        clean_segment["textContent"] = text

        section_path = clean_segment.get("sectionPath")
        if isinstance(section_path, list):
            clean_path = [clean_text(str(item)) for item in section_path]
            clean_segment["sectionPath"] = [item for item in clean_path if item]

        clean_segments.append(clean_segment)

    return clean_segments


def _is_noise_line(line: str) -> bool:
    if _PURE_DOT_LINE_RE.match(line):
        return True
    if _REPEATED_SYMBOL_LINE_RE.match(line):
        return True
    if any(char in _USEFUL_MATH_CHARS for char in line):
        return False
    return _PURE_NOISE_LINE_RE.match(line) is not None


def _looks_like_garbled_text(text: str) -> bool:
    visible_chars = [char for char in text if not char.isspace()]
    if not visible_chars:
        return True

    useful_chars = [
        char
        for char in visible_chars
        if char.isalnum() or "\u4e00" <= char <= "\u9fff" or char in _USEFUL_MATH_CHARS
    ]
    return len(visible_chars) >= 8 and len(useful_chars) / len(visible_chars) < 0.2


@dataclass(frozen=True)
class ParserScaffold:
    resource_type: str
    owner: str

    def status(self) -> str:
        return "placeholder"
