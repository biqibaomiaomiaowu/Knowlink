# vivo AI 接入研究

本文件用于沉淀中国高校计算机大赛 AIGC 创新赛 vivo 文档站的可复用接入事实，服务于后续 agent 检索、KnowLink 落地设计与具体工程接入。

- 适用范围：vivo 比赛文档站中当前已抓到的 29 个节点，其中 19 个 article 正文节点、10 个 category 目录节点（无独立正文）
- 不替代：`ARCHITECTURE.md`、`docs/contracts/api-contract.md`、`docs/contracts/error-codes.md`
- authoritative 口径：本文件是第三方能力研究与实现参考，不是 KnowLink 自身 contract

## 1. 文档目的与适用范围

- 为后续 agent 提供稳定入口：先读本文件，再按需回溯 sidecar 快照
- 把“页面树、分类页判定、接口模式、鉴权、限额、实现注意事项”收成机器友好的归一事实
- 避免后续实现再次依赖浏览器登录或本机 `Downloads/` 路径

## 2. 快照元信息

```yaml
doc_set_id: vivo_aigc_competition_2026-04-21
vendor: vivo_aigc
source_site: https://aigc.vivo.com.cn
snapshot_at: 2026-04-21
last_verified_at: 2026-04-22
snapshot_basis:
  tree_endpoint: /vstack/webapi/service/doc/tree
  detail_endpoint: /vstack/webapi/service/doc/info/v1
snapshot_files:
  docs_json: docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json
coverage:
  total_nodes: 29
  article_nodes: 19
  category_nodes: 10
extraction_methods:
  - 调用 /vstack/webapi/service/doc/tree 获取目录树与父子关系
  - 调用 /vstack/webapi/service/doc/info/v1 获取单页正文详情
known_limits:
  - 10 个分类节点在 /vstack/webapi/service/doc/info/v1 中返回 {"retcode":0,"msg":"success","data":{}}
  - 分类节点只提供树结构，不提供独立正文
  - 当前 docs.json 只保留清洗后的正文文本，不保留原始 HTML 与上游运营元数据
last_verified_from:
  - /vstack/webapi/service/doc/tree 的目录树响应
  - /vstack/webapi/service/doc/info/v1 的单页详情响应
  - 导出的 docs.json
```

## 3. 页面索引

判定规则：

- `article`：`/vstack/webapi/service/doc/info/v1?docId=...` 返回非空 `data`，且 `docs.json` 中 `text` 非空
- `category`：`/vstack/webapi/service/doc/info/v1?docId=...` 返回空 `data`，且 `/vstack/webapi/service/doc/tree` 中存在子节点
- `must_read=true`：实际实现时通常需要直接阅读的正文页

