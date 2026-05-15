from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek

from server.ai.core.errors import AIProviderError
from server.ai.core.json_output import message_content_to_text, parse_json_object
from server.ai.core.types import AIModelResult, ChatMessage, JsonChatRequest


@dataclass(frozen=True)
class DeepSeekLangChainConfig:
    api_key: str
    model: str
    base_url: str | None = None
    timeout_sec: float = 30.0


ChatFactory = Callable[..., Any]


def _message_role_and_content(message: ChatMessage | Mapping[str, Any]) -> tuple[str, str]:
    if isinstance(message, Mapping):
        role = message.get("role", "user")
        if not isinstance(role, str):
            role = "user"
        return role, message_content_to_text(message.get("content"))
    return message.role, message.content


def _to_langchain_messages(messages: Sequence[ChatMessage | Mapping[str, Any]]) -> list[BaseMessage]:
    langchain_messages: list[BaseMessage] = []
    for message in messages:
        role, content = _message_role_and_content(message)
        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        else:
            langchain_messages.append(HumanMessage(content=content))
    return langchain_messages


class DeepSeekLangChainJsonClient:
    def __init__(
        self,
        config: DeepSeekLangChainConfig,
        *,
        chat_factory: ChatFactory = ChatDeepSeek,
    ) -> None:
        self._config = config
        self._chat_factory = chat_factory

    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        kwargs: dict[str, Any] = {
            "model": request.model or self._config.model,
            "api_key": self._config.api_key,
            "temperature": request.temperature,
            "timeout": request.timeout_sec or self._config.timeout_sec,
        }
        if request.response_format:
            kwargs["model_kwargs"] = {"response_format": request.response_format}
        max_tokens = request.metadata.get("max_tokens")
        if isinstance(max_tokens, int) and not isinstance(max_tokens, bool):
            kwargs["max_tokens"] = max_tokens
        reasoning_effort = request.metadata.get("reasoning_effort")
        if isinstance(reasoning_effort, str):
            kwargs["reasoning_effort"] = reasoning_effort
        if self._config.base_url:
            kwargs[_base_url_argument_name(self._chat_factory)] = self._config.base_url

        try:
            chat = self._chat_factory(**kwargs)
            message = chat.invoke(_to_langchain_messages(request.messages))
        except Exception as exc:  # noqa: BLE001 - provider SDK errors are normalized at this boundary.
            raise AIProviderError(f"deepseek provider call failed: {exc}") from exc

        text = message_content_to_text(getattr(message, "content", message))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=message)


def _base_url_argument_name(chat_factory: ChatFactory) -> str:
    try:
        parameters = inspect.signature(chat_factory).parameters
    except (TypeError, ValueError):
        return "api_base"
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return "api_base"
    if "api_base" in parameters:
        return "api_base"
    return "base_url"
