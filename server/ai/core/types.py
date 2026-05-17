from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence


ChatRole = Literal["system", "user", "assistant"]
AIProviderName = Literal["deepseek", "vivo", "custom"]
StreamEventKind = Literal["token", "message", "error", "done"]
LocalImagePath = str | Path


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class JsonChatRequest:
    provider: AIProviderName
    model: str
    messages: Sequence[ChatMessage]
    temperature: float = 0.2
    timeout_sec: float = 30.0
    response_format: dict[str, Any] | None = field(default_factory=lambda: {"type": "json_object"})
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisionImage:
    mime_type: str
    data: bytes
    source_name: str | None = None


@dataclass(frozen=True)
class VisionJsonRequest:
    provider: AIProviderName
    model: str
    prompt: str
    images: Sequence[VisionImage]
    temperature: float = 0.1
    timeout_sec: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIModelResult:
    text: str
    parsed_json: dict[str, Any] | None = None
    raw: Any = None
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass(frozen=True)
class StreamChatRequest:
    provider: AIProviderName
    model: str
    messages: Sequence[ChatMessage]
    temperature: float = 0.2
    timeout_sec: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIStreamEvent:
    kind: StreamEventKind
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