| doc_id | title | page_kind | parent_doc_id | child_doc_ids | tree_path | capability_tags | content_length | must_read | snapshot_file |
|---|---|---|---|---|---|---|---:|---|---|
| 1676 | 文档中心 | category | - | 1746,1677,1720 | 文档中心 | `platform.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1746 | 使用指引 | article | 1676 | - | 文档中心 > 使用指引 | `platform.overview` | 582 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1677 | 鉴权方式 | article | 1676 | - | 文档中心 > 鉴权方式 | `platform.access` | 1336 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1720 | 接口文档 | category | 1676 | 1744,1724,2200,1727,1728,1725,1726,1729 | 文档中心 > 接口文档 | `platform.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1744 | 文本生成 | category | 1720 | 1745,1805 | 文档中心 > 接口文档 > 文本生成 | `llm.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1745 | 大模型 | article | 1744 | - | 文档中心 > 接口文档 > 文本生成 > 大模型 | `llm.chat` | 15745 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1805 | Function calling | article | 1744 | - | 文档中心 > 接口文档 > 文本生成 > Function calling | `llm.function_calling` | 2833 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1724 | 图片生成 | category | 1720 | 1732 | 文档中心 > 接口文档 > 图片生成 | `image.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1732 | 图片生成 | article | 1724 | - | 文档中心 > 接口文档 > 图片生成 > 图片生成 | `image.generation` | 4441 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2200 | 视频生成 | category | 1720 | 2201 | 文档中心 > 接口文档 > 视频生成 | `video.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2201 | 视频生成 | article | 2200 | - | 文档中心 > 接口文档 > 视频生成 > 视频生成 | `video.generation` | 3675 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1727 | 视觉技术 | category | 1720 | 1737 | 文档中心 > 接口文档 > 视觉技术 | `vision.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1737 | 通用OCR | article | 1727 | - | 文档中心 > 接口文档 > 视觉技术 > 通用OCR | `vision.ocr` | 2526 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1728 | 自然语言处理 | category | 1720 | 1733,1734,2060,2061 | 文档中心 > 接口文档 > 自然语言处理 | `nlp.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1733 | 文本翻译 | article | 1728 | - | 文档中心 > 接口文档 > 自然语言处理 > 文本翻译 | `nlp.translation` | 1816 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1734 | 文本向量 | article | 1728 | - | 文档中心 > 接口文档 > 自然语言处理 > 文本向量 | `nlp.embedding` | 2511 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2060 | 文本相似度 | article | 1728 | - | 文档中心 > 接口文档 > 自然语言处理 > 文本相似度 | `nlp.similarity` | 1873 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2061 | 查询改写 | article | 1728 | - | 文档中心 > 接口文档 > 自然语言处理 > 查询改写 | `nlp.query_rewrite` | 2306 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1725 | ASR | category | 1720 | 1738,1740,1739,2065,2068 | 文档中心 > 接口文档 > ASR | `asr.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1738 | 实时短语音识别 | article | 1725 | - | 文档中心 > 接口文档 > ASR > 实时短语音识别 | `asr.realtime_short` | 2711 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1740 | 长语音听写 | article | 1725 | - | 文档中心 > 接口文档 > ASR > 长语音听写 | `asr.long_dictation` | 3487 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1739 | 长语音转写 | article | 1725 | - | 文档中心 > 接口文档 > ASR > 长语音转写 | `asr.long_transcription` | 4329 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2065 | 方言自由说 | article | 1725 | - | 文档中心 > 接口文档 > ASR > 方言自由说 | `asr.dialect_free_speech` | 2896 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2068 | 同声音传译 | article | 1725 | - | 文档中心 > 接口文档 > ASR > 同声音传译 | `asr.same_voice_interpretation` | 4829 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1726 | TTS | category | 1720 | 1735,2062 | 文档中心 > 接口文档 > TTS | `tts.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1735 | 音频生成 | article | 1726 | - | 文档中心 > 接口文档 > TTS > 音频生成 | `tts.audio_generation` | 10454 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 2062 | 声音复刻 | article | 1726 | - | 文档中心 > 接口文档 > TTS > 声音复刻 | `tts.voice_clone` | 2759 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1729 | LBS | category | 1720 | 1736 | 文档中心 > 接口文档 > LBS | `lbs.index` | 0 | false | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |
| 1736 | 地理编码(POI搜索) | article | 1729 | - | 文档中心 > 接口文档 > LBS > 地理编码(POI搜索) | `lbs.poi_search` | 3839 | true | `docs/vendor-snapshots/vivo-aigc/2026-04-21-docs.json` |

分类节点统一判定理由：

- `/vstack/webapi/service/doc/tree` 返回了明确的父子节点关系
- `/vstack/webapi/service/doc/info/v1` 对这 10 个节点返回空 `data`
- 同一树下的 article 子节点能返回非空正文，因此这些节点当前应视为目录节点而不是漏抓正文

## 4. 能力总览

`1746 使用指引` 给出的能力总览如下：

| 大类 | 代表能力 | 正文 doc_id |
|---|---|---|
| 文本生成 | 大模型、Function calling | `1745`、`1805` |
| 图片生成 | 文生图、图生图、风格转换 | `1732` |
| 视频生成 | 文生视频、图生视频 | `2201` |
| 视觉技术 | 通用 OCR | `1737` |
| 自然语言处理 | 翻译、向量、相似度、查询改写 | `1733`、`1734`、`2060`、`2061` |
| ASR | 实时短语音、长语音听写、长语音转写、方言自由说、同声音传译 | `1738`、`1740`、`1739`、`2065`、`2068` |
| TTS | 音频生成、声音复刻 | `1735`、`2062` |
| LBS | 地理编码(POI搜索) | `1736` |

## 5. 鉴权与公共调用约定

共性事实：

- AppKey 获取入口：`https://aigc.vivo.com.cn/#/platform`
- 鉴权头：`Authorization: Bearer AppKey`
- 统一失败信号：鉴权文档明确给出 `HTTP 401`
- 已知鉴权失败响应：
  - `{"message":"missing required app_id in the request header"}`
  - `{"message":"invalid api-key"}`
  - `{"message":"not having this ability, you need to apply for it"}`

调用模式分三类：

- OpenAI 兼容 HTTP：`llm.chat`
- 自定义同步 REST：`image.generation`、`vision.ocr`、`nlp.*`、`lbs.poi_search`
- 自定义异步 REST / WebSocket：`video.generation`、`asr.*`、`tts.*`、`tts.voice_clone`

## 6. Quick Lookup

### 6.1 Auth Quick Lookup

