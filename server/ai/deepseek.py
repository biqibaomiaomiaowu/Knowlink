from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping


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
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._timeout_sec = timeout_sec
        self._label = label

    def complete_json(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> dict[str, Any]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": self._reasoning_effort,
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{_chat_base_url(self._base_url)}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                body = response.read().decode("utf-8")
            chat_payload = json.loads(body)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{self._label} request failed: {exc}") from exc

        return parse_chat_json_payload(chat_payload, label=self._label)


def parse_chat_json_payload(payload: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    if "error" in payload:
        raise RuntimeError(f"{label} failed: {payload['error']}")

    try:
        content = payload["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{label} response missing message content") from exc

    json_text = _extract_json_object(_message_content_to_text(content))
    if json_text is None:
        raise RuntimeError(f"{label} response is not JSON")

    try:
        model_payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} response has invalid JSON: {exc}") from exc
    if not isinstance(model_payload, dict):
        raise RuntimeError(f"{label} JSON must be an object")
    return model_payload


def _chat_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed[:-3]
    return trimmed


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_json_object(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return None
