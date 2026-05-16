from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsingEnhancementRequest:
    resource_id: str
    segment_text: str
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsingEnhancementResult:
    enhanced_text: str
    confidence: float
    issues: tuple[str, ...] = ()