| auth_scheme | header_name | token_source | failure_status | source_doc_ids |
|---|---|---|---|---|
| `Bearer AppKey` | `Authorization` | `https://aigc.vivo.com.cn/#/platform` | `401` | `1677` |

### 6.2 Endpoint Matrix

| capability_id | method | host | path | pattern | source_doc_ids |
|---|---|---|---|---|---|
| `llm.chat` | `POST` | `api-ai.vivo.com.cn` | `/v1/chat/completions` | `openai_compatible_sync` | `1745` |
| `image.generation` | `POST` | `api-ai.vivo.com.cn` | `/api/v1/image_generation` | `custom_sync` | `1732` |
| `video.generation.submit` | `POST` | `api-ai.vivo.com.cn` | `/api/v1/submit_task` | `custom_async` | `2201` |
| `video.generation.query` | `GET` | `api-ai.vivo.com.cn` | `/api/v1/query_task` | `custom_async` | `2201` |
| `vision.ocr` | `POST` | `api-ai.vivo.com.cn` | `/ocr/general_recognition` | `custom_sync` | `1737` |
| `nlp.translation` | `POST` | `api-ai.vivo.com.cn` | `/translation/query/self` | `custom_sync` | `1733` |
| `nlp.embedding` | `POST` | `api-ai.vivo.com.cn` | `/embedding-model-api/predict/batch` | `custom_sync` | `1734` |
| `nlp.similarity` | `POST` | `api-ai.vivo.com.cn` | `/rerank` | `custom_sync` | `2060` |
| `nlp.query_rewrite` | `POST` | `api-ai.vivo.com.cn` | `/query_rewrite_base` | `custom_sync` | `2061` |
| `asr.realtime_short` | `WS` | `api-ai.vivo.com.cn` | `/asr/v2` | `custom_ws_stream` | `1738` |
| `asr.long_dictation` | `WS` | `api-ai.vivo.com.cn` | `/asr/v2` | `custom_ws_stream` | `1740` |
| `asr.long_transcription` | `POST + multipart + GET` | `api-ai.vivo.com.cn` | `/lasr/*` | `custom_async_multi_step` | `1739` |
| `asr.dialect_free_speech` | `WS` | `api-ai.vivo.com.cn` | `/asr/v2` | `custom_ws_stream` | `2065` |
| `asr.same_voice_interpretation` | `WS` | `api-ai.vivo.com.cn` | `/asr/v2` | `custom_ws_stream` | `2068` |
| `tts.audio_generation` | `WSS` | `api-ai.vivo.com.cn` | `/tts` | `custom_ws_stream` | `1735` |
| `tts.voice_clone` | `POST` | `api-ai.vivo.com.cn` | `/replica/create_vcn_task` | `custom_async` | `2062` |
| `lbs.poi_search` | `GET` | `api-ai.vivo.com.cn` | `/search/geo` | `custom_sync` | `1736` |

### 6.3 Special Params / Headers

| capability_id | required_header_or_param | where | why_it_matters | source_doc_ids |
|---|---|---|---|---|
| `llm.chat` | `Authorization`, `Content-Type`, `requestId/request_id` | header + query/request | 鉴权在 header，请求追踪 id 在请求参数或 SDK query 中 | `1677,1745` |
| `image.generation` | `module=aigc`, `request_id`, `system_time(秒)` | query | 图片接口不是 OpenAI 兼容风格，少一个都不应假定可省略 | `1732` |
| `video.generation` | `module=aigc`, `request_id`, `system_time(秒)`, `task_id(查询阶段)` | query | 提交任务和查询任务都依赖公共 query 参数，轮询时还必须补 `task_id` | `2201` |
| `asr.*` | `user_id`, `requestId`, `system_time(毫秒)`, `engineid` 等 | query | ASR 能力是移动端导向协议，参数量远大于普通 REST，且 `system_time` 用毫秒 | `1738,1740,1739,2065,2068` |
| `tts.audio_generation` | `engineid`, `user_id`, `system_time(秒)`, `requestId` 等 | query | TTS WebSocket 握手必须带设备/应用元信息，且 `system_time` 用秒 | `1735` |
| `tts.voice_clone` | `multipart/form-data`, `requestId` | header + query + body | 声音复刻是文件上传任务，不是 JSON body 接口 | `2062` |
| `lbs.poi_search` | `keywords`, `city`, `requestId` | query | `keywords` 与 `city` 为主输入，分页参数有上限 | `1736` |

### 6.4 Quota / Competition Limits

| capability_id | daily_limit | total_limit | notes | source_doc_ids |
|---|---:|---:|---|---|
| `image.generation` | 10 | 300 | 初赛期间限制提交任务次数 | `1732` |
| `video.generation` | 5 | 50 | 初赛阶段限制生成视频任务次数 | `2201` |
| `llm.chat` | - | - | 文档提到存在 QPS 限流与单日用量限制错误码 `2003`，但未给固定数值 | `1745` |

### 6.5 Implementation Gotchas

| topic | rule | affected_capabilities | source_doc_ids |
|---|---|---|---|
| 分类页 | 不要对 `1720/1744/1724/2200/1727/1728/1725/1726/1729` 直接做实现推断，正文在其子页 | `all` | `1720,1744,1724,2200,1727,1728,1725,1726,1729` |
| LLM 兼容口径 | 文档宣称支持 OpenAI / Responses 风格，但明确给出的生产接口只有 `/v1/chat/completions` | `llm.chat` | `1745` |
| 模型字段差异 | 思考开关字段按模型不同而不同：`thinking.type` 与 `enable_thinking` 不能混用 | `llm.chat` | `1745` |
| 图片输入 | 2026-04-21 快照时图片接口只明确支持 URL 输入，base64 仍是“预计支持”状态 | `image.generation` | `1732` |
| 图片超时 | 图片生成是同步接口，但文档样例与说明表明单图可能耗时 10-30 秒，请求超时不要按普通 REST 的 5-10 秒设置 | `image.generation` | `1732` |
| 异步模式 | 视频生成不是同步返回视频 URL，而是“提交任务 + 轮询查询任务” | `video.generation` | `2201` |
| 时间戳单位 | `system_time` 不是全站统一单位：图片/视频/TTS 用 Unix 秒，ASR/长语音转写 用 Unix 毫秒 | `image.generation`, `video.generation`, `asr.*`, `tts.audio_generation` | `1732,2201,1738,1740,1739,2065,2068,1735` |
| 协议偏移动端 | ASR/TTS 多数接口要求设备、系统、包名、SDK 版本等 query 参数 | `asr.*`, `tts.*` | `1738,1740,1739,2065,2068,1735` |
| 协议示例不一致 | 多篇 ASR 文档示例中同时出现 `api-ai.vivo.com.cn` 与测试域名/`ws://` URL，生产接入前要再实测 TLS 口径 | `asr.*` | `1738,1740,2065,2068` |
| Function calling 口径 | `1805` 讲的是 message 组织与 schema 提示词，不是新 endpoint；优先复用 `llm.chat` 的 `tools` 能力 | `llm.function_calling` | `1745,1805` |
| 翻译 body | 文本翻译文档中 `app=test` 是必填字段，不是普通示例值 | `nlp.translation` | `1733` |
| 向量检索 instruction | `bge-base-zh-v1.5` 做检索时，query 前需要补 instruction 句式 | `nlp.embedding` | `1734` |
| 转写流程 | 长语音转写是 5 阶段协议，且 create/upload 必须复用同一 `x-sessionId` | `asr.long_transcription` | `1739` |
| 声音复刻对接 | 声音复刻产出的是 `vcn` 与 `engineid`，后续仍需配合 `tts.audio_generation` 真正合成音频 | `tts.voice_clone` | `2062,1735` |

## 7. 能力分项摘要

### 7.1 `platform.overview`

```yaml
capability_id: platform.overview
display_name: 使用指引
source_doc_ids: [1746]
supporting_category_doc_ids: [1676]
integration_pattern: documentation_index
base_url: null
endpoints: []
auth_scheme: see platform.access
required_headers: []
required_query_params: []
required_body_fields: []
optional_body_fields: []
response_pattern: null
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 该页是能力索引页，不是调用文档
  - 真正可实现的协议需要继续读各子页
must_read_order: [1746, 1677, 1745, 1732, 2201]
confidence: high
```

### 7.2 `platform.access`

```yaml
capability_id: platform.access
display_name: 鉴权方式
source_doc_ids: [1677]
supporting_category_doc_ids: [1676]
integration_pattern: shared_auth
base_url: https://aigc.vivo.com.cn/#/platform
endpoints: []
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params: []
required_body_fields: []
optional_body_fields: []
response_pattern: shared_auth
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals:
  - HTTP 401
  - missing required app_id in the request header
  - invalid api-key
  - not having this ability, you need to apply for it
implementation_gotchas:
  - 先确认应用已开通对应能力，再排查代码问题
must_read_order: [1677]
confidence: high
```

### 7.3 `llm.chat`

