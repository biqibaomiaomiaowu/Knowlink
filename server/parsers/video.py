from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from server.ai.asr import AsrClient, get_configured_asr_client
from server.ai.vision import VisionClient, get_configured_vision_client
from server.parsers.base import BaseParser, ParserIssue, ParserResult
from server.parsers.video_visual import (
    FfmpegFrameExtractor,
    VideoFrameCandidate,
    analyze_video_frames,
    build_video_visual_segments,
    candidate_timestamps_from_captions,
)


class VideoParser(BaseParser):
    resource_type = "mp4"

    def __init__(
        self,
        asr_client: AsrClient | None = None,
        *,
        vision_client: VisionClient | None = None,
        frame_extractor: Any | None = None,
        enable_visual_parse: bool | None = None,
    ) -> None:
        self._asr_client = asr_client if asr_client is not None else get_configured_asr_client()
        self._vision_client = vision_client
        self._frame_extractor = frame_extractor
        self._enable_visual_parse = (
            _env_bool("KNOWLINK_ENABLE_VIDEO_VISUAL_PARSE")
            if enable_visual_parse is None
            else enable_visual_parse
        )

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

        if self._enable_visual_parse:
            visual_segments, visual_issues = self._parse_visual_segments(file_path, segments)
            segments.extend(visual_segments)
            issues.extend(visual_issues)

        return self._succeeded(segments, issues)

    def _parse_visual_segments(
        self,
        file_path: str | Path,
        caption_segments: list[dict[str, Any]],
    ) -> tuple[list[dict[str, object]], list[ParserIssue]]:
        candidates: list[VideoFrameCandidate] = []
        issues: list[ParserIssue] = []
        for index, (timestamp_sec, start_sec, end_sec) in enumerate(
            candidate_timestamps_from_captions(caption_segments),
            start=1,
        ):
            try:
                image_bytes = self._resolve_frame_extractor().extract_frame(file_path, timestamp_sec=timestamp_sec)
            except Exception as exc:
                issues.append(
                    ParserIssue(
                        code="mp4.frame_extract_failed",
                        message="MP4 frame extraction failed.",
                        details={"timestampSec": timestamp_sec, "error": str(exc)},
                    )
                )
                continue

            timestamp_key = int(timestamp_sec)
            candidates.append(
                VideoFrameCandidate(
                    asset_id=f"mp4-f-{timestamp_key:06d}",
                    image_key=f"frames/mp4/{Path(file_path).stem}/{timestamp_key:06d}.png",
                    image_bytes=image_bytes,
                    mime_type="image/png",
                    start_sec=start_sec,
                    end_sec=end_sec,
                    order_no=len(caption_segments) + index,
                )
            )

        visual_results, visual_issues = analyze_video_frames(
            candidates=candidates,
            vision_client=self._resolve_vision_client(),
        )
        issues.extend(visual_issues)
        visual_segments = build_video_visual_segments(candidates, visual_results, key_prefix="mp4-vf")
        _renumber_segments(visual_segments, start_order_no=len(caption_segments) + 1)
        return visual_segments, issues

    def _resolve_vision_client(self) -> VisionClient | None:
        if self._vision_client is None:
            self._vision_client = get_configured_vision_client()
        return self._vision_client

    def _resolve_frame_extractor(self) -> Any:
        if self._frame_extractor is None:
            self._frame_extractor = FfmpegFrameExtractor()
        return self._frame_extractor


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _renumber_segments(segments: list[dict[str, object]], *, start_order_no: int) -> None:
    for index, segment in enumerate(segments, start=start_order_no):
        segment["orderNo"] = index
