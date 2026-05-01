from __future__ import annotations

from pathlib import Path

from server.ai.asr import AsrClient, get_configured_asr_client
from server.parsers.base import BaseParser, ParserIssue, ParserResult


class VideoParser(BaseParser):
    resource_type = "mp4"

    def __init__(self, asr_client: AsrClient | None = None) -> None:
        self._asr_client = asr_client if asr_client is not None else get_configured_asr_client()

    def parse(self, file_path: str | Path) -> ParserResult:
        if self._asr_client is not None:
            return self._parse_with_asr(file_path)

        return self._failed(
            ParserIssue(
                code="mp4.asr_not_configured",
                message="ASR is not configured; provide an SRT file or configure ASR later.",
                details={"path": str(file_path)},
            )
        )

    def _parse_with_asr(self, file_path: str | Path) -> ParserResult:
        try:
            asr_segments = self._asr_client.transcribe(file_path)
        except Exception as exc:
            return self._failed(
                ParserIssue(
                    code="mp4.asr_failed",
                    message="ASR failed to transcribe the video.",
                    details={"path": str(file_path), "error": str(exc)},
                )
            )

        issues: list[ParserIssue] = []
        segments: list[dict[str, object]] = []
        for index, asr_segment in enumerate(asr_segments, start=1):
            start_sec = int(asr_segment.start_sec)
            end_sec = int(asr_segment.end_sec)
            if end_sec <= start_sec:
                issues.append(
                    ParserIssue(
                        code="mp4.asr_timeline_invalid",
                        message="ASR segment end time must be later than start time.",
                        details={"segmentNo": index, "startSec": start_sec, "endSec": end_sec},
                    )
                )
                continue

            segments.append(
                {
                    "segmentKey": f"mp4-c{index}",
                    "segmentType": "video_caption",
                    "orderNo": index,
                    "textContent": asr_segment.text,
                    "startSec": start_sec,
                    "endSec": end_sec,
                }
            )

        if not segments:
            return self._failed_with_issues(
                issues
                or [
                    ParserIssue(
                        code="mp4.asr_empty",
                        message="ASR returned no usable caption segments.",
                        details={"path": str(file_path)},
                    )
                ]
            )

        return self._succeeded(segments, issues)