```yaml
capability_id: llm.chat
display_name: 大模型
source_doc_ids: [1745]
supporting_category_doc_ids: [1744, 1720]
integration_pattern: openai_compatible_sync
base_url: https://api-ai.vivo.com.cn/v1
endpoints:
  - endpoint_id: chat_completions
    method: POST
    path: /v1/chat/completions
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params:
  - requestId or request_id
required_body_fields:
  - model
  - messages
optional_body_fields:
  - stream
  - max_tokens
  - max_completion_tokens
  - reasoning_effort
  - temperature
  - top_p
  - tools
response_pattern: sync_json_or_stream
supports_stream: true
supports_tools: true
supports_multimodal_input: true
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - 明确列出的模型有 Volc-DeepSeek-V3.2、Doubao-Seed-2.0-mini/lite/pro、qwen3.5-plus
  - 思考开关字段按模型不同而不同：部分模型用 thinking.type，qwen3.5-plus 用 enable_thinking
  - 文档提到 Responses API 风格，但快照中没有给出单独的 Responses endpoint
  - 文档提到存在 QPS 限流与单日用量限制错误码 2003，但没有给固定数值
  - 图片理解走 messages[].content[] 结构，不是独立视觉 endpoint
must_read_order: [1677, 1745, 1805]
confidence: high
```

### 7.4 `llm.function_calling`

```yaml
capability_id: llm.function_calling
display_name: Function calling
source_doc_ids: [1805]
supporting_category_doc_ids: [1744, 1720]
integration_pattern: openai_compatible_via_llm_chat
base_url: https://api-ai.vivo.com.cn/v1
endpoints:
  - endpoint_id: chat_completions_tools
    method: POST
    path: /v1/chat/completions
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params:
  - requestId or request_id
required_body_fields:
  - messages
  - tools
optional_body_fields:
  - system prompt with API schema
response_pattern: tool_call_turns
supports_stream: inherited_from_llm_chat
supports_tools: true
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 本页主要定义 messages 结构和 API schema 提示方式，不是独立 endpoint
  - 如果实现 OpenAI 风格 tools，优先以 1745 的 tools 参数为准，再参考本页的 system/message 组织方式
  - 不要直接假设完整原生 tool_calls 生命周期与 OpenAI 完全一致，先以实际返回做适配
must_read_order: [1745, 1805]
confidence: high
```

### 7.5 `image.generation`

```yaml
capability_id: image.generation
display_name: 图片生成
source_doc_ids: [1732]
supporting_category_doc_ids: [1724, 1720]
integration_pattern: custom_sync
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: image_generation
    method: POST
    path: /api/v1/image_generation
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params:
  - module=aigc
  - request_id=<uuid>
  - system_time=<unix_seconds>
required_body_fields:
  - model=Doubao-Seedream-4.5
  - prompt
optional_body_fields:
  - image
  - parameters.size
  - parameters.prompt_extend
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: true
quota_or_competition_limits:
  - daily_limit: 10
    total_limit: 300
failure_signals:
  - code 1003 Rate limit exceeded
  - code 1004 输入/输出内容审核不通过
implementation_gotchas:
  - 快照中只明确支持 image URL，未把 base64 视为已可用能力
  - 响应中的单个 image 字段已标注为即将废弃，读取时应优先使用 images[]
  - 虽然是同步接口，但单图生成时间可明显高于普通 REST，客户端超时建议至少按 60 秒级别考虑
must_read_order: [1677, 1732]
confidence: high
```

### 7.6 `video.generation`

```yaml
capability_id: video.generation
display_name: 视频生成
source_doc_ids: [2201]
supporting_category_doc_ids: [2200, 1720]
integration_pattern: custom_async
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: submit_task
    method: POST
    path: /api/v1/submit_task
  - endpoint_id: query_task
    method: GET
    path: /api/v1/query_task
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params:
  - module=aigc
  - request_id=<uuid>
  - system_time=<unix_seconds>
  - task_id=<query_stage_only>
required_body_fields:
  - model=Doubao-Seedance-1.0-pro
  - content
optional_body_fields: []
response_pattern: submit_then_query
supports_stream: false
supports_tools: false
supports_multimodal_input: true
quota_or_competition_limits:
  - daily_limit: 5
    total_limit: 50
failure_signals:
  - code 1003 Rate limit exceeded
  - code 3002 Task not found
implementation_gotchas:
  - content 同时支持 text、image_url，图生视频可带首帧或首尾帧
  - 成功结果需要从查询任务接口返回的 content.video_url 读取
  - `task_id` 只在查询任务阶段必填；不要把 submit 与 query 的 query 参数完全等同
must_read_order: [1677, 2201]
confidence: high
```

### 7.7 `vision.ocr`

```yaml
capability_id: vision.ocr
display_name: 通用OCR
source_doc_ids: [1737]
supporting_category_doc_ids: [1727, 1720]
integration_pattern: custom_sync
base_url: http://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: general_recognition
    method: POST
    path: /ocr/general_recognition
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
  - Content-Type: application/x-www-form-urlencoded
required_query_params:
  - requestId=<uuid>
required_body_fields:
  - image
  - pos
  - businessid
optional_body_fields: []
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: true
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - image 要求 base64，文档示例偏表单/base64 上传口径，不是 OpenAI 风格
  - host 在快照中写成 http，生产是否支持 https 需落地前再验
  - 补充说明中提到不同 businessid 代表不同 OCR 能力，旋转识别支持可能不同
must_read_order: [1677, 1737]
confidence: medium
```

