from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AIStreamEnvelope:
    kind: str
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class StreamEventSink(Protocol):
    def emit(self, event: AIStreamEnvelope) -> None:
        ...
