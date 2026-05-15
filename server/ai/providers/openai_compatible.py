from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from server.ai.core.errors import AIProviderError
from server.ai.core.json_output import message_content_to_text, parse_json_object
from server.ai.core.types import AIModelResult, JsonChatRequest, VisionJsonRequest
from server.ai.providers.deepseek_chat import _to_langchain_messages
from server.ai.providers.vision_chat import build_vision_content


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    model: str
    base_url: str
    timeout_sec: float = 30.0


ChatFactory = Callable[..., Any]


class OpenAICompatibleJsonClient:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        chat_factory: ChatFactory = ChatOpenAI,
    ) -> None:
        self._config = config
        self._chat_factory = chat_factory

    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        try:
            chat = self._chat_factory(
                **_chat_kwargs(
                    config=self._config,
                    model=request.model,
                    temperature=request.temperature,
                    timeout_sec=request.timeout_sec,
                    response_format=request.response_format,
                )
            )
            message = chat.invoke(_to_langchain_messages(request.messages))
        except Exception as exc:  # noqa: BLE001 - provider SDK errors are normalized at this boundary.
            raise AIProviderError(f"openai-compatible provider call failed: {exc}") from exc

        text = message_content_to_text(getattr(message, "content", message))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=message)


class OpenAICompatibleVisionJsonClient:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        chat_factory: ChatFactory = ChatOpenAI,
    ) -> None:
        self._config = config
        self._chat_factory = chat_factory

    def complete_vision_json(self, request: VisionJsonRequest) -> AIModelResult:
        content = build_vision_content(request.prompt, request.images)
        try:
            chat = self._chat_factory(
                **_chat_kwargs(
                    config=self._config,
                    model=request.model,
                    temperature=request.temperature,
                    timeout_sec=request.timeout_sec,
                    response_format={"type": "json_object"},
                )
            )
            message = chat.invoke([HumanMessage(content=content)])
        except Exception as exc:  # noqa: BLE001 - provider SDK errors are normalized at this boundary.
            raise AIProviderError(f"openai-compatible vision provider call failed: {exc}") from exc

        text = message_content_to_text(getattr(message, "content", message))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=message)


def _chat_kwargs(
    *,
    config: OpenAICompatibleConfig,
    model: str,
    temperature: float,
    timeout_sec: float,
    response_format: dict[str, Any] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model or config.model,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "temperature": temperature,
        "timeout": timeout_sec or config.timeout_sec,
    }
    if response_format:
        kwargs["model_kwargs"] = {"response_format": response_format}
    return kwargs