### 7.8 `nlp.translation`

```yaml
capability_id: nlp.translation
display_name: 文本翻译
source_doc_ids: [1733]
supporting_category_doc_ids: [1728, 1720]
integration_pattern: custom_sync
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: translation_query_self
    method: POST
    path: /translation/query/self
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params: []
required_body_fields:
  - from
  - to
  - text
  - app=test
optional_body_fields: []
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - 文档将 app=test 写为必填，不建议省略
must_read_order: [1677, 1733]
confidence: medium
```

### 7.9 `nlp.embedding`

```yaml
capability_id: nlp.embedding
display_name: 文本向量
source_doc_ids: [1734]
supporting_category_doc_ids: [1728, 1720]
integration_pattern: custom_sync
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: embedding_predict_batch
    method: POST
    path: /embedding-model-api/predict/batch
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params: []
required_body_fields:
  - text list
optional_body_fields: []
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - 文档引用了 bge/m3e 模型背景，但工程接入只应依赖 vivo 返回格式，不要混入第三方模型 wire shape
  - 若用 bge-base-zh-v1.5 做检索，query 前需要补 instruction：为这个句子生成表示以用于检索相关文章
must_read_order: [1677, 1734]
confidence: medium
```

### 7.10 `nlp.similarity`

```yaml
capability_id: nlp.similarity
display_name: 文本相似度
source_doc_ids: [2060]
supporting_category_doc_ids: [1728, 1720]
integration_pattern: custom_sync
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: rerank
    method: POST
    path: /rerank
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params: []
required_body_fields:
  - query
  - sentences
optional_body_fields: []
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - 文档偏 rerank 语义，不要误当通用 embedding 接口
  - 文档说明 query+sentence 总长度不应超过约 500 字
must_read_order: [1677, 2060]
confidence: medium
```

### 7.11 `nlp.query_rewrite`

```yaml
capability_id: nlp.query_rewrite
display_name: 查询改写
source_doc_ids: [2061]
supporting_category_doc_ids: [1728, 1720]
integration_pattern: custom_sync
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: query_rewrite_base
    method: POST
    path: /query_rewrite_base
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params: []
required_body_fields:
  - prompts
optional_body_fields:
  - history context
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - 更适合 RAG / 搜索预处理，不是直接面向最终回答的 LLM endpoint
  - 文档提到最多 3 轮历史，当前 q 长度 <= 50
  - `-8/-9` 更像无需改写信号，不应一律当作系统异常
must_read_order: [1677, 2061]
confidence: medium
```

### 7.12 `asr.realtime_short`

```yaml
capability_id: asr.realtime_short
display_name: 实时短语音识别
source_doc_ids: [1738]
supporting_category_doc_ids: [1725, 1720]
integration_pattern: custom_ws_stream
base_url: ws://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: asr_v2
    method: WS
    path: /asr/v2
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params:
  - user_id
  - package
  - client_version
  - sdk_version
  - android_version
  - system_time
  - requestId
  - engineid
required_body_fields:
  - started text frame
  - binary audio frames
optional_body_fields:
  - asr_info.lang
  - asr_info.punctuation
response_pattern: websocket_handshake_then_binary_stream
supports_stream: true
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 文档强烈面向移动端 SDK 场景，服务端封装前要先决定如何补齐这些设备字段
  - 音频要求 16k/16bit 单声道 PCM
  - 单轮时长按文档口径控制在 60s 内
  - 音频结束发 binary `--end--`，关闭连接发 `--close--`
must_read_order: [1677, 1738]
confidence: medium
```

### 7.13 `asr.long_dictation`

```yaml
capability_id: asr.long_dictation
display_name: 长语音听写
source_doc_ids: [1740]
supporting_category_doc_ids: [1725, 1720]
integration_pattern: custom_ws_stream
base_url: ws://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: asr_v2
    method: WS
    path: /asr/v2
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params:
  - user_id
  - package
  - client_version
  - sdk_version
  - android_version
  - system_time
  - requestId
  - engineid=longasrlisten
required_body_fields:
  - started text frame
  - binary audio frames
optional_body_fields:
  - asr_info.lang
  - asr_info.punctuation
response_pattern: websocket_handshake_then_binary_stream
supports_stream: true
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 文档示例 URL 同时出现测试域名与生产域名，实际接入前需确认可用 host 与 scheme
  - 定位于长音频实时听写，不等同于离线文件转写
  - 返回 code=8 为中间结果，0 为完整结果，9 为最后一句，可据此决定何时断开
must_read_order: [1677, 1740]
confidence: medium
```

