# AI Service Layer LangChain V2 Design

日期：2026-05-15

## 1. 目标

统一 KnowLink 后端的 AI 调用底座，先解决现有 LLM 和 vivo vision 调用分散、provider 行为不统一、结构化输出解析重复的问题，同时把 vivo ASR/OCR 这类自定义协议收编到同一个 facade 和 registry 中。LangChain 用于 chat、vision 和后续模型编排；非 LangChain 协议继续作为 custom adapter。底座同时为 V2 的流式输出、知识图谱、主观题判卷、资料解析增强和视频抽帧解析预留清晰结构。

第一轮不实现完整 V2 业务能力。知识图谱、SSE 流式输出、主观题判卷、资料解析增强、视频抽帧解析只定义接口形状和目录边界，避免把底座重构和新业务链路绑在一个大改动里。

## 2. 当前上下文

当前 `server/ai` 不是统一服务层，而是按能力拆开的函数和 provider client：

- `server/ai/deepseek.py` 自写 OpenAI-compatible chat JSON client。
- `server/ai/handout_lazy.py`、`server/ai/handout_block.py`、`server/ai/qa_policy.py`、`server/ai/quiz_strategy.py` 各自构造 prompt、HTTP 请求、JSON 解析和 provider 配置。
- `server/ai/ocr.py`、`server/ai/asr.py`、`server/ai/embedding.py`、`server/ai/vision.py` 对接 vivo 自定义或 OpenAI-compatible 能力。
- `server/ai/pipelines/*` 目前只是占位实现，不承载真实编排。

现有业务有强兼容约束：

- 未配置模型时，handout/QA 等路径必须 fallback 或返回 `None`，不能在初始化阶段提前抛异常改变控制流。
- 模型输出必须继续经过 KnowLink 的业务校验，包括 `sourceSegmentKeys`、视频时间线、locator 单一性、citation 反查、quiz source repair 和 jsonschema 验证。
- Embedding 必须保持输入顺序和输出数量严格一致。
- vivo ASR/OCR/部分 embedding endpoint 是非标准 REST 协议，不应强行塞进 LangChain。
- vivo ASR/OCR 仍应纳入统一 AI facade 和 provider registry，统一配置装配、错误映射和调用入口，但底层协议保持 custom adapter。

## 3. 依赖与配置

### 3.1 LangChain 依赖

引入 LangChain v1 相关依赖，使用 provider 拆分包：

- `langchain>=1.3,<2.0`
- `langchain-core>=1.4,<2.0`
- `langchain-openai>=1.2,<2.0`
- `langchain-deepseek>=1.0,<2.0`

保留当前 `openai>=1.54,<2.0`。`langchain-openai` 只用于 OpenAI-compatible provider，例如 vivo chat completion；DeepSeek 官方 API 使用 `langchain-deepseek` 的 `ChatDeepSeek`，不走带 `base_url` 覆盖的 `ChatOpenAI`。第一轮不引入 `langchain-community`，除非后续实现确实需要 community integration。

### 3.2 dotenv 加载

`python-dotenv` 已在 `pyproject.toml` 中声明，但当前代码没有实际调用。底座重构必须补上自动读取 `.env` 的配置入口。

规则：

- 默认读取项目根目录 `.env`，即仓库根目录下的 `.env`。
- 代码定位使用 `Path(__file__).resolve().parents[2] / ".env"`，因为 `server/config/settings.py` 位于 `server/config/`。
- 使用 `load_dotenv(dotenv_path=root_env_path, override=False)`。
- 系统环境变量优先级高于 `.env`，部署环境显式注入的变量不能被 `.env` 覆盖。
- 不读取 `.env.example`。
- `.env` 缺失时不报错，继续使用当前默认值和系统环境变量。
- 测试需要覆盖 `.env` 读取、系统环境变量优先、缺失 `.env` 不失败、`get_settings()` cache clear 后可重新读取。

## 4. 设计范围

### 4.1 本轮实现范围

本轮 spec 只覆盖调用底座：

