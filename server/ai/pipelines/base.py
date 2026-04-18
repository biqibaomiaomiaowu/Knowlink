from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScaffoldPipeline:
    name: str
    owner: str

    def status(self) -> str:
        return "placeholder"
