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
_SUPPORTED_REASONING_EFFORTS = {"low", "medium", "high"}
_STRUCTURED_OUTPUT_ERROR_MARKERS = (
    "response_format",
    "json_schema",
    "structured output",
    "json_object",
)
_UNSUPPORTED_ERROR_MARKERS = (
    "not support",
    "unsupported",
    "invalid",
    "unknown",
    "unrecognized",
    "not accepted",
    "not allowed",
    "extra inputs are not permitted",
)


def normalize_deepseek_base_url(base_url: str | None) -> str | None:
    if base_url is None:
        return None
    trimmed = base_url.rstrip("/")
    if not trimmed:
        return None
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


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
        if isinstance(max_tokens, int) and not isinstance(max_tokens, bool) and max_tokens > 0:
            kwargs["max_tokens"] = max_tokens
        reasoning_effort = request.metadata.get("reasoning_effort")
        if isinstance(reasoning_effort, str) and reasoning_effort in _SUPPORTED_REASONING_EFFORTS:
            kwargs["reasoning_effort"] = reasoning_effort
        base_url = normalize_deepseek_base_url(self._config.base_url)
        if base_url:
            kwargs[_base_url_argument_name(self._chat_factory)] = base_url

        try:
            message = self._invoke_chat(kwargs, request)
        except Exception as exc:  # noqa: BLE001 - provider SDK errors are normalized at this boundary.
            if request.response_format and _is_unsupported_structured_output_error(exc):
                fallback_kwargs = dict(kwargs)
                fallback_kwargs.pop("model_kwargs", None)
                try:
                    message = self._invoke_chat(fallback_kwargs, request)
                except Exception as retry_exc:  # noqa: BLE001 - provider SDK errors are normalized at this boundary.
                    raise AIProviderError(f"deepseek provider call failed: {retry_exc}") from retry_exc
            else:
                raise AIProviderError(f"deepseek provider call failed: {exc}") from exc

        text = message_content_to_text(getattr(message, "content", message))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=message)

    def _invoke_chat(self, kwargs: dict[str, Any], request: JsonChatRequest) -> Any:
        chat = self._chat_factory(**kwargs)
        return chat.invoke(_to_langchain_messages(request.messages))


def _is_unsupported_structured_output_error(error: Exception) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in _STRUCTURED_OUTPUT_ERROR_MARKERS) and any(
        marker in message for marker in _UNSUPPORTED_ERROR_MARKERS
    )


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