- 新增统一 AI service facade。
- 新增 LangChain chat provider adapter。
- 新增 LangChain multimodal vision provider adapter。
- 新增 custom ASR/OCR provider adapter 的统一装配入口。
- 新增共享 JSON 输出解析和错误映射。
- 逐步迁移现有 LLM 和 vivo vision 调用方到统一底座；ASR/OCR 第一轮只收编配置和 facade 边界，不重写多阶段协议。
- 保留现有业务函数外部签名，降低 router/task/service 的改动面。
- 预留 V2 能力目录和协议，不接真实业务流。

优先承接的调用方：

- DeepSeek quiz generation。
- DeepSeek/Vivo handout outline。
- DeepSeek/Vivo handout block。
- DeepSeek/Vivo QA answer。
- Vivo vision extraction。
- VivoLongAsrClient 和 VivoOcrClient 的 facade/registry 收编。

### 4.2 不在本轮实现

以下内容不在第一轮实现：

- 完整知识图谱生成。
- 完整主观题判卷。
- 完整资料解析增强策略。
- 完整视频抽帧解析链路。
- 持久化 SSE event store。
- Flutter 流式展示。
- ASR/OCR 的 LangChain 化。
- 自定义 vivo embedding endpoint 的 LangChain 化。
- 大规模 prompt 重写。

## 5. 目标架构

新增结构建议：

```text
server/ai/
  core/
    __init__.py
    errors.py
    json_output.py
    messages.py
    types.py
  providers/
    __init__.py
    deepseek_chat.py
    langchain_chat.py
    vision_chat.py
    registry.py
    vivo/
      __init__.py
      asr.py
      ocr.py
  service.py
  prompts/
    __init__.py
  v2/
    __init__.py
    graph.py
    grading.py
    parsing.py
    streaming.py
    video_frames.py
```

职责：

- `core/types.py` 定义 `ChatRequest`、`JsonChatRequest`、`ChatModelConfig`、`AIUsage`、`AIModelResult` 等稳定类型。
- `core/errors.py` 定义 `AIConfigurationError`、`AIProviderError`、`AIOutputParseError`，并提供到现有 fallback reason 的映射。
- `core/json_output.py` 复用当前 JSON object 抽取能力，保留对 fenced JSON、content list、普通 string content 的兼容。
- `providers/deepseek_chat.py` 封装 `langchain_deepseek.ChatDeepSeek`，专门承接 DeepSeek 官方 API。
- `providers/langchain_chat.py` 封装 LangChain `ChatOpenAI`、`ChatPromptTemplate` 或 message list 调用，承接 vivo 这类 OpenAI-compatible chat provider。
- `providers/vision_chat.py` 封装 OpenAI-compatible multimodal chat 调用，承接 `VivoVisionClient` 当前的 base64 data URL 图片理解路径。
- `providers/vivo/asr.py` 保留 `VivoLongAsrClient` 的五段式上传、轮询和结果解析协议，对外仍暴露 `AsrClient` 能力端口。
- `providers/vivo/ocr.py` 保留 `VivoOcrClient` 的 form-encoded OCR REST 协议，对外仍暴露 `OcrClient` 能力端口。
- `providers/registry.py` 负责按 env 构造 provider，不让业务模块直接读散落的 provider 细节。
- `service.py` 对业务暴露 `complete_json()`、`complete_vision_json()`、`asr_client()`、`ocr_client()`，预留 `stream_events()`。
- `prompts/` 第一轮只作为新 prompt builder 的落点，不强制搬迁现有常量 prompt。
- `v2/` 只放协议和空实现边界，为后续 graph/grading/parsing/streaming/video frame extraction 计划使用。

## 6. Provider 策略

### 6.1 DeepSeek 官方 provider

DeepSeek 使用 LangChain 官方 DeepSeek provider：

- 依赖包：`langchain-deepseek`。
- import：`from langchain_deepseek import ChatDeepSeek`。
- 默认模型仍由 `KNOWLINK_DEEPSEEK_MODEL` 控制。
- 当前项目已有 `KNOWLINK_DEEPSEEK_API_KEY`，registry 必须继续支持该变量；adapter 可在内部桥接到 `ChatDeepSeek` 需要的 credential 参数或 `DEEPSEEK_API_KEY`，但不能要求开发者重复配置两份 key。
- DeepSeek hosted API 的默认路径使用官方 provider 默认值；只有明确需要私有网关时，才通过配置扩展覆盖 base URL。
- 结构化 JSON 任务优先使用支持 structured output 的 DeepSeek chat 模型。若配置到不支持 structured output 的 reasoning 模型，底座必须回退到 raw content JSON 抽取和业务 validator，不能绕过现有校验。

