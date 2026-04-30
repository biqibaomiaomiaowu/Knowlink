from __future__ import annotations

from pathlib import Path

from server.parsers.base import BaseParser, ParserIssue, ParserResult


class VideoParser(BaseParser):
    resource_type = "mp4"

    def parse(self, file_path: str | Path) -> ParserResult:
        return self._failed(
            ParserIssue(
                code="mp4.asr_not_configured",
                message="ASR is not configured; provide an SRT file or configure ASR later.",
                details={"path": str(file_path)},
            )
        )
