from __future__ import annotations

import math
import re
from pathlib import Path

from server.parsers.base import BaseParser, ParserIssue, ParserResult, clean_text


_TIMELINE_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})(?:\s+.*)?$"
)
_TIMECODE_RE = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{1,3})$")


class SrtParser(BaseParser):
    resource_type = "srt"

    def parse(self, file_path: str | Path) -> ParserResult:
        try:
            raw_text = Path(file_path).read_text(encoding="utf-8-sig")
        except Exception as exc:
            return self._read_failed(file_path, exc)

        blocks = [block.strip() for block in re.split(r"\n\s*\n", raw_text.replace("\r\n", "\n").replace("\r", "\n"))]
        blocks = [block for block in blocks if block]
        if not blocks:
            return self._failed(
                ParserIssue(
                    code="srt.caption_empty",
                    message="SRT has no parseable caption blocks.",
                )
            )

        issues: list[ParserIssue] = []
        segments: list[dict[str, object]] = []

        for block_no, block in enumerate(blocks, start=1):
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if lines and lines[0].isdigit():
                lines = lines[1:]
            if len(lines) < 2:
                return self._failed(
                    ParserIssue(
                        code="srt.timeline_invalid",
                        message="SRT caption block is missing a timeline or text.",
                        details={"blockNo": block_no},
                    )
                )

            match = _TIMELINE_RE.match(lines[0])
            if match is None:
                return self._failed(
                    ParserIssue(
                        code="srt.timeline_invalid",
                        message="SRT caption block has an invalid timeline format.",
                        details={"blockNo": block_no, "timeline": lines[0]},
                    )
                )

            try:
                start_ms = _timecode_to_ms(match.group("start"))
                end_ms = _timecode_to_ms(match.group("end"))
            except ValueError as exc:
                return self._failed(
                    ParserIssue(
                        code="srt.timeline_invalid",
                        message="SRT caption block has invalid timeline values.",
                        details={"blockNo": block_no, "timeline": lines[0], "error": str(exc)},
                    )
                )
            if end_ms <= start_ms:
                return self._failed(
                    ParserIssue(
                        code="srt.timeline_invalid",
                        message="SRT caption end time must be later than start time.",
                        details={"blockNo": block_no, "timeline": lines[0]},
                    )
                )

            text = clean_text("\n".join(lines[1:]))
            if not text:
                issues.append(
                    ParserIssue(
                        code="srt.caption_text_empty",
                        message="SRT caption block has empty text and was skipped.",
                        details={"blockNo": block_no},
                    )
                )
                continue

            segments.append(
                {
                    "segmentKey": f"srt-c{block_no}",
                    "segmentType": "video_caption",
                    "orderNo": block_no,
                    "textContent": text,
                    "startSec": start_ms // 1000,
                    "endSec": math.ceil(end_ms / 1000),
                }
            )

        if not segments:
            return self._failed_with_issues(
                issues
                or [
                    ParserIssue(
                        code="srt.caption_empty",
                        message="SRT has no parseable caption text.",
                    )
                ]
            )

        return self._succeeded(segments, issues)


def _timecode_to_ms(timecode: str) -> int:
    match = _TIMECODE_RE.match(timecode)
    if match is None:
        raise ValueError(f"invalid SRT timecode: {timecode}")

    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"invalid SRT timecode: {timecode}")
    millis = int(match.group("ms").ljust(3, "0"))
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis
