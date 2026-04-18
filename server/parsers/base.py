from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParserScaffold:
    resource_type: str
    owner: str

    def status(self) -> str:
        return "placeholder"
