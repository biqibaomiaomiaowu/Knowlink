from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class AIGraphNode:
    key: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIGraphEdge:
    source_key: str
    target_key: str
    relation: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIGraphDraft:
    nodes: Sequence[AIGraphNode]
    edges: Sequence[AIGraphEdge]
