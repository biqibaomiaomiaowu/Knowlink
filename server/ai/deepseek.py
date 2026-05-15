from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from server.ai.core.errors import AIOutputParseError, AIProviderError
from server.ai.core.json_output import message_content_to_text, parse_json_object
from server.ai.core.types import ChatMessage, JsonChatRequest
from server.ai.providers.deepseek_chat import DeepSeekLangChainConfig, DeepSeekLangChainJsonClient


_DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
_DEFAULT_DEEPSEEK_REASONING_EFFORT = "high"


@dataclass(frozen=True)
class DeepSeekChatConfig:
    api_key: str
    base_url: str
    model: str
    reasoning_effort: str


def get_configured_deepseek_chat_config() -> DeepSeekChatConfig | None:
    api_key = os.getenv("KNOWLINK_DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    return DeepSeekChatConfig(
        api_key=api_key,
        base_url=os.getenv("KNOWLINK_DEEPSEEK_BASE_URL", _DEFAULT_DEEPSEEK_BASE_URL).strip()
        or _DEFAULT_DEEPSEEK_BASE_URL,
        model=os.getenv("KNOWLINK_DEEPSEEK_MODEL", _DEFAULT_DEEPSEEK_MODEL).strip()
        or _DEFAULT_DEEPSEEK_MODEL,
        reasoning_effort=os.getenv(
            "KNOWLINK_DEEPSEEK_REASONING_EFFORT",
            _DEFAULT_DEEPSEEK_REASONING_EFFORT,
        ).strip()
        or _DEFAULT_DEEPSEEK_REASONING_EFFORT,
    )


class DeepSeekJsonChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str,
        timeout_sec: float,
        label: str,
        langchain_client: DeepSeekLangChainJsonClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._timeout_sec = timeout_sec
        self._label = label
        self._langchain_client = langchain_client

    def complete_json(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> dict[str, Any]:
        request = JsonChatRequest(
            provider="deepseek",
            model=self._model,
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ],
            timeout_sec=self._timeout_sec,
            response_format={"type": "json_object"},
            metadata={
                "max_tokens": max_tokens,
                "reasoning_effort": self._reasoning_effort,
            },
        )

        try:
            result = self._get_langchain_client().complete_json(request)
        except AIProviderError as exc:
            raise RuntimeError(f"{self._label} request failed: {exc}") from exc
        except AIOutputParseError as exc:
            raise RuntimeError(_parse_error_message(exc, label=self._label)) from exc

        if isinstance(result.parsed_json, dict):
            return result.parsed_json
        try:
            return parse_json_object(result.text)
        except AIOutputParseError as exc:
            raise RuntimeError(_parse_error_message(exc, label=self._label)) from exc

    def _get_langchain_client(self) -> DeepSeekLangChainJsonClient:
        if self._langchain_client is None:
            self._langchain_client = DeepSeekLangChainJsonClient(
                DeepSeekLangChainConfig(
                    api_key=self._api_key,
                    model=self._model,
                    base_url=self._base_url,
                    timeout_sec=self._timeout_sec,
                )
            )
        return self._langchain_client


def parse_chat_json_payload(payload: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if "error" in payload:
        raise RuntimeError(f"{label} failed: {payload['error']}")

    try:
        content = payload["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{label} response missing message content") from exc

    try:
        return parse_json_object(message_content_to_text(content))
    except AIOutputParseError as exc:
        raise RuntimeError(_parse_error_message(exc, label=label)) from exc


def _chat_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed[:-3]
    return trimmed


def _parse_error_message(error: AIOutputParseError, *, label: str) -> str:
    message = str(error)
    if "JSON root must be an object" in message:
        return f"{label} JSON must be an object"
    if "invalid JSON" in message:
        return f"{label} response has invalid JSON: {message}"
    return f"{label} response is not JSON"
