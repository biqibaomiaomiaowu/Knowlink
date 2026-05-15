from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class AIGradingCriterion:
    key: str
    label: str
    max_score: float


@dataclass(frozen=True)
class AIGradingRequest:
    answer_text: str
    criteria: Sequence[AIGradingCriterion]
    metadata: dict[str, Any] = field(default_factory=dict)
