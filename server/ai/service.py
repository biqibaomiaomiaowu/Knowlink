from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from server.ai.asr import AsrClient
from server.ai.core.errors import AIConfigurationError
from server.ai.core.types import AIModelResult, AIProviderName, JsonChatRequest, VisionJsonRequest
from server.ai.ocr import OcrClient


class JsonChatClient(Protocol):
    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        """Complete a JSON chat request."""


class VisionJsonClient(Protocol):
    def complete_vision_json(self, request: VisionJsonRequest) -> AIModelResult:
        """Complete a multimodal JSON request."""


@dataclass(frozen=True)
class AIService:
    json_clients: dict[AIProviderName, JsonChatClient]
    vision_clients: dict[AIProviderName, VisionJsonClient]
    asr_client: AsrClient | None = None
    ocr_client: OcrClient | None = None

    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        client = self.json_clients.get(request.provider)
        if client is None:
            raise AIConfigurationError(f"AI JSON provider is not configured: {request.provider}")
        return client.complete_json(request)

    def complete_vision_json(self, request: VisionJsonRequest) -> AIModelResult:
        client = self.vision_clients.get(request.provider)
        if client is None:
            raise AIConfigurationError(f"AI vision provider is not configured: {request.provider}")
        return client.complete_vision_json(request)


@lru_cache(maxsize=1)
def get_default_ai_service() -> AIService:
    from server.ai.providers.registry import build_default_ai_service

    return build_default_ai_service()
