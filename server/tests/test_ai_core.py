from __future__ import annotations

import pytest

from server.ai.core import (
    AIConfigurationError,
    AIOutputParseError,
    AIProviderError,
    JsonChatRequest,
    parse_json_object,
    fallback_reason_for_error,
    message_content_to_text,
)


def test_fenced_json_can_be_parsed() -> None:
    assert parse_json_object('```json\n{"answer": 42}\n```') == {"answer": 42}


def test_plain_json_can_be_parsed() -> None:
    assert parse_json_object('{"answer": 42}') == {"answer": 42}


def test_json_surrounded_by_explanation_can_be_parsed() -> None:
    assert parse_json_object('Here is the result:\n{"answer": 42}\nThanks.') == {"answer": 42}


def test_missing_object_raises_parse_error() -> None:
    with pytest.raises(AIOutputParseError):
        parse_json_object("no json here")


def test_array_root_raises_parse_error() -> None:
    with pytest.raises(AIOutputParseError):
        parse_json_object("[1, 2, 3]")


def test_array_root_with_nested_object_raises_parse_error() -> None:
    with pytest.raises(AIOutputParseError):
        parse_json_object('[{"answer": 42}]')


def test_langchain_list_content_converts_to_text() -> None:
    content = [
        {"type": "text", "text": "first"},
        "second",
        {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}},
        {"text": "third"},
    ]

    assert message_content_to_text(content) == "first\nsecond\nthird"


def test_dataclass_default_dicts_are_isolated() -> None:
    first = JsonChatRequest(
        provider="deepseek",
        model="deepseek-chat",
        messages=[],
    )
    second = JsonChatRequest(
        provider="deepseek",
        model="deepseek-chat",
        messages=[],
    )

    first.metadata["request_id"] = "first"
    first.response_format["strict"] = True

    assert second.metadata == {}
    assert second.response_format == {"type": "json_object"}


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (AIConfigurationError("missing key"), "model_unconfigured"),
        (AIOutputParseError("bad json"), "model_output_invalid"),
        (AIProviderError("provider failed"), "model_provider_error"),
        (RuntimeError("other"), "model_unavailable"),
    ],
)
def test_fallback_reason_for_error_mapping(error: Exception, reason: str) -> None:
    assert fallback_reason_for_error(error) == reason
