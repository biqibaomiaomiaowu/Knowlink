from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class VideoFrameCandidate:
    timestamp_sec: float
    image_bytes: bytes
    mime_type: str = "image/png"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoFrameExtractionRequest:
    video_path: str | Path
    sample_interval_sec: float
    max_frames: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VideoFrameExtractionResult:
    frames: Sequence[VideoFrameCandidate]
    issues: tuple[str, ...] = ()