### 6.2 OpenAI-compatible chat and vision

vivo chat completion 和 vivo vision extraction 按 OpenAI-compatible provider 处理：

- vivo 保留 `request_id` query 参数、`temperature`、`max_tokens`、`stream=False` 等当前行为。
- provider adapter 需要允许传入额外 body 或 query 参数，避免 LangChain 默认参数吞掉现有 provider 特性。
- vision adapter 必须保留当前多模态 content list 语义：文本 prompt 加 `image_url` content block。
- vision adapter 不能把本地文件路径直接传给 `image_url`。本地图片必须先读取 bytes，按 MIME type 编码为 `data:<mime>;base64,<payload>`，再写入 `image_url.url`。
- 只有图片已经有 provider 可访问的 HTTPS URL 时，才允许直接传远程 URL；默认 parser 路径使用 base64 data URL。
- vision adapter 的输出仍必须经过当前 `VisionAssetResult` 解析和校验，模型只能产生 `assetId`、`segmentType`、`textContent` 等 schema-compatible 字段。
- vision adapter 需要保留当前对“不支持图片输入”的错误识别能力，避免 parser 层失去 `vision_model_unsupported` 类 issue。

### 6.3 非标准能力

以下能力继续保留 custom adapter，不做 LangChain 化：

- `VivoLongAsrClient`
- `VivoOcrClient`
- vivo 自定义 embedding batch endpoint

Vision 已纳入第一轮迁移，但只迁移当前 `VivoVisionClient` 的 chat-completions 多模态路径，不改变 parser 对 OCR、vision failure 和 unsupported model 的降级语义。

`VivoLongAsrClient` 和 `VivoOcrClient` 可以纳入统一 AIService facade 和 registry，但不能包装成 LangChain chat model、embedding model 或 structured-output parser：

- ASR 是 `create -> upload slices -> run -> progress poll -> result` 的多阶段文件协议，包含 multipart 上传、`x-sessionId`、毫秒级 `system_time`、`engineid` 和轮询超时。
- OCR 是 `POST /ocr/general_recognition?requestId={request_id}` 的 form-encoded REST 协议，body 包含 base64 `image`、固定 `pos=2` 和 `businessid`。
- 两者的业务质量门都在 parser 层：ASR timeline 校验、OCR 质量判断、OCR 优先于 vision、vision fallback、issue code 都不能下沉到 provider。

统一底座对 ASR/OCR 只负责装配、配置、错误归一和能力暴露；具体协议、节流、分片、bbox 解析、毫秒转秒等细节保持在 custom adapter 内。

## 7. 数据流

### 7.1 非流式 JSON 调用

标准数据流：

1. 业务函数构造现有 prompt context。
2. 业务函数调用 `AIService.complete_json(request)`。
3. `AIService` 通过 registry 获取 provider config。
4. LangChain adapter 构造 model 和 messages。
5. Provider 返回 raw message。
6. `json_output.py` 抽取 JSON object。
7. 业务模块继续运行现有 normalizer 和 validator。
8. 成功返回当前 schema-compatible payload；失败按原语义 fallback、repair 或抛错。

业务校验不能下沉到 LangChain parser 内部。LangChain parser 只负责把模型输出转成 dict；KnowLink normalizer 仍负责判断 dict 是否可信。

### 7.2 预留流式调用

第一轮只定义接口：

```python
class AIService:
    def stream_events(self, request: StreamChatRequest) -> Iterator[AIStreamEvent]:
        raise NotImplementedError("reserved for V2 streaming integration")
```

预留事件类型：

- `llm.delta`
- `llm.completed`
- `artifact.updated`
- `provider.error`

本轮不落库、不提供 SSE endpoint。后续 V2 流式计划再把 `AIStreamEvent` 映射到 `async_tasks` 事件表或 Redis Stream。

### 7.3 Vision 调用

