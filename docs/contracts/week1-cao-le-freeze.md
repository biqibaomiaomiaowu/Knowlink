# 曹乐 Week 1 冻结稿

本文件是曹乐在第 1 周的 owner 交付验收入口，用于把已经分散在架构、接口 contract、schema 和种子数据中的冻结项收成一份可核对清单。

- 适用时间：2026-04-20 至 2026-04-26
- 适用范围：只覆盖曹乐 owner 的业务语义、状态枚举、AI/解析 contract、推荐规则和 demo 基线
- 不包含：migration 落表、FastAPI router/service 实现、Flutter 页面接线

## 1. 核心表语义

| 实体 | Week 1 冻结语义 |
|---|---|
| `courses` | 用户课程主表；冻结 `lifecycle_status`、`pipeline_stage`、`pipeline_status`、`active_parse_run_id` 的业务含义 |
| `course_resources` | 课程资源表；每个上传源文件一条记录，资料类型只允许 `mp4` `pdf` `pptx` `docx` `srt` |
| `parse_runs` | 解析版本线；每次重解析都创建新版本，只有 `succeeded` 的 run 才能切到生效版本 |
| `async_tasks` | 异步根任务/子任务共用表；前端轮询和实体生成状态都只认这套状态模型 |
| `learning_preferences` | 问询结果快照；冻结目标类型、基础水平、时间预算、讲义风格、解释密度等学习偏好语义 |
| `handout_versions` | 讲义版本表；每次重生成创建新版本，讲义块和引用都从属于具体版本 |
| `quizzes` | 测验版本入口；题目结构由 AI schema 定义，后端实现不得自行扩写题型字段 |
| `review_task_runs` | 复习重算版本入口；重算原因、生成数量和状态语义先冻结，再由后端落库实现 |

字段全集与索引仍以 [ARCHITECTURE.md](../../ARCHITECTURE.md) 第 10 节为准；本文件只负责冻结业务含义和验收口径。

## 2. 核心状态枚举

- `lifecycle_status`: `draft` `resource_ready` `inquiry_ready` `learning_ready` `archived` `failed`
- `pipeline_stage`: `idle` `upload` `parse` `inquiry` `handout`
- `pipeline_status`: `idle` `queued` `running` `partial_success` `succeeded` `failed`
- `async_tasks.status`: `queued` `running` `succeeded` `failed` `retrying` `canceled` `skipped`

状态语义补充：

- `draft`：课程已创建，但还未满足最低可解析资源条件
- `resource_ready`：资源已满足最低可解析条件，可进入解析
- `inquiry_ready`：解析结果已可支撑问询
- `learning_ready`：讲义版本已 ready，可进入学习闭环
- `partial_success`：允许部分资料成功、部分资料失败，但课程仍可继续往下游推进

## 3. 推荐契约冻结

- 推荐输入字段固定为 `goalText`、`selfLevel`、`timeBudgetMinutes`、`examAt`、`preferredStyle`
- 推荐输出字段至少固定为 `catalogId`、`title`、`provider`、`estimatedHours`、`fitScore`、`reasons[]`、`defaultResourceManifest`
- 排序规则固定为 `fitScore` 降序；若 `fitScore` 相同，保持 `server/seeds/course_catalog.json` 的种子顺序
- `course_catalog` 的 authoritative 数据源固定为 [server/seeds/course_catalog.json](../../server/seeds/course_catalog.json)

Week 1 允许出现的推荐理由文案只有以下 6 条：

- `难度与当前基础匹配`
- `难度可控，适合作为过渡课程`
- `时长可在当前预算内完成`
- `需要拆分学习节奏，但仍可安排`
- `目标关键词与课程主题高度一致`
- `讲义风格与当前偏好一致`

## 4. AI 与解析 Contract

冻结的 schema 文件：

