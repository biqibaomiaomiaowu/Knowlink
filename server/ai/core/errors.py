from __future__ import annotations


class AIError(Exception):
    """Base exception for AI service failures."""


class AIConfigurationError(AIError):
    """Raised when an AI provider or model is not configured."""


class AIProviderError(AIError):
    """Raised when a provider call fails."""


class AIOutputParseError(AIError):
    """Raised when model output cannot be parsed into the expected shape."""


def fallback_reason_for_error(error: Exception) -> str:
    if isinstance(error, AIConfigurationError):
        return "model_unconfigured"
    if isinstance(error, AIOutputParseError):
        return "model_output_invalid"
    if isinstance(error, AIProviderError):
        return "model_provider_error"
    return "model_unavailable"