第一轮 vision 数据流：

1. Parser 继续按当前逻辑收集图片 asset、构造 prompt 和 data URL。
2. `VivoVisionClient` 或其替代 wrapper 调用 `AIService.complete_vision_json(request)`。
3. `providers/vision_chat.py` 使用 OpenAI-compatible multimodal message 调用 vivo vision model。
4. `core/json_output.py` 抽取 JSON object。
5. `server/ai/vision.py` 继续执行当前 schema 校验和 `VisionAssetResult` normalization。
6. Parser 继续把失败映射为现有 `ParserIssue`，包括 `vision_failed` 和 `vision_model_unsupported`。

Vision 迁移不能改变 PDF/PPTX/DOCX parser 对失败图片的处理方式。

### 7.4 ASR/OCR custom 调用

ASR/OCR 数据流保持现有协议，改动只发生在装配边界：

1. Parser 通过 `AIService.asr_client()` 或 `AIService.ocr_client()` 获取能力端口。
2. ASR 仍调用 `AsrClient.transcribe(file_path)`，返回 `list[AsrSegment]`。
3. OCR 仍调用 `OcrClient.recognize_images(assets, resource_type=resource_type)`，返回 `list[OcrAssetResult]`。
4. Parser 继续负责把异常映射成 `mp4.asr_failed`、`pdf.ocr_failed`、`pptx.ocr_failed`、`docx.ocr_failed` 等 issue。
5. Parser 继续负责 OCR 低质判断、重复过滤、vision fallback 和 ASR timeline 校验。

ASR/OCR 不能通过 LangChain `Runnable` 改写成单次模型调用。后续如果需要观测性，可以在 custom adapter 外层加 trace/span，但不改变协议形态。

## 8. 错误处理与兼容语义

错误处理必须保持现有业务差异：

- Handout outline：provider 未配置或模型失败时 fallback 到字幕分组 outline。
- Handout block：provider 未配置或模型失败时 fallback 到本地 block。
- QA：候选证据不足时返回 `insufficient_evidence`；模型失败时 fallback 到候选证据回答。
- Quiz：provider 未配置时继续抛 `deepseek quiz generation is not configured`；模型输出 source 错误时保留 repair once；非可修复错误继续抛 `ValueError`。
- Embedding：不改变现有失败语义，向量化失败仍允许 parse pipeline 进入 `partial_success`。

LangChain 的异常类型必须映射为 KnowLink 内部错误，不能把 provider-specific exception 泄漏到业务层。

## 9. V2 预留结构

### 9.1 知识图谱

`server/ai/v2/graph.py` 只定义协议：

- 输入：课程、讲义块、segments、knowledge points、citations。
- 输出：nodes、edges、evidenceRefs、confidence、version、generationMetadata。

不实现生成逻辑，不新增数据库表。

### 9.2 主观题判卷

`server/ai/v2/grading.py` 只定义协议：

- 输入：题目、学生答案、参考答案、rubric、RAG evidence candidates。
- 输出：totalScore、dimensionScores、feedback、deductions、evidenceRefs、confidence、needsHumanReview、judgeVersion。

不实现评分逻辑，不接 quiz API。

### 9.3 流式输出

`server/ai/v2/streaming.py` 只定义 AI stream event 类型和 mapping helper。

不实现 SSE，不改 `async_tasks` schema。

### 9.4 资料解析增强

`server/ai/v2/parsing.py` 只定义协议：

- 输入：resource metadata、normalized document segments、parser issues、layout hints、可选 vision/OCR results。
- 输出：enhancedSegments、layoutBlocks、tableCandidates、formulaCandidates、figureCandidates、qualitySignals、evidenceRefs、generationMetadata。

该协议用于后续复杂版面、公式、表格、图文混排增强。第一轮不改变现有 parser 输出 schema，不新增数据库表。

### 9.5 视频抽帧解析

`server/ai/v2/video_frames.py` 只定义协议：

- 输入：video metadata、caption segments、frame sampling policy、frame assets、timestamp range。
- 输出：frameObservations、visualSegments、slideChangeCandidates、boardTextCandidates、frameRefs、qualitySignals、generationMetadata。

