# AI 服务层 LangChain 统一底座实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `server/ai` 服务层，统一 DeepSeek、vivo 文本、vivo Vision、OCR、ASR 的调用入口；引入当前 PyPI 主版本 LangChain 依赖；默认从项目根目录 `.env` 读取配置；为 V2 的 graph、grading、streaming、资料解析增强、视频抽帧解析留下稳定结构，但本轮不实现 V2 业务能力。

**Architecture:** 新增 `server/ai/core` 作为稳定请求和错误类型层，新增 `server/ai/providers` 作为 LangChain 与自定义 vivo 协议适配层，新增 `server/ai/service.py` 作为业务侧 facade。现有 `handout_*`、`qa_policy`、`quiz_strategy`、`vision` 保留公开类名和工厂函数，内部迁移到统一 facade。`VivoLongAsrClient` 和 `VivoOcrClient` 纳入统一底座注册，但继续保持自定义 REST 适配，不包装成 LangChain provider。

**Tech Stack:** Python 3.12、FastAPI、pytest、LangChain 1.x、`langchain-deepseek`、`langchain-openai`、`python-dotenv`。

---

## 版本依据

- 2026-05-15 通过 PyPI 核对当前版本：`langchain==1.3.1`、`langchain-core==1.4.0`、`langchain-openai==1.2.1`、`langchain-deepseek==1.0.1`、`python-dotenv==1.2.2`。
- 依赖范围使用同一主版本内的下限约束：`langchain>=1.3.1,<2.0`、`langchain-core>=1.4,<2.0`、`langchain-openai>=1.2,<2.0`、`langchain-deepseek>=1.0,<2.0`、`openai>=2.26,<3.0`、`python-dotenv>=1.2,<2.0`。
- `langchain-openai==1.2.1` 要求 `openai>=2.26,<3.0`，所以本轮保留 OpenAI SDK 依赖但升级到 2.x；仓库当前没有直接 `openai` SDK 调用，兼容风险由 LangChain provider 适配层测试覆盖。
- PyPI 页面：`https://pypi.org/project/langchain/`、`https://pypi.org/project/langchain-core/`、`https://pypi.org/project/langchain-openai/`、`https://pypi.org/project/langchain-deepseek/`、`https://pypi.org/project/python-dotenv/`。

## 子 Agent 执行规则

- 主 agent 只做编排、集成和最终验证；每个实施任务交给一个 fresh worker subagent。
- 每个任务执行顺序固定为：implementer subagent 完成实现与测试，自审后返回；spec reviewer subagent 检查该任务是否满足本计划和已批准 spec；code quality reviewer subagent 检查代码质量和回归风险。
- 任一 reviewer 提出必须修复的问题时，回到同一个 implementer subagent 修复，再重新走对应 reviewer。
- 不并行派发多个实现 subagent，因为任务会连续修改 `server/ai` 共享边界；调查类 subagent 可以并行，已完成的 ASR/OCR 调查结论写入本计划。
- 不关闭未完成的 subagent。主 agent 只在 subagent 返回 completed 状态后继续下一步。
- 由于当前 Codex 子 agent 在独立工作区产出变更，主 agent 在质量门通过后负责整合变更，并按本计划给出的提交标题提交。
- 所有依赖安装和测试命令必须使用仓库虚拟环境 `.venv`，禁止全局 `pip install`。若 `.venv/bin/python` 不存在，先用 `python3 -m venv .venv` 创建；后续统一调用 `.venv/bin/python -m pip` 和 `.venv/bin/python -m pytest`。

## File Structure

