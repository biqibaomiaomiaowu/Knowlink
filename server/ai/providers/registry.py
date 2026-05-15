from __future__ import annotations

import os

from server.ai.asr import get_configured_asr_client
from server.ai.core.types import AIProviderName
from server.ai.ocr import get_configured_ocr_client
from server.ai.providers.deepseek_chat import DeepSeekLangChainConfig, DeepSeekLangChainJsonClient
from server.ai.providers.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleJsonClient,
    OpenAICompatibleVisionJsonClient,
)
from server.ai.service import AIService, JsonChatClient, VisionJsonClient


_DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
_DEFAULT_VIVO_BASE_URL = "https://api-ai.vivo.com.cn/v1"
_DEFAULT_VIVO_TEXT_MODEL = "Doubao-Seed-2.0-pro"
_DEFAULT_VIVO_VISION_MODEL = "Doubao-Seed-2.0-mini"


def build_default_ai_service() -> AIService:
    json_clients: dict[AIProviderName, JsonChatClient] = {}
    vision_clients: dict[AIProviderName, VisionJsonClient] = {}

    deepseek = _build_deepseek_client()
    if deepseek is not None:
        json_clients["deepseek"] = deepseek

    vivo_chat = _build_vivo_chat_client()
    if vivo_chat is not None:
        json_clients["vivo"] = vivo_chat

    vivo_vision = _build_vivo_vision_client()
    if vivo_vision is not None:
        vision_clients["vivo"] = vivo_vision

    return AIService(
        json_clients=json_clients,
        vision_clients=vision_clients,
        asr_client=get_configured_asr_client(),
        ocr_client=get_configured_ocr_client(),
    )


def _build_deepseek_client() -> DeepSeekLangChainJsonClient | None:
    api_key = os.getenv("KNOWLINK_DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    return DeepSeekLangChainJsonClient(
        DeepSeekLangChainConfig(
            api_key=api_key,
            model=_env_str("KNOWLINK_DEEPSEEK_MODEL", _DEFAULT_DEEPSEEK_MODEL),
            base_url=_env_optional_str("KNOWLINK_DEEPSEEK_BASE_URL"),
            timeout_sec=_env_float("KNOWLINK_DEEPSEEK_TIMEOUT_SEC", 30.0),
        )
    )


def _build_vivo_chat_client() -> OpenAICompatibleJsonClient | None:
    if not _env_bool("KNOWLINK_ENABLE_VIVO_CHAT"):
        return None
    api_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not api_key:
        return None
    return OpenAICompatibleJsonClient(
        OpenAICompatibleConfig(
            api_key=api_key,
            model=_env_str("KNOWLINK_VIVO_CHAT_MODEL", _DEFAULT_VIVO_TEXT_MODEL),
            base_url=_env_str("KNOWLINK_VIVO_BASE_URL", _DEFAULT_VIVO_BASE_URL),
            timeout_sec=_env_float("KNOWLINK_VIVO_CHAT_TIMEOUT_SEC", 30.0),
        )
    )


def _build_vivo_vision_client() -> OpenAICompatibleVisionJsonClient | None:
    if not _env_bool("KNOWLINK_ENABLE_VIVO_VISION"):
        return None
    api_key = os.getenv("KNOWLINK_VIVO_APP_KEY", "").strip()
    if not api_key:
        return None
    return OpenAICompatibleVisionJsonClient(
        OpenAICompatibleConfig(
            api_key=api_key,
            model=_env_str("KNOWLINK_VIVO_VISION_MODEL", _DEFAULT_VIVO_VISION_MODEL),
            base_url=_env_str("KNOWLINK_VIVO_BASE_URL", _DEFAULT_VIVO_BASE_URL),
            timeout_sec=_env_float("KNOWLINK_VIVO_VISION_TIMEOUT_SEC", 30.0),
        )
    )


def _env_bool(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _env_optional_str(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