### 7.14 `asr.long_transcription`

```yaml
capability_id: asr.long_transcription
display_name: 长语音转写
source_doc_ids: [1739]
supporting_category_doc_ids: [1725, 1720]
integration_pattern: custom_async_multi_step
base_url: http://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: create_audio
    method: POST
    path: /lasr/create
  - endpoint_id: upload_slice
    method: multipart
    path: /lasr/upload
  - endpoint_id: create_task
    method: POST
    path: /lasr/trans
  - endpoint_id: query_progress
    method: GET
    path: /lasr/progress
  - endpoint_id: query_result
    method: GET
    path: /lasr/result
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params:
  - client_version
  - package
  - user_id
  - system_time
  - engineid=fileasrrecorder
  - requestId
required_body_fields:
  - audio metadata
  - x-sessionId
  - slice_num
optional_body_fields: []
response_pattern: create_upload_transcribe_poll
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 这是 5 阶段协议，不要按单次 POST 设计
  - 文档写明单次转写文件限制 5 小时且小于 500M
  - create 与 upload 必须复用同一 `x-sessionId`
  - 单片大小按文档示例控制在 5MB，`slice_num` 不应超过 100
must_read_order: [1677, 1739]
confidence: medium
```

### 7.15 `asr.dialect_free_speech`

```yaml
capability_id: asr.dialect_free_speech
display_name: 方言自由说
source_doc_ids: [2065]
supporting_category_doc_ids: [1725, 1720]
integration_pattern: custom_ws_stream
base_url: ws://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: asr_v2
    method: WS
    path: /asr/v2
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params:
  - user_id
  - package
  - client_version
  - sdk_version
  - android_version
  - system_time
  - engineid=shortasrinput
  - requestId
required_body_fields:
  - started text frame
  - binary audio frames
optional_body_fields:
  - asr_info.lang=dialect
  - asr_info.chinese2digital
  - asr_info.punctuation
response_pattern: websocket_handshake_then_binary_stream
supports_stream: true
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 快照中明确支持济南话、河南话、四川话、武汉话
  - 其余 framing、40ms 分帧、结束控制语义与实时短语音识别一致
must_read_order: [1677, 2065]
confidence: medium
```

### 7.16 `asr.same_voice_interpretation`

```yaml
capability_id: asr.same_voice_interpretation
display_name: 同声音传译
source_doc_ids: [2068]
supporting_category_doc_ids: [1725, 1720]
integration_pattern: custom_ws_stream
base_url: ws://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: asr_v2
    method: WS
    path: /asr/v2
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params:
  - user_id
  - package
  - client_version
  - sdk_version
  - android_version
  - system_time
  - engineid=longasrsubtitle
  - requestId
required_body_fields:
  - started text frame
  - binary audio frames
optional_body_fields:
  - asr_info.target_lang
  - asr_info.tc
  - asr_info.scene
  - asr_info.audio_source
  - asr_info.roletype
  - tts_info.engineid
response_pattern: websocket_handshake_then_binary_stream
supports_stream: true
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - 这是实时 ASR + 翻译复合能力，target_lang 是关键字段
  - 开同传需显式带 `asr_info.tc=1`
  - 文档支持叠加 TTS/同声纹复制相关字段
must_read_order: [1677, 2068]
confidence: medium
```

### 7.17 `tts.audio_generation`

```yaml
capability_id: tts.audio_generation
display_name: 音频生成
source_doc_ids: [1735]
supporting_category_doc_ids: [1726, 1720]
integration_pattern: custom_ws_stream
base_url: wss://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: tts
    method: WSS
    path: /tts
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
required_query_params:
  - engineid
  - system_time
  - user_id
  - model
  - product
  - package
  - client_version
  - system_version
  - sdk_version
  - android_version
  - requestId
required_body_fields:
  - synthesis text payload
optional_body_fields: []
response_pattern: websocket_text_to_pcm_stream
supports_stream: true
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals: []
implementation_gotchas:
  - engineid 决定能力：短音频 `short_audio_synthesis_jovi`，长音频 `long_audio_synthesis_screen`，超拟人 `tts_humanoid_lam`
  - 服务端会周期性回传 PCM 数据，不是一次性返回音频文件
  - 请求 JSON 中还会出现 `vcn`、`aue` 等语音参数
  - 文档标注文本长度无限制
must_read_order: [1677, 1735]
confidence: medium
```

### 7.18 `tts.voice_clone`

