from __future__ import annotations

from typing import Any, Sequence

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from server.ai.core import AIConfigurationError, ChatMessage, JsonChatRequest, VisionImage, VisionJsonRequest
from server.ai.providers import vivo
from server.ai.providers.deepseek_chat import (
    DeepSeekLangChainConfig,
    DeepSeekLangChainJsonClient,
    normalize_deepseek_base_url,
)
from server.ai.providers.deepseek_chat import _to_langchain_messages
from server.ai.providers.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleJsonClient
from server.ai.providers.openai_compatible import OpenAICompatibleVisionJsonClient
from server.ai.providers.registry import build_default_ai_service
from server.ai.providers.vivo import VivoLongAsrClient, VivoOcrClient
from server.ai.providers.vision_chat import image_to_data_url
from server.ai.service import AIService
from server.config import settings as settings_module


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
            model="config-model",
            base_url="https://api.deepseek.com",
            timeout_sec=9,
        ),
        chat_factory=chat_factory,
    )

    result = client.complete_json(
        JsonChatRequest(
            provider="deepseek",
            model="request-model",
            messages=[
                ChatMessage(role="system", content="system prompt"),
                ChatMessage(role="assistant", content="previous answer"),
                ChatMessage(role="user", content="question"),
            ],
            temperature=0.7,
            timeout_sec=13,
            response_format={"type": "json_object"},
            metadata={"max_tokens": 2048, "reasoning_effort": "high"},
        )
    )

    assert result.parsed_json == {"answer": 42}
    assert result.text == 'prefix {"answer": 42}'
    assert len(created) == 1
    assert created[0].kwargs["model"] == "request-model"
    assert created[0].kwargs["api_key"] == "deepseek-key"
    assert created[0].kwargs["timeout"] == 13
    assert created[0].kwargs["temperature"] == 0.7
    assert created[0].kwargs["max_tokens"] == 2048
    assert created[0].kwargs["reasoning_effort"] == "high"
    assert created[0].kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}
    assert created[0].kwargs.get("api_base") == "https://api.deepseek.com/v1"
    assert [type(message) for message in created[0].invocations[0]] == [SystemMessage, AIMessage, HumanMessage]
    assert [message.content for message in created[0].invocations[0]] == [
        "system prompt",
        "previous answer",
        "question",
    ]


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        (None, None),
        ("", None),
        ("https://api.deepseek.com", "https://api.deepseek.com/v1"),
        ("https://api.deepseek.com/", "https://api.deepseek.com/v1"),
        ("https://api.deepseek.com/v1", "https://api.deepseek.com/v1"),
        ("https://api.deepseek.com/v1/", "https://api.deepseek.com/v1"),
    ],
)
def test_normalize_deepseek_base_url(base_url: str | None, expected: str | None) -> None:
    assert normalize_deepseek_base_url(base_url) == expected


def test_deepseek_langchain_message_mapping_accepts_legacy_dict_messages() -> None:
    messages = _to_langchain_messages(
        [
            {"role": "system", "content": [{"text": "system hello"}]},
            {"role": "assistant", "content": [{"text": "assistant hello"}]},
            {"content": [{"text": "hello"}]},
        ]
    )

    assert [type(message) for message in messages] == [SystemMessage, AIMessage, HumanMessage]
    assert [message.content for message in messages] == ["system hello", "assistant hello", "hello"]


