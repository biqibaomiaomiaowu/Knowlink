from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.ai.vision import VisionAssetResult, VisionClient, VisualAsset, analyze_visual_assets
from server.parsers.base import ParserIssue, clean_text


@dataclass(frozen=True)
class VideoFrameCandidate:
    asset_id: str
    image_key: str
    image_bytes: bytes
    mime_type: str
    start_sec: int
    end_sec: int
    order_no: int


class FfmpegFrameExtractor:
    def extract_frame(self, video_path: str | Path, *, timestamp_sec: float) -> bytes:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_path = Path(tmp_file.name)
        tmp_file.close()

        try:
            command = [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp_sec),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-f",
                "image2",
                str(tmp_path),
            ]
            result = subprocess.run(command, capture_output=True, check=False)
            if result.returncode != 0:
                error = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"ffmpeg frame extraction failed: {error}")

            image_bytes = tmp_path.read_bytes()
            if not image_bytes:
                raise RuntimeError("ffmpeg frame extraction produced an empty image.")
            return image_bytes
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg executable is not available.") from exc
        finally:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass


def candidate_timestamps_from_captions(
    caption_segments: list[dict[str, Any]],
    *,
    max_frames: int = 12,
) -> list[tuple[float, int, int]]:
    timestamps: list[tuple[float, int, int]] = []
    for segment in caption_segments:
        start_sec = _timeline_value(segment, "startSec")
        end_sec = _timeline_value(segment, "endSec")
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            continue

        midpoint = start_sec + (end_sec - start_sec) / 2
        timestamps.append((midpoint, int(start_sec), int(_ceil(end_sec))))
        if len(timestamps) >= max_frames:
            break
    return timestamps


def build_video_visual_segments(
    candidates: list[VideoFrameCandidate],
    results: list[VisionAssetResult],
    *,
    key_prefix: str,
) -> list[dict[str, object]]:
    results_by_asset_id: dict[str, list[VisionAssetResult]] = {}
    for result in results:
        results_by_asset_id.setdefault(result.asset_id, []).append(result)

    segments: list[dict[str, object]] = []
    timeline_counts: dict[tuple[int, str], int] = {}
    for candidate in candidates:
        candidate_segment_count = 0
        for result in results_by_asset_id.get(candidate.asset_id, []):
            text = clean_text(result.text)
            short_type = _VISUAL_SEGMENT_KEY_TYPES.get(result.segment_type)
            if not text or short_type is None:
                continue

            timeline_key = (candidate.start_sec, short_type)
            timeline_counts[timeline_key] = timeline_counts.get(timeline_key, 0) + 1
            segment: dict[str, object] = {
                "segmentKey": f"{key_prefix}-{candidate.start_sec}-{short_type}-{timeline_counts[timeline_key]}",
                "segmentType": result.segment_type,
                "orderNo": candidate.order_no + candidate_segment_count,
                "textContent": text,
                "startSec": candidate.start_sec,
                "endSec": candidate.end_sec,
                "imageKey": candidate.image_key,
            }
            if result.segment_type == "formula":
                segment["formulaText"] = text
            segments.append(segment)
            candidate_segment_count += 1
    return segments


def analyze_video_frames(
    candidates: list[VideoFrameCandidate],
    vision_client: VisionClient | None,
) -> tuple[list[VisionAssetResult], list[ParserIssue]]:
    if vision_client is None or not candidates:
        return [], []

    assets = [
        VisualAsset(
            asset_id=candidate.asset_id,
            image_bytes=candidate.image_bytes,
            mime_type=candidate.mime_type,
            location={"startSec": candidate.start_sec, "endSec": candidate.end_sec},
            hint="mp4_timeline_visual",
        )
        for candidate in candidates
    ]
    try:
        return analyze_visual_assets(vision_client, assets, resource_type="mp4"), []
    except Exception as exc:
        return [], [
            ParserIssue(
                code="mp4.visual_failed",
                message="MP4 timeline visual analysis failed.",
                details={"error": str(exc)},
            )
        ]


_VISUAL_SEGMENT_KEY_TYPES = {
    "formula": "formula",
    "ocr_text": "ocr",
    "image_caption": "image",
}


def _timeline_value(segment: dict[str, Any], key: str) -> float | None:
    value = segment.get(key)
    if not isinstance(value, int | float):
        return None
    return float(value)


def _ceil(value: float) -> int:
    number = int(value)
    if value == number:
        return number
    return number + 1
