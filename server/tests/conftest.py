from __future__ import annotations

import os

import pytest

from server.config import settings as settings_module


_AI_PROVIDER_ENV_PREFIXES = (
    "KNOWLINK_DEEPSEEK_",
    "KNOWLINK_ENABLE_VIVO_",
    "KNOWLINK_VIVO_",
    "KNOWLINK_HANDOUT_",
    "KNOWLINK_QA_",
    "KNOWLINK_QUIZ_",
)


def _clear_ai_provider_env() -> None:
    for name in list(os.environ):
        if name.startswith(_AI_PROVIDER_ENV_PREFIXES):
            os.environ.pop(name, None)


os.environ.setdefault("KNOWLINK_DISABLE_DOTENV", "1")
_clear_ai_provider_env()


@pytest.fixture(autouse=True)
def isolate_root_dotenv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KNOWLINK_DISABLE_DOTENV", "1")
    _clear_ai_provider_env()
    settings_module.get_settings.cache_clear()
    yield
    _clear_ai_provider_env()
    settings_module.get_settings.cache_clear()
