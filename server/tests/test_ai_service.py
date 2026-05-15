from __future__ import annotations

from typing import Any, Sequence

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from server.ai.core import AIConfigurationError, ChatMessage, JsonChatRequest, VisionImage, VisionJsonRequest
from server.ai.providers.deepseek_chat import DeepSeekLangChainConfig, DeepSeekLangChainJsonClient
from server.ai.providers.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleJsonClient
from server.ai.providers.openai_compatible import OpenAICompatibleVisionJsonClient
from server.ai.providers.registry import build_default_ai_service
from server.ai.providers.vision_chat import image_to_data_url
from server.ai.service import AIService


class FakeChatModel:
    def __init__(self, response: str = '{"ok": true}', **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.invocations: list[Sequence[Any]] = []
        self.response = response

    def invoke(self, messages: Sequence[Any]) -> AIMessage:
        self.invocations.append(messages)
        return AIMessage(content=self.response)


def test_ai_service_raises_when_provider_is_not_configured() -> None:
    service = AIService(json_clients={}, vision_clients={})

    with pytest.raises(AIConfigurationError, match="deepseek"):
        service.complete_json(
            JsonChatRequest(
                provider="deepseek",
                model="deepseek-chat",
                messages=[ChatMessage(role="user", content="Return JSON")],
            )
        )

    with pytest.raises(AIConfigurationError, match="vivo"):
        service.complete_vision_json(
            VisionJsonRequest(
                provider="vivo",
                model="vision-model",
                prompt="Return JSON",
                images=[VisionImage(mime_type="image/png", data=b"png")],
            )
        )


def test_deepseek_langchain_client_uses_factory_messages_and_json_mode() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('prefix {"answer": 42}', **kwargs)
        created.append(model)
        return model

    client = DeepSeekLangChainJsonClient(
        DeepSeekLangChainConfig(
            api_key="deepseek-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            timeout_sec=9,
        ),
        chat_factory=chat_factory,
    )

    result = client.complete_json(
        JsonChatRequest(
            provider="deepseek",
            model="request-model-ignored",
            messages=[
                ChatMessage(role="system", content="system prompt"),
                ChatMessage(role="assistant", content="previous answer"),
                ChatMessage(role="user", content="question"),
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
    )

    assert result.parsed_json == {"answer": 42}
    assert result.text == 'prefix {"answer": 42}'
    assert len(created) == 1
    assert created[0].kwargs["model"] == "deepseek-v4-flash"
    assert created[0].kwargs["api_key"] == "deepseek-key"
    assert created[0].kwargs["timeout"] == 9
    assert created[0].kwargs["temperature"] == 0.7
    assert created[0].kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}
    assert created[0].kwargs.get("api_base") == "https://api.deepseek.com"
    assert [type(message) for message in created[0].invocations[0]] == [SystemMessage, AIMessage, HumanMessage]
    assert [message.content for message in created[0].invocations[0]] == [
        "system prompt",
        "previous answer",
        "question",
    ]


def test_openai_compatible_json_client_passes_base_url_and_json_mode() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": "ok"}', **kwargs)
        created.append(model)
        return model

    client = OpenAICompatibleJsonClient(
        OpenAICompatibleConfig(
            api_key="vivo-key",
            model="Doubao-Seed-2.0-pro",
            base_url="https://api-ai.vivo.com.cn/v1",
            timeout_sec=11,
        ),
        chat_factory=chat_factory,
    )

    result = client.complete_json(
        JsonChatRequest(
            provider="vivo",
            model="request-model-ignored",
            messages=[ChatMessage(role="user", content="question")],
            response_format={"type": "json_object"},
        )
    )

    assert result.parsed_json == {"answer": "ok"}
    assert created[0].kwargs["model"] == "Doubao-Seed-2.0-pro"
    assert created[0].kwargs["api_key"] == "vivo-key"
    assert created[0].kwargs["base_url"] == "https://api-ai.vivo.com.cn/v1"
    assert created[0].kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}


def test_image_to_data_url_rejects_non_image_mime() -> None:
    assert image_to_data_url(VisionImage(mime_type="image/png", data=b"png-bytes")).startswith(
        "data:image/png;base64,cG5nLWJ5dGVz"
    )

    with pytest.raises(AIConfigurationError, match="image MIME"):
        image_to_data_url(VisionImage(mime_type="application/pdf", data=b"%PDF"))


def test_openai_compatible_vision_client_sends_data_urls_without_paths() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"segments": []}', **kwargs)
        created.append(model)
        return model

    client = OpenAICompatibleVisionJsonClient(
        OpenAICompatibleConfig(
            api_key="vivo-key",
            model="Doubao-Seed-2.0-mini",
            base_url="https://api-ai.vivo.com.cn/v1",
        ),
        chat_factory=chat_factory,
    )

    result = client.complete_vision_json(
        VisionJsonRequest(
            provider="vivo",
            model="vision-model",
            prompt="Describe this image",
            images=[VisionImage(mime_type="image/png", data=b"png-bytes", source_name="/tmp/local.png")],
        )
    )

    assert result.parsed_json == {"segments": []}
    [message] = created[0].invocations[0]
    assert isinstance(message, HumanMessage)
    content = message.content
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "Describe this image"}
    image_url = content[1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert "/tmp/local.png" not in image_url


def test_registry_only_registers_deepseek_when_api_key_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_CHAT", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_VISION", raising=False)
    assert "deepseek" not in build_default_ai_service().json_clients

    monkeypatch.setenv("KNOWLINK_DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_TIMEOUT_SEC", "12")
    service = build_default_ai_service()

    assert "deepseek" in service.json_clients