```yaml
capability_id: tts.voice_clone
display_name: 声音复刻
source_doc_ids: [2062]
supporting_category_doc_ids: [1726, 1720]
integration_pattern: custom_async
base_url: http://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: create_vcn_task
    method: POST
    path: /replica/create_vcn_task
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Authorization: Bearer AppKey
  - Content-Type: multipart/form-data
required_query_params:
  - req_id / requestId
required_body_fields:
  - audio file
  - text
optional_body_fields: []
response_pattern: task_creation_json
supports_stream: false
supports_tools: false
supports_multimodal_input: true
quota_or_competition_limits: []
failure_signals:
  - error_code != 0
implementation_gotchas:
  - 输入音频要求 24k 采样率、单通道、16bit wav
  - 该能力产出音色 id / engineid，真正合成音频还要结合 `1735 音频生成`
  - URI 参数示例写 `req_id`，表格写 `requestId`，实现前需以联调结果为准
must_read_order: [1677, 2062, 1735]
confidence: medium
```

### 7.19 `lbs.poi_search`

```yaml
capability_id: lbs.poi_search
display_name: 地理编码(POI搜索)
source_doc_ids: [1736]
supporting_category_doc_ids: [1729, 1720]
integration_pattern: custom_sync
base_url: https://api-ai.vivo.com.cn
endpoints:
  - endpoint_id: search_geo
    method: GET
    path: /search/geo
auth_scheme: Authorization: Bearer AppKey
required_headers:
  - Content-Type: application/json
  - Authorization: Bearer AppKey
required_query_params:
  - keywords
  - city
  - requestId
required_body_fields: []
optional_body_fields:
  - page_num
  - page_size
response_pattern: sync_json
supports_stream: false
supports_tools: false
supports_multimodal_input: false
quota_or_competition_limits: []
failure_signals:
  - shared 401 auth failures
implementation_gotchas:
  - page_num 小于 1 按 1 处理，大于 20 按 20 处理
  - page_size 小于 1 按 10 处理，大于 15 按 15 处理
must_read_order: [1677, 1736]
confidence: high
```

## 8. 分类节点判定与无独立正文说明

当前以下 10 个节点统一按“分类节点”处理，而不是“正文抓取遗漏”：

- `1676 文档中心`
- `1720 接口文档`
- `1744 文本生成`
- `1724 图片生成`
- `2200 视频生成`
- `1727 视觉技术`
- `1728 自然语言处理`
- `1725 ASR`
- `1726 TTS`
- `1729 LBS`

判定依据：

- `/vstack/webapi/service/doc/tree` 为这些节点返回了稳定的父子层级关系，且都存在明确子节点
- `/vstack/webapi/service/doc/info/v1` 对这 10 个节点返回 `{"retcode":0,"msg":"success","data":{}}`
- 同一批快照里已经拿到这些分类节点下的正文子页，因此空 `data` 更符合“目录节点无独立正文”而不是“详情抓漏”

落库与检索口径：

- 页面索引中这 10 个节点的 `page_kind` 固定为 `category`
- `content_length` 统一记为 `0`
- 真正可用于实现与摘要抽取的正文内容应以下游 article 子页为准，不直接对分类节点补写伪正文

## 9. KnowLink 落地提示

按 KnowLink 当前产品形态，优先顺序建议如下：

1. `platform.access`
2. `llm.chat`
3. `llm.function_calling`
4. `vision.ocr`
5. `nlp.embedding` / `nlp.query_rewrite`
6. 视演示需要再评估 `image.generation`

不建议在第一轮落地中直接把以下能力纳入 MVP 主链路：

- `video.generation`
- `asr.*`
- `tts.*`
- `tts.voice_clone`

原因：

- 配额限制更强或协议更偏移动端
- 设备参数、WebSocket 时序、音频分片等实现成本明显高于标准 REST
- 当前 KnowLink 骨架更适合先落 OCR + LLM + 检索增强链路

## 10. 风险与待确认项

- `1745` 声称支持 Responses API 风格，但快照中没有单独 endpoint；真正实现时仍以 `/v1/chat/completions` 为主
- 多个 ASR / TTS / OCR 文档使用 `http://` 或 `ws://` 示例，生产环境是否统一支持 `https://` / `wss://` 需要联调再确认
- `1732` 中“预计 4.24 前支持 base64 图片”是 2026-04-21 快照时的未来承诺，不应提前假定已上线
- `1733`、`1734`、`2060`、`2061` 的本文件只保留实现级事实；具体请求字段名在真正接入时仍应二次回看对应原文
- 如果 `/vstack/webapi/service/doc/info/v1` 后续开始为当前 category 节点返回非空 `data`，应先回修页面索引中的 `page_kind`、`content_length` 与 `must_read`，再决定是否扩写能力摘要