- [schemas/ai/handout_blocks.schema.json](../../schemas/ai/handout_blocks.schema.json)
- [schemas/ai/qa_response.schema.json](../../schemas/ai/qa_response.schema.json)
- [schemas/ai/quiz_generation.schema.json](../../schemas/ai/quiz_generation.schema.json)
- [schemas/ai/review_tasks.schema.json](../../schemas/ai/review_tasks.schema.json)
- [schemas/parse/normalized_document.schema.json](../../schemas/parse/normalized_document.schema.json)

冻结的引用语义：

- `pageNo` 只用于 PDF
- `slideNo` 只用于 PPTX
- `anchorKey` 只用于 DOCX
- `startSec` / `endSec` 只用于视频时间定位
- 每条 citation 必须且只能带一组合法定位字段：`pageNo` / `slideNo` / `anchorKey` / `startSec+endSec`
- 每条 normalized segment 必须且只能带与 `resourceType` 匹配的定位字段
- 不为 `docx` 伪造页码，不把引用位置混写成单一字符串

## 5. Demo 鉴权与课程标题

- demo token 环境变量名固定为 `KNOWLINK_DEMO_TOKEN`
- 推荐演示课程标题固定来自当前 seed：
  - `高等数学期末冲刺`
  - `考研数学基础巩固`
  - `线性代数高频题型课`
- 手动导入联调课程标题固定为 `KnowLink 固定联调课`

## 6. 固定联调资料集

固定资料集规范见 [../demo-assets-baseline.md](../demo-assets-baseline.md)。

- 每周联调默认使用 `1 mp4 + 1 pdf + 1 pptx + 1 docx`
- `srt` 是可选辅助输入，不单独构成联调通过条件
- 仓库内只维护清单、命名规则、MIME 和 checksum 规范，不提交二进制样例
- 当前首版资料集的项目内本地副本放在 `local_assets/first-edition/what-is-set/`，并由 `server/seeds/demo_assets_manifest.json` 记录映射关系
- 虽然推荐目录中的 `pptx/docx` 可标为可选资源，但固定联调资料集必须包含它们，用于覆盖 mixed citation 场景

## 7. Week 1 验收口径

- 架构文档、API contract、schema、seed 数据中的命名和状态枚举互相对得上
- 推荐页不依赖 mock；`fitScore`、`reasons[]`、`defaultResourceManifest` 有明确冻结规则
- AI / parse schema 已能表达 PDF / PPTX / DOCX / 视频四类定位信息
- demo token、联调课程标题、固定资料集命名规则已写成文档，后续联调不再口头约定

## 8. 第 1 周接口预留 / 第 2 周预留实现（曹乐 contract owner，杨彩艺实现 owner）

- 以下内容在第 1 周先完成接口与错误码预留，在第 2 周完成 stub 实现。
- 第 1 周验收范围只包含路径、命名、错误码和状态语义冻结，不要求接口已可访问；实现 owner 以 TEAM_DIVISION/WEEKLY_PLAN 的杨彩艺为准。
- B 站单视频导入接口和扫码登录接口由杨彩艺在第 2 周完成 stub 实现，并沿用第 1 周已冻结的 contract。
- 当前仅预留以下路径，不接通真实下载实现：
  - `POST /api/v1/courses/{courseId}/resources/imports/bilibili`
  - `GET /api/v1/courses/{courseId}/resources/imports/bilibili`
  - `GET /api/v1/bilibili-import-runs/{importRunId}/status`
  - `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`
  - `POST /api/v1/bilibili/auth/qr/sessions`
  - `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`
  - `GET /api/v1/bilibili/auth/session`
  - `DELETE /api/v1/bilibili/auth/session`
- 当前统一错误码为 `bilibili.not_implemented`，用于明确表达“contract 已冻结、能力未接通”。
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili` 在 stub 阶段也统一走该 `501` 契约，不因 body 校验差异返回 `422`，但 OpenAPI 中仍保留 `videoUrl` 字段。