@pytest.mark.parametrize(
    ("metadata", "forbidden_kwargs"),
    [
        ({"max_tokens": 0, "reasoning_effort": "high"}, {"max_tokens"}),
        ({"max_tokens": -1, "reasoning_effort": "high"}, {"max_tokens"}),
        ({"max_tokens": True, "reasoning_effort": "high"}, {"max_tokens"}),
        ({"max_tokens": "2048", "reasoning_effort": "high"}, {"max_tokens"}),
        ({"max_tokens": 2048, "reasoning_effort": ""}, {"reasoning_effort"}),
        ({"max_tokens": 2048, "reasoning_effort": "unsupported"}, {"reasoning_effort"}),
        ({"max_tokens": 2048, "reasoning_effort": 1}, {"reasoning_effort"}),
    ],
)
def test_deepseek_langchain_client_omits_invalid_metadata_kwargs(
    metadata: dict[str, Any],
    forbidden_kwargs: set[str],
) -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": 42}', **kwargs)
        created.append(model)
        return model

    client = DeepSeekLangChainJsonClient(
        DeepSeekLangChainConfig(api_key="deepseek-key", model="config-model"),
        chat_factory=chat_factory,
    )

    client.complete_json(
        JsonChatRequest(
            provider="deepseek",
            model="request-model",
            messages=[ChatMessage(role="user", content="question")],
            metadata=metadata,
        )
    )

    assert forbidden_kwargs.isdisjoint(created[0].kwargs)


def test_deepseek_langchain_client_omits_model_kwargs_when_response_format_is_none() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": 42}', **kwargs)
        created.append(model)
        return model

    client = DeepSeekLangChainJsonClient(
        DeepSeekLangChainConfig(api_key="deepseek-key", model="config-model"),
        chat_factory=chat_factory,
    )

    client.complete_json(
        JsonChatRequest(
            provider="deepseek",
            model="",
            messages=[ChatMessage(role="user", content="question")],
            response_format=None,
        )
    )

    assert created[0].kwargs["model"] == "config-model"
    assert "model_kwargs" not in created[0].kwargs


def test_deepseek_langchain_client_retries_without_response_format_when_structured_output_is_unsupported() -> None:
    created: list[FakeChatModel] = []

    class UnsupportedStructuredOutputModel(FakeChatModel):
        def invoke(self, messages: Sequence[Any]) -> AIMessage:
            raise ValueError("response_format json_schema is not supported by this model")

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        if "model_kwargs" in kwargs:
            model = UnsupportedStructuredOutputModel(**kwargs)
        else:
            model = FakeChatModel('{"answer": 42}', **kwargs)
        created.append(model)
        return model

    client = DeepSeekLangChainJsonClient(
        DeepSeekLangChainConfig(api_key="deepseek-key", model="config-model"),
        chat_factory=chat_factory,
    )

    result = client.complete_json(
        JsonChatRequest(
            provider="deepseek",
            model="request-model",
            messages=[ChatMessage(role="user", content="question")],
            response_format={"type": "json_object"},
        )
    )

    assert result.parsed_json == {"answer": 42}
    assert len(created) == 2
    assert created[0].kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}
    assert "model_kwargs" not in created[1].kwargs


def test_openai_compatible_json_client_passes_request_model_base_url_and_json_mode() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": "ok"}', **kwargs)
        created.append(model)
        return model

    client = OpenAICompatibleJsonClient(
        OpenAICompatibleConfig(
            api_key="vivo-key",
            model="config-model",
            base_url="https://api-ai.vivo.com.cn/v1",
            timeout_sec=11,
        ),
        chat_factory=chat_factory,
    )

    result = client.complete_json(
        JsonChatRequest(
            provider="vivo",
            model="request-model",
            messages=[ChatMessage(role="user", content="question")],
            timeout_sec=17,
            response_format={"type": "json_object"},
        )
    )

    assert result.parsed_json == {"answer": "ok"}
    assert created[0].kwargs["model"] == "request-model"
    assert created[0].kwargs["api_key"] == "vivo-key"
    assert created[0].kwargs["base_url"] == "https://api-ai.vivo.com.cn/v1"
    assert created[0].kwargs["timeout"] == 17
    assert created[0].kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}


