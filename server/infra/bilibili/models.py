from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class BilibiliSourceType(StrEnum):
    SINGLE_VIDEO = "single_video"
    MULTI_P = "multi_p"
    COLLECTION = "collection"
    BANGUMI = "bangumi"


@dataclass(frozen=True)
class BilibiliPart:
    part_id: str
    title: str
    duration_sec: int
    cid: str
    page_no: int
    selected_by_default: bool = False

    def to_api(self) -> dict[str, object]:
        return {
            "partId": self.part_id,
            "title": self.title,
            "durationSec": self.duration_sec,
            "cid": self.cid,
            "pageNo": self.page_no,
            "selectedByDefault": self.selected_by_default,
        }


@dataclass(frozen=True)
class BilibiliPreview:
    preview_id: str
    source_url: str
    source_type: BilibiliSourceType
    title: str
    cover_url: str | None
    total_parts: int
    parts: list[BilibiliPart]
    default_selection_mode: Literal["current_part", "all_parts", "selected_parts"]

    def to_api(self) -> dict[str, object]:
        return {
            "previewId": self.preview_id,
            "sourceUrl": self.source_url,
            "sourceType": self.source_type.value,
            "title": self.title,
            "coverUrl": self.cover_url,
            "totalParts": self.total_parts,
            "parts": [part.to_api() for part in self.parts],
            "defaultSelectionMode": self.default_selection_mode,
        }