```text
pyproject.toml
server/config/settings.py
server/ai/core/__init__.py
server/ai/core/types.py
server/ai/core/errors.py
server/ai/core/json_output.py
server/ai/providers/__init__.py
server/ai/providers/deepseek_chat.py
server/ai/providers/openai_compatible.py
server/ai/providers/vision_chat.py
server/ai/providers/registry.py
server/ai/providers/vivo/__init__.py
server/ai/service.py
server/ai/deepseek.py
server/ai/handout_lazy.py
server/ai/handout_block.py
server/ai/qa_policy.py
server/ai/quiz_strategy.py
server/ai/vision.py
server/ai/v2/__init__.py
server/ai/v2/graph.py
server/ai/v2/grading.py
server/ai/v2/streaming.py
server/ai/v2/parsing.py
server/ai/v2/video_frames.py
server/tests/test_runtime_wiring_contract.py
server/tests/test_ai_core.py
server/tests/test_ai_service.py
server/tests/test_ai_v2_contracts.py
server/tests/test_quiz_strategy.py
server/tests/test_handout_lazy.py
server/tests/test_handout_block.py
server/tests/test_qa_policy.py
server/tests/test_parsers.py
```

## Task 1: 依赖与 `.env` 默认加载

**Goal:** 安装 LangChain 相关依赖，确保 `get_settings()` 读取环境变量前自动加载项目根目录 `.env`，且真实系统环境变量优先。

**Implementer subagent ownership:** `pyproject.toml`、`server/config/settings.py`、`server/tests/test_runtime_wiring_contract.py`。

- [ ] 修改 `pyproject.toml` 的 `dependencies`，保留已有 `openai`，加入或更新以下条目：

```toml
  "langchain>=1.3.1,<2.0",
  "langchain-core>=1.4,<2.0",
  "langchain-openai>=1.2,<2.0",
  "langchain-deepseek>=1.0,<2.0",
  "openai>=2.26,<3.0",
  "python-dotenv>=1.2,<2.0",
```

- [ ] 在仓库虚拟环境中安装依赖，禁止使用全局 pip：

```bash
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -c "import langchain, langchain_core, langchain_openai, langchain_deepseek, dotenv"
```

Expected: command exits 0，依赖只安装到 `.venv`，导入检查通过。

- [ ] 修改 `server/config/settings.py`，在读取 `os.getenv` 前加载根目录 `.env`，`override=False`：

```python
from dotenv import load_dotenv

_ROOT_DIR = Path(__file__).resolve().parents[2]
_DOTENV_PATH = _ROOT_DIR / ".env"


def _load_root_dotenv() -> None:
    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)


@lru_cache
def get_settings() -> Settings:
    _load_root_dotenv()
    base_dir = Path(__file__).resolve().parents[1]
    settings = Settings(
        app_name=os.getenv("KNOWLINK_APP_NAME", "KnowLink API"),
        env=os.getenv("KNOWLINK_ENV", "development"),
        host=os.getenv("KNOWLINK_HOST", "0.0.0.0"),
        port=int(os.getenv("KNOWLINK_PORT", "8000")),
        demo_token=os.getenv("KNOWLINK_DEMO_TOKEN", "knowlink-demo-token"),
        demo_user_id=int(os.getenv("KNOWLINK_DEMO_USER_ID", "1")),
        demo_user_name=os.getenv("KNOWLINK_DEMO_USER_NAME", "KnowLink Demo"),
        database_url=os.getenv(
            "KNOWLINK_DATABASE_URL",
            "postgresql://knowlink:knowlink@localhost:5432/knowlink",
        ),
        redis_url=os.getenv("KNOWLINK_REDIS_URL", "redis://localhost:6379/0"),
        storage_backend=os.getenv("KNOWLINK_STORAGE_BACKEND", "demo"),
        minio_endpoint=os.getenv("KNOWLINK_MINIO_ENDPOINT", "localhost:9000"),
        minio_internal_endpoint=os.getenv(
            "KNOWLINK_MINIO_INTERNAL_ENDPOINT",
            os.getenv("KNOWLINK_MINIO_ENDPOINT", "localhost:9000"),
        ),
        minio_public_endpoint=os.getenv(
            "KNOWLINK_MINIO_PUBLIC_ENDPOINT",
            os.getenv("KNOWLINK_MINIO_ENDPOINT", "localhost:9000"),
        ),
        minio_access_key=os.getenv("KNOWLINK_MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("KNOWLINK_MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.getenv("KNOWLINK_MINIO_BUCKET", "knowlink"),
        minio_secure=_env_bool("KNOWLINK_MINIO_SECURE", False),
        cors_allow_origins=_env_csv(
            "KNOWLINK_CORS_ALLOW_ORIGINS",
            ("http://localhost:*", "http://127.0.0.1:*"),
        ),
        course_catalog_path=base_dir / "seeds" / "course_catalog.json",
        runtime_repository_backend=os.getenv("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "memory"),
        task_queue=os.getenv("KNOWLINK_TASK_QUEUE", "dramatiq"),
        scheduler_enabled=_env_bool("KNOWLINK_SCHEDULER_ENABLED", False),
    )
    _validate_task_queue(settings)
    _validate_runtime_hardening(settings)
    return settings
```