def test_openai_compatible_json_client_passes_valid_generation_metadata() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": "ok"}', **kwargs)
        created.append(model)
        return model

    client = OpenAICompatibleJsonClient(
        OpenAICompatibleConfig(
            api_key="vivo-key",
            model="config-model",
            base_url="https://api-ai.vivo.com.cn/v1",
        ),
        chat_factory=chat_factory,
    )

    client.complete_json(
        JsonChatRequest(
            provider="vivo",
            model="request-model",
            messages=[ChatMessage(role="user", content="question")],
            metadata={"max_tokens": 2048, "stream": False},
        )
    )

    assert created[0].kwargs["max_tokens"] == 2048
    assert created[0].kwargs["streaming"] is False


@pytest.mark.parametrize(
    "metadata",
    [
        {"max_tokens": 0, "stream": False},
        {"max_tokens": -1, "stream": False},
        {"max_tokens": True, "stream": False},
        {"max_tokens": "2048", "stream": False},
    ],
)
def test_openai_compatible_json_client_omits_invalid_max_tokens(metadata: dict[str, Any]) -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": "ok"}', **kwargs)
        created.append(model)
        return model

    client = OpenAICompatibleJsonClient(
        OpenAICompatibleConfig(
            api_key="vivo-key",
            model="config-model",
            base_url="https://api-ai.vivo.com.cn/v1",
        ),
        chat_factory=chat_factory,
    )

    client.complete_json(
        JsonChatRequest(
            provider="vivo",
            model="request-model",
            messages=[ChatMessage(role="user", content="question")],
            metadata=metadata,
        )
    )

    assert "max_tokens" not in created[0].kwargs
    assert created[0].kwargs["streaming"] is False


def test_openai_compatible_json_client_omits_model_kwargs_when_response_format_is_none() -> None:
    created: list[FakeChatModel] = []

    def chat_factory(**kwargs: Any) -> FakeChatModel:
        model = FakeChatModel('{"answer": "ok"}', **kwargs)
        created.append(model)
        return model

    client = OpenAICompatibleJsonClient(
        OpenAICompatibleConfig(
            api_key="vivo-key",
            model="config-model",
            base_url="https://api-ai.vivo.com.cn/v1",
        ),
        chat_factory=chat_factory,
    )

    client.complete_json(
        JsonChatRequest(
            provider="vivo",
            model="",
            messages=[ChatMessage(role="user", content="question")],
            response_format=None,
        )
    )

    assert created[0].kwargs["model"] == "config-model"
    assert "model_kwargs" not in created[0].kwargs


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
            model="config-model",
            base_url="https://api-ai.vivo.com.cn/v1",
            timeout_sec=19,
        ),
        chat_factory=chat_factory,
    )

    result = client.complete_vision_json(
        VisionJsonRequest(
            provider="vivo",
            model="request-vision-model",
            prompt="Describe this image",
            images=[VisionImage(mime_type="image/png", data=b"png-bytes", source_name="/tmp/local.png")],
            timeout_sec=23,
            metadata={"max_tokens": 2048, "stream": False, "request_id": "vision-request-id"},
        )
    )

    assert result.parsed_json == {"segments": []}
    assert created[0].kwargs["model"] == "request-vision-model"
    assert created[0].kwargs["timeout"] == 23
    assert created[0].kwargs["max_tokens"] == 2048
    assert created[0].kwargs["streaming"] is False
    assert created[0].kwargs["default_query"] == {"request_id": "vision-request-id"}
    assert created[0].kwargs["model_kwargs"]["response_format"] == {"type": "json_object"}
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
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_CHAT", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_VISION", raising=False)
    assert "deepseek" not in build_default_ai_service().json_clients

    monkeypatch.setenv("KNOWLINK_DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_TIMEOUT_SEC", "12")
    service = build_default_ai_service()

    assert "deepseek" in service.json_clients
    client = service.json_clients["deepseek"]
    assert isinstance(client, DeepSeekLangChainJsonClient)
    assert client._config.base_url == "https://api.deepseek.com/v1"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.deepseek.com",
        "https://api.deepseek.com/",
        "https://api.deepseek.com/v1",
        "https://api.deepseek.com/v1/",
    ],
)
def test_deepseek_scoped_helpers_normalize_base_url(base_url: str) -> None:
    from server.ai import handout_block, handout_lazy, qa_policy, quiz_strategy

    for module in (handout_block, handout_lazy, qa_policy, quiz_strategy):
        assert module._deepseek_base_url(base_url) == "https://api.deepseek.com/v1"