该协议用于后续从视频画面抽取板书、幻灯片变化、图示和视觉线索。第一轮不实现 ffmpeg 抽帧、不上传 frame asset、不改 `VideoParser` 主流程。

## 10. 测试策略

测试分三层。

### 10.1 配置测试

新增或更新 settings 测试：

- 根目录 `.env` 会被读取。
- 系统环境变量覆盖 `.env`。
- `.env` 缺失不报错。
- `get_settings.cache_clear()` 后可以反映新的 env。

### 10.2 LangChain 底座单元测试

使用 fake model 或 monkeypatch LangChain adapter，不依赖真实 API key：

- `complete_json()` 能解析普通 JSON string。
- `complete_json()` 能解析 fenced JSON。
- `complete_json()` 能解析 content list 中的 text。
- `complete_vision_json()` 能发送 text + `image_url.url=data:<mime>;base64,<payload>` content blocks。
- `complete_vision_json()` 不接受本地文件路径作为 `image_url.url`。
- `AIService.asr_client()` 保持 enable flag 默认关闭、缺 key 返回 `None`、五段式 vivo LASR 协议顺序、5MB 分片和 100 片上限。
- `AIService.ocr_client()` 保持 enable flag 默认关闭、缺 key/businessid 返回 `None`、`businessid=aigc{APP_ID}`、`pos=2`、0.2s throttle 和 bbox 归一化。
- vision malformed JSON 映射到 `AIOutputParseError`。
- vision unsupported-model/provider error 能被业务层映射回当前 parser issue。
- provider error 映射到 `AIProviderError`。
- malformed JSON 映射到 `AIOutputParseError`。
- provider-specific model kwargs 能传入 adapter。

### 10.3 业务兼容测试

现有测试必须继续通过，并优先关注：

- `server/tests/test_handout_lazy.py`
- `server/tests/test_handout_block.py`
- `server/tests/test_qa_policy.py`
- `server/tests/test_quiz_strategy.py`
- `server/tests/test_parsers.py`
- `server/tests/test_demo_assets_smoke.py`
- `server/tests/test_embedding.py`
- `server/tests/test_parse_pipeline_worker.py`

新增迁移测试时，先锁住当前行为，再替换底层调用实现。

## 11. 验收标准

本轮完成后应满足：

- `pyproject.toml` 引入 LangChain v1 provider 依赖。
- 后端自动读取项目根目录 `.env`，且系统环境变量优先。
- LLM JSON 调用存在统一底座，业务模块不再各自重复维护 HTTP chat client。
- Vivo vision 多模态 JSON 调用接入统一底座，PDF/PPTX/DOCX parser 的视觉增强失败语义保持兼容。
- VivoLongAsrClient 和 VivoOcrClient 被统一 facade/registry 收编，但仍保持 custom adapter 协议，不做 LangChain 化。
- DeepSeek quiz、DeepSeek/Vivo handout、DeepSeek/Vivo QA 的外部行为保持兼容。
- V2 graph/grading/streaming/parsing/video frame extraction 有清晰协议和目录，但没有未完成业务逻辑。
- 现有 AI、parser、runtime 测试通过。

## 12. 实施拆分建议

后续 implementation plan 可拆为：

1. 配置和依赖：LangChain 依赖、根目录 `.env` 自动加载、配置测试。
2. AI core：类型、错误、JSON 输出解析、底座单元测试。
3. Provider adapter：`ChatDeepSeek` adapter、OpenAI-compatible vivo chat/vision adapter、custom ASR/OCR adapter 装配、registry 和 provider config。
4. 迁移 DeepSeek quiz：保持 repair/failure 行为。
5. 迁移 handout outline/block：保持 fallback 行为。
6. 迁移 QA：保持候选证据和 fallback 行为。
7. 迁移 vivo vision：保持 multimodal data URL、schema normalization 和 parser issue 行为。
8. 收编 ASR/OCR：通过 facade/registry 暴露 `AsrClient` 和 `OcrClient`，不改底层 custom REST/multipart 协议。
9. V2 预留协议：graph/grading/streaming/parsing/video frame extraction 空结构和轻量测试。
10. 全量回归：AI、parser 相关 pytest 与必要 runtime contract。