- [ ] 在 `server/tests/test_runtime_wiring_contract.py` 添加 `.env` 加载测试，避免污染全局缓存：

```python
def test_settings_loads_root_dotenv_before_reading_environment(monkeypatch, tmp_path):
    from server.config import settings as settings_module

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KNOWLINK_HOST=127.0.0.9\nKNOWLINK_TASK_QUEUE=noop\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DOTENV_PATH", dotenv_path)
    monkeypatch.delenv("KNOWLINK_HOST", raising=False)
    monkeypatch.delenv("KNOWLINK_TASK_QUEUE", raising=False)
    settings_module.get_settings.cache_clear()

    try:
        settings = settings_module.get_settings()
    finally:
        settings_module.get_settings.cache_clear()

    assert settings.host == "127.0.0.9"
    assert settings.task_queue == "noop"


def test_settings_keeps_real_environment_above_dotenv(monkeypatch, tmp_path):
    from server.config import settings as settings_module

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("KNOWLINK_HOST=127.0.0.9\nKNOWLINK_TASK_QUEUE=noop\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_DOTENV_PATH", dotenv_path)
    monkeypatch.setenv("KNOWLINK_HOST", "10.0.0.5")
    monkeypatch.setenv("KNOWLINK_TASK_QUEUE", "dramatiq")
    settings_module.get_settings.cache_clear()

    try:
        settings = settings_module.get_settings()
    finally:
        settings_module.get_settings.cache_clear()

    assert settings.host == "10.0.0.5"
    assert settings.task_queue == "dramatiq"
```

- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_runtime_wiring_contract.py -q
```

Expected: command exits 0, all tests in `test_runtime_wiring_contract.py` pass.

**Commit:** `chore(repo): 引入 LangChain 依赖并加载根目录环境配置`

## Task 2: 核心 AI 请求类型、错误类型与 JSON 输出工具

**Goal:** 抽出业务侧稳定契约，LangChain 细节只存在于 provider 目录内。

**Implementer subagent ownership:** `server/ai/core/**`、`server/tests/test_ai_core.py`。

- [ ] 新增 `server/ai/core/types.py`：

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ChatRole = Literal["system", "user", "assistant"]
AIProviderName = Literal["deepseek", "vivo", "custom"]


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class JsonChatRequest:
    provider: AIProviderName
    model: str
    messages: Sequence[ChatMessage]
    temperature: float = 0.2
    timeout_sec: float = 30.0
    response_format: dict[str, Any] | None = field(default_factory=lambda: {"type": "json_object"})
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisionImage:
    mime_type: str
    data: bytes
    source_name: str | None = None


@dataclass(frozen=True)
class VisionJsonRequest:
    provider: AIProviderName
    model: str
    prompt: str
    images: Sequence[VisionImage]
    temperature: float = 0.1
    timeout_sec: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIModelResult:
    text: str
    parsed_json: dict[str, Any] | None = None
    raw: Any = None
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass(frozen=True)
class StreamChatRequest:
    provider: AIProviderName
    model: str
    messages: Sequence[ChatMessage]
    temperature: float = 0.2
    timeout_sec: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIStreamEvent:
    kind: Literal["token", "message", "error", "done"]
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


LocalImagePath = str | Path
```

- [ ] 新增 `server/ai/core/errors.py`：

```python
from __future__ import annotations


class AIError(RuntimeError):
    """Base class for AI service errors."""


class AIConfigurationError(AIError):
    """Raised when an AI provider is not configured."""


class AIProviderError(AIError):
    """Raised when a provider call fails."""


class AIOutputParseError(AIError):
    """Raised when model output cannot be parsed as the requested shape."""


def fallback_reason_for_error(error: BaseException) -> str:
    if isinstance(error, AIConfigurationError):
        return "model_unconfigured"
    if isinstance(error, AIOutputParseError):
        return "model_output_invalid"
    if isinstance(error, AIProviderError):
        return "model_provider_error"
    return "model_unavailable"
```

- [ ] 新增 `server/ai/core/json_output.py`，从 `server/ai/deepseek.py` 迁移并复用 JSON 提取逻辑：

```python
from __future__ import annotations

import json
from typing import Any

from server.ai.core.errors import AIOutputParseError


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIOutputParseError("AI response did not contain a JSON object.")
    return stripped[start : end + 1]


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(extract_json_object(text))
    except json.JSONDecodeError as exc:
        raise AIOutputParseError(f"AI response JSON is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise AIOutputParseError("AI response JSON root must be an object.")
    return value
```

- [ ] 新增 `server/ai/core/__init__.py` 导出公开类型和错误。
- [ ] 新增 `server/tests/test_ai_core.py` 覆盖 fenced JSON、纯 JSON、缺少对象、数组根节点、LangChain list content 转文本。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_ai_core.py -q
```

Expected: command exits 0, all core tests pass.

**Commit:** `feat(ai): 新增统一 AI 核心契约`

## Task 3: LangChain provider 适配器与统一 service facade

**Goal:** 建立 `AIService`，让业务代码只依赖统一 facade，不直接依赖 provider SDK。

**Implementer subagent ownership:** `server/ai/providers/**`、`server/ai/service.py`、`server/tests/test_ai_service.py`。

- [ ] 新增 `server/ai/providers/deepseek_chat.py`，必须使用官方 `langchain_deepseek.ChatDeepSeek`：

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek

from server.ai.core.errors import AIProviderError
from server.ai.core.json_output import message_content_to_text, parse_json_object
from server.ai.core.types import AIModelResult, ChatMessage, JsonChatRequest


class ChatFactory(Protocol):
    def __call__(self, **kwargs: Any) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class DeepSeekLangChainConfig:
    api_key: str
    model: str
    base_url: str | None = None
    timeout_sec: float = 30.0


def _to_langchain_messages(messages: Sequence[ChatMessage]) -> list[Any]:
    converted: list[Any] = []
    for message in messages:
        if message.role == "system":
            converted.append(SystemMessage(content=message.content))
        elif message.role == "assistant":
            converted.append(AIMessage(content=message.content))
        else:
            converted.append(HumanMessage(content=message.content))
    return converted


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
        if self._config.base_url:
            kwargs["api_base"] = self._config.base_url
        if request.response_format:
            kwargs["model_kwargs"] = {"response_format": request.response_format}
        chat = self._chat_factory(**kwargs)
        try:
            response = chat.invoke(_to_langchain_messages(request.messages))
        except Exception as exc:
            raise AIProviderError(f"DeepSeek LangChain request failed: {exc}") from exc
        text = message_content_to_text(getattr(response, "content", response))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=response)
```

- [ ] 新增 `server/ai/providers/openai_compatible.py`，用于 vivo 文本类和 vision 类 OpenAI-compatible endpoint，使用 `langchain_openai.ChatOpenAI`，保留 base URL、API key、模型、timeout、temperature 注入能力：

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from server.ai.core.errors import AIProviderError
from server.ai.core.json_output import message_content_to_text, parse_json_object
from server.ai.core.types import AIModelResult, JsonChatRequest, VisionJsonRequest
from server.ai.providers.deepseek_chat import _to_langchain_messages
from server.ai.providers.vision_chat import build_vision_content


class OpenAIChatFactory(Protocol):
    def __call__(self, **kwargs: Any) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    api_key: str
    model: str
    base_url: str
    timeout_sec: float = 30.0


class OpenAICompatibleJsonClient:
    def __init__(self, config: OpenAICompatibleConfig, *, chat_factory: OpenAIChatFactory = ChatOpenAI) -> None:
        self._config = config
        self._chat_factory = chat_factory

    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        chat = self._chat_factory(
            model=request.model or self._config.model,
            api_key=self._config.api_key,
            base_url=self._config.base_url,
            temperature=request.temperature,
            timeout=request.timeout_sec or self._config.timeout_sec,
            model_kwargs={"response_format": request.response_format} if request.response_format else None,
        )
        try:
            response = chat.invoke(_to_langchain_messages(request.messages))
        except Exception as exc:
            raise AIProviderError(f"OpenAI-compatible request failed: {exc}") from exc
        text = message_content_to_text(getattr(response, "content", response))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=response)


class OpenAICompatibleVisionJsonClient:
    def __init__(self, config: OpenAICompatibleConfig, *, chat_factory: OpenAIChatFactory = ChatOpenAI) -> None:
        self._config = config
        self._chat_factory = chat_factory

    def complete_vision_json(self, request: VisionJsonRequest) -> AIModelResult:
        chat = self._chat_factory(
            model=request.model or self._config.model,
            api_key=self._config.api_key,
            base_url=self._config.base_url,
            temperature=request.temperature,
            timeout=request.timeout_sec or self._config.timeout_sec,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        try:
            response = chat.invoke([HumanMessage(content=build_vision_content(request.prompt, request.images))])
        except Exception as exc:
            raise AIProviderError(f"OpenAI-compatible vision request failed: {exc}") from exc
        text = message_content_to_text(getattr(response, "content", response))
        return AIModelResult(text=text, parsed_json=parse_json_object(text), raw=response)
```

- [ ] 新增 `server/ai/providers/vision_chat.py`，用于 vision 请求，把 bytes 编码为 data URL，再构造 LangChain multimodal content：

```python
from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

from server.ai.core.errors import AIConfigurationError
from server.ai.core.types import VisionImage


def image_to_data_url(image: VisionImage) -> str:
    if not image.mime_type.startswith("image/"):
        raise AIConfigurationError(f"Unsupported image MIME type: {image.mime_type}")
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded}"


def build_vision_content(prompt: str, images: Sequence[VisionImage]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image in images:
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(image)}})
    return content
```

- [ ] 新增 `server/ai/service.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from server.ai.asr import AsrClient
from server.ai.core.errors import AIConfigurationError
from server.ai.core.types import AIModelResult, JsonChatRequest, VisionJsonRequest
from server.ai.ocr import OcrClient


class JsonChatClient(Protocol):
    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        raise NotImplementedError


class VisionJsonClient(Protocol):
    def complete_vision_json(self, request: VisionJsonRequest) -> AIModelResult:
        raise NotImplementedError


@dataclass(frozen=True)
class AIService:
    json_clients: dict[str, JsonChatClient]
    vision_clients: dict[str, VisionJsonClient]
    asr_client: AsrClient | None = None
    ocr_client: OcrClient | None = None

    def complete_json(self, request: JsonChatRequest) -> AIModelResult:
        client = self.json_clients.get(request.provider)
        if client is None:
            raise AIConfigurationError(f"AI provider is not configured: {request.provider}")
        return client.complete_json(request)

    def complete_vision_json(self, request: VisionJsonRequest) -> AIModelResult:
        client = self.vision_clients.get(request.provider)
        if client is None:
            raise AIConfigurationError(f"Vision provider is not configured: {request.provider}")
        return client.complete_vision_json(request)


@lru_cache
def get_default_ai_service() -> AIService:
    from server.ai.providers.registry import build_default_ai_service

    return build_default_ai_service()
```

- [ ] 新增 `server/ai/providers/registry.py`，从现有环境变量构建 provider，DeepSeek 缺 key 时不注册 DeepSeek client，vivo 缺 key 时不注册 vivo client。OCR/ASR 使用现有 `get_configured_ocr_client()` 和 `get_configured_asr_client()`。
- [ ] 在 `server/tests/test_ai_service.py` 使用 fake chat factory 测试：DeepSeek provider 调用 `ChatDeepSeek`、`response_format={"type": "json_object"}` 传入 `model_kwargs`、返回 JSON 被解析、provider 未配置时报 `AIConfigurationError`。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_ai_service.py server/tests/test_ai_core.py -q
```

Expected: command exits 0, service and core tests pass.

**Commit:** `feat(ai): 增加 LangChain 统一调用服务`

## Task 4: DeepSeek JSON 兼容层迁移

**Goal:** 让 `server/ai/deepseek.py` 继续提供现有公开 API，但内部走 `DeepSeekLangChainJsonClient`，减少业务文件一次性改动风险。

**Implementer subagent ownership:** `server/ai/deepseek.py`、现有 DeepSeek 相关测试。

- [ ] 保留 `DeepSeekChatConfig`、`DeepSeekJsonChatClient`、`get_configured_deepseek_chat_config()`、`complete_json()`、`parse_chat_json_payload()` 公开名字。
- [ ] `DeepSeekJsonChatClient.complete_json()` 内部构造 `JsonChatRequest(provider="deepseek", model=config.model, messages=converted_messages, temperature=temperature, timeout_sec=config.timeout_sec)`，调用 `DeepSeekLangChainJsonClient`。
- [ ] `parse_chat_json_payload()` 改为调用 `server.ai.core.json_output.parse_json_object()`。
- [ ] 兼容旧 message 字典输入，转换规则为：缺少 `role` 默认 `user`，`content` 先经 `message_content_to_text()` 归一化。
- [ ] 更新现有 DeepSeek 测试，不再断言 `urllib.request.urlopen`，改为 fake LangChain chat factory 断言 messages、model、api_key、timeout、response_format。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_quiz_strategy.py server/tests/test_handout_lazy.py server/tests/test_handout_block.py server/tests/test_qa_policy.py -q
```

Expected: command exits 0, DeepSeek 兼容层没有打断现有业务测试。

**Commit:** `refactor(ai): 将 DeepSeek JSON 调用迁移到 LangChain`

## Task 5: 迁移 quiz、handout、QA 文本生成入口

**Goal:** 业务生成客户端通过 `AIService.complete_json()` 调用模型，保留已有 fallback metadata 和公开工厂函数。

**Implementer subagent ownership:** `server/ai/quiz_strategy.py`、`server/ai/handout_lazy.py`、`server/ai/handout_block.py`、`server/ai/qa_policy.py`、对应测试文件。

- [ ] 在四个业务文件中统一构造 `JsonChatRequest`，系统提示和用户提示保持现有内容，不改业务 prompt 语义。
- [ ] 保留现有类名：`DeepSeekQuizGenerationClient`、`VivoHandoutOutlineClient`、`DeepSeekHandoutOutlineClient`、`VivoHandoutBlockClient`、`DeepSeekHandoutBlockClient`、`VivoQaAnswerClient`、`DeepSeekQaAnswerClient`。
- [ ] 每个类允许注入 `AIService` 或 `JsonChatClient` 以便测试，默认使用 `get_default_ai_service()`。
- [ ] provider 选择规则：DeepSeek 类使用 `provider="deepseek"`；vivo 文本类使用 `provider="vivo"`；模型名仍来自现有环境变量和默认值。
- [ ] 错误处理统一映射为 fallback metadata：`AIConfigurationError -> model_unconfigured`、`AIOutputParseError -> model_output_invalid`、`AIProviderError -> model_provider_error`、其他异常 `model_unavailable`。
- [ ] 修改测试，使用 fake `AIService` 返回 `AIModelResult(parsed_json={"ok": True})`，保留 fallback 场景断言。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_quiz_strategy.py server/tests/test_handout_lazy.py server/tests/test_handout_block.py server/tests/test_qa_policy.py -q
```

Expected: command exits 0,四类文本生成测试全部通过。

**Commit:** `refactor(ai): 统一文本生成客户端调用底座`

## Task 6: 第一轮迁移 vivo Vision

**Goal:** 将 `VivoVisionClient` 纳入统一 AI 底座，确保本地图片不会作为裸本地路径传入 `image_url`，统一转为 base64 data URL。

**Implementer subagent ownership:** `server/ai/vision.py`、`server/ai/providers/vision_chat.py`、`server/tests/test_parsers.py` 中 vision 相关测试。

- [ ] `VisualAsset` 到 `VisionImage` 的转换必须使用原始 bytes 和 MIME type。
- [ ] `VivoVisionClient.analyze_images()` 保留现有签名和错误类型，内部通过 `AIService.complete_vision_json(VisionJsonRequest(provider="vivo", model=model, prompt=prompt, images=images))`。
- [ ] `server/ai/providers/vision_chat.py` 禁止接受本地文件路径作为 `image_url.url`。构造 content 时只允许 `data:image/png;base64,abc123` 这类 data URL 或显式远程 `http` URL；本轮业务只传 data URL。
- [ ] 更新 tests：断言 fake provider 收到的图片内容是 data URL，且不包含本地路径；保留 `VisionModelUnsupportedError` 与 fallback 行为。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_parsers.py -q
```

Expected: command exits 0，PDF、PPTX、DOCX、视频解析相关回归测试通过。

**Commit:** `refactor(ai): 将 vivo Vision 接入统一调用底座`

## Task 7: OCR 与 ASR 纳入统一底座但保持自定义适配

**Goal:** 统一 facade 能获取 OCR/ASR 客户端，同时不破坏 vivo OCR/Long ASR 的专有协议实现。

**Implementer subagent ownership:** `server/ai/providers/vivo/__init__.py`、`server/ai/providers/registry.py`、`server/ai/service.py`、`server/tests/test_ai_service.py`、`server/tests/test_parsers.py`。

- [ ] 新增 `server/ai/providers/vivo/__init__.py`，显式导出既有自定义客户端：

```python
from server.ai.asr import AsrClient, VivoLongAsrClient, get_configured_asr_client
from server.ai.ocr import OcrClient, VivoOcrClient, get_configured_ocr_client

__all__ = [
    "AsrClient",
    "VivoLongAsrClient",
    "get_configured_asr_client",
    "OcrClient",
    "VivoOcrClient",
    "get_configured_ocr_client",
]
```

- [ ] `registry.build_default_ai_service()` 把 `get_configured_asr_client()` 和 `get_configured_ocr_client()` 的返回值填入 `AIService(asr_client=asr_client, ocr_client=ocr_client)`。
- [ ] 不修改 `VivoLongAsrClient` 的五阶段协议：create、upload slices、run、progress poll、result。
- [ ] 不修改 `VivoOcrClient` 的 form-urlencoded 协议：`image` base64、`pos=2`、`businessid`、Bearer auth。
- [ ] 添加 service-level 测试：未启用 env 时 ASR/OCR 为 `None`；启用必要 env 时返回现有客户端类型。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_ai_service.py server/tests/test_parsers.py -q
```

Expected: command exits 0，service facade 与既有解析测试通过。

**Commit:** `refactor(ai): 将 vivo OCR 和 ASR 纳入统一底座`

## Task 8: V2 保留结构

**Goal:** 预留 V2 graph、grading、streaming、资料解析增强、视频抽帧解析结构，不接入现有业务流。

**Implementer subagent ownership:** `server/ai/v2/**`、`server/tests/test_ai_v2_contracts.py`。

- [ ] 新增 `server/ai/v2/graph.py`：

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIGraphNode:
    key: str
    kind: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AIGraphEdge:
    source_key: str
    target_key: str
    relation: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AIGraphDraft:
    nodes: Sequence[AIGraphNode]
    edges: Sequence[AIGraphEdge]
```

- [ ] 新增 `server/ai/v2/grading.py`：

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AIGradingCriterion:
    key: str
    label: str
    max_score: float


@dataclass(frozen=True)
class AIGradingRequest:
    answer_text: str
    criteria: Sequence[AIGradingCriterion]
    metadata: dict[str, object] = field(default_factory=dict)
```

- [ ] 新增 `server/ai/v2/streaming.py`，只定义 `StreamEventSink` Protocol 和 `AIStreamEnvelope` dataclass，不接 SSE。
- [ ] 新增 `server/ai/v2/parsing.py`，定义 `ParsingEnhancementRequest`、`ParsingEnhancementResult`，用于后续资料解析增强。
- [ ] 新增 `server/ai/v2/video_frames.py`，定义 `VideoFrameExtractionRequest`、`VideoFrameExtractionResult`、`VideoFrameCandidate`，用于后续视频抽帧解析。
- [ ] 新增 `server/ai/v2/__init__.py` 导出这些类型。
- [ ] 新增 `server/tests/test_ai_v2_contracts.py`，只做 dataclass 构造、不可变性、导入契约测试。
- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests/test_ai_v2_contracts.py -q
```

Expected: command exits 0，V2 契约测试通过。

**Commit:** `feat(ai): 预留 V2 AI 能力契约`

## Task 9: 全量回归与最终审查

**Goal:** 验证重构没有破坏后端测试、依赖解析和提交规范。

**Implementer subagent ownership:** no file ownership unless a reviewer finds a concrete issue.

- [ ] Run:

```bash
.venv/bin/python -m pytest server/tests -q
```

Expected: command exits 0，后端测试通过。

- [ ] Run:

```bash
git diff --check
```

Expected: command exits 0，没有空白错误。

- [ ] Run:

```bash
git status --short
```

Expected: only intentional implementation files are modified before final commit.

- [ ] 派发 final code reviewer subagent，范围为本计划所有任务和已批准 spec，要求输出 findings first，并明确是否有阻塞问题。
- [ ] 如果 final reviewer 无阻塞问题，使用 `superpowers:verification-before-completion` 记录验证命令和结果。
- [ ] 如果需要合并或开 PR，使用 `superpowers:finishing-a-development-branch` 决定后续路径。

**Commit:** `chore(repo): 验证 AI 底座重构回归`

## Spec Coverage Checklist

- [ ] DeepSeek 官方 API 调用使用 `langchain_deepseek.ChatDeepSeek`。
- [ ] vivo 文本与 vivo Vision 通过 LangChain OpenAI-compatible provider 接入。
- [ ] 本轮迁移包含 vivo Vision。
- [ ] `.env` 默认项目根目录，`python-dotenv` 自动加载，系统环境变量优先。
- [ ] 本地图片不作为 `image_url` 本地路径上传，统一转 base64 data URL。
- [ ] `VivoLongAsrClient` 纳入 `AIService`，但继续自定义协议。
- [ ] `VivoOcrClient` 纳入 `AIService`，但继续自定义协议。
- [ ] V2 graph、grading、streaming、资料解析增强、视频抽帧解析只保留结构，不接业务。
- [ ] 现有 parser、quiz、handout、QA 测试通过。
- [ ] 每个实施任务使用 subagent-driven-development 的 implementer、spec reviewer、code quality reviewer 三段质量门。

## Commit Sequence

```text
chore(repo): 引入 LangChain 依赖并加载根目录环境配置
feat(ai): 新增统一 AI 核心契约
feat(ai): 增加 LangChain 统一调用服务
refactor(ai): 将 DeepSeek JSON 调用迁移到 LangChain
refactor(ai): 统一文本生成客户端调用底座
refactor(ai): 将 vivo Vision 接入统一调用底座
refactor(ai): 将 vivo OCR 和 ASR 纳入统一底座
feat(ai): 预留 V2 AI 能力契约
chore(repo): 验证 AI 底座重构回归
```