def test_registry_loads_root_dotenv_before_reading_provider_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KNOWLINK_DEEPSEEK_API_KEY=deepseek-from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DOTENV_PATH", dotenv_path)
    monkeypatch.delenv("KNOWLINK_DISABLE_DOTENV", raising=False)
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_CHAT", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_VISION", raising=False)

    service = build_default_ai_service()

    assert "deepseek" in service.json_clients


def test_registry_leaves_vivo_asr_and_ocr_unconfigured_without_enable_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_ASR", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_OCR", raising=False)
    monkeypatch.setenv("KNOWLINK_VIVO_APP_ID", "2026764332")
    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "vivo-key")

    service = build_default_ai_service()

    assert service.asr_client is None
    assert service.ocr_client is None


def test_registry_configures_vivo_asr_and_ocr_clients_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNOWLINK_ENABLE_VIVO_ASR", "true")
    monkeypatch.setenv("KNOWLINK_ENABLE_VIVO_OCR", "true")
    monkeypatch.setenv("KNOWLINK_VIVO_APP_ID", "2026764332")
    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "vivo-key")
    monkeypatch.delenv("KNOWLINK_VIVO_OCR_BUSINESS_ID", raising=False)

    service = build_default_ai_service()

    assert isinstance(service.asr_client, VivoLongAsrClient)
    assert isinstance(service.ocr_client, VivoOcrClient)
    assert service.ocr_client._business_id == "aigc2026764332"


def test_vivo_provider_facade_exports_custom_asr_and_ocr_clients() -> None:
    assert set(vivo.__all__) == {
        "AsrClient",
        "VivoLongAsrClient",
        "get_configured_asr_client",
        "OcrClient",
        "VivoOcrClient",
        "get_configured_ocr_client",
    }


def test_registry_does_not_override_deepseek_base_url_when_env_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNOWLINK_DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_CHAT", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_VISION", raising=False)

    client = build_default_ai_service().json_clients["deepseek"]

    assert isinstance(client, DeepSeekLangChainJsonClient)
    assert client._config.base_url is None


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api-ai.vivo.com.cn",
        "https://api-ai.vivo.com.cn/",
        "https://api-ai.vivo.com.cn/v1",
        "https://api-ai.vivo.com.cn/v1/",
    ],
)
def test_registry_normalizes_vivo_chat_base_url(monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("KNOWLINK_ENABLE_VIVO_CHAT", "1")
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_VISION", raising=False)
    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "vivo-key")
    monkeypatch.setenv("KNOWLINK_VIVO_BASE_URL", base_url)

    client = build_default_ai_service().json_clients["vivo"]

    assert isinstance(client, OpenAICompatibleJsonClient)
    assert client._config.base_url == "https://api-ai.vivo.com.cn/v1"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api-ai.vivo.com.cn",
        "https://api-ai.vivo.com.cn/",
        "https://api-ai.vivo.com.cn/v1",
        "https://api-ai.vivo.com.cn/v1/",
    ],
)
def test_registry_normalizes_vivo_vision_base_url(monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    monkeypatch.delenv("KNOWLINK_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_CHAT", raising=False)
    monkeypatch.setenv("KNOWLINK_ENABLE_VIVO_VISION", "1")
    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "vivo-key")
    monkeypatch.setenv("KNOWLINK_VIVO_BASE_URL", base_url)

    client = build_default_ai_service().vision_clients["vivo"]

    assert isinstance(client, OpenAICompatibleVisionJsonClient)
    assert client._config.base_url == "https://api-ai.vivo.com.cn/v1"
