from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizeParserOutput:
    target: str = "citation"

    def status(self) -> str:
        return "placeholder"
