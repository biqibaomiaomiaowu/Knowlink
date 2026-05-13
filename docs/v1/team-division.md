# KnowLink 团队分工与协作方案

本分工文档以策划书《knowlink作品策划文档终稿 (6).docx》为基础，并与 [architecture.md](./architecture.md) 保持一一对应。目标不是只分“谁做前端、谁做后端”，而是让每位队员从开工第一天起就知道：

- 自己负责哪些模块
- 哪些表、接口、页面和任务归自己写
- 哪些内容只能读、不能改
- 什么时候可以并行，什么时候必须等待上游交付

按周排期和每周交付物见 [weekly-plan.md](./weekly-plan.md)。

## 0. 版本适用范围

本文档保留为 KnowLink 第一版（V1）分工与协作边界说明，主要用于解释第一版开发期间的 owner、接口、表结构和联调责任。

KnowLink 第二版（V2）从 2026-05-18 开始按 [docs/v2/phase-plan.md](../v2/phase-plan.md) 推进。V2 的阶段计划、每周任务、负责人分工和验收口径以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准；当本文档中的 V1 owner 口径与 V2 阶段计划冲突时，V2 任务以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为主。

V2 后端分工的核心变化是：

- 曹乐是 V2 后端技术主责与 AI 主责，负责困难后端、AI、解析、B站导入核心、知识图谱、流式输出、主观题判卷和推荐策略。
- 杨彩艺是 V2 后端辅助与用户测试调研主责，只负责边界清楚、低风险、可独立完成的后端辅助任务，包括基础 CRUD、简单 DTO、状态查询、接口文档、测试数据整理、简单接口联调；第三阶段总负责真实用户测试反馈调研。
- 朱春雯仍全权负责前端、Android、页面设计优化和前端联调。

### 0.1 V2 后端分工相关旧口径

以下内容是 V1 期间的后端分工口径，不能直接套用到 V2：

- 第 3 节“FastAPI 路由与服务 | 杨彩艺 | 包括 API、任务入队、聚合状态”：这是 V1 后端骨架和常规接口口径。V2 中涉及 B站下载合并、复杂状态机、图谱、SSE、判卷等困难后端任务时，不再默认由杨彩艺负责。
- 第 3 节“B 站导入预留接口与扫码登录预留接口 | 杨彩艺”：这是 V1 的预留接口和 `501` stub 口径。V2 要做真实登录、下载、合并和课程导入，核心后端由曹乐负责，杨彩艺只做状态查询、简单 DTO、接口文档和测试数据等辅助任务。
- 第 3 节“MinIO / Redis / PostgreSQL 接入 | 杨彩艺”：这是 V1 基础设施 scaffold 和常规运行时口径。V2 中如果涉及 B站导入、流式事件、图谱 read model、主观题判卷结果等复杂链路，主责以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。
- 第 4.3 节“杨彩艺单写”中 `server/api/routers/**`、`server/domain/services/**`、`server/tasks/**`、`server/infra/**` 全部归杨彩艺的表述，是 V1 单写边界。V2 中困难后端任务不按这个旧口径默认分配给杨彩艺。
- 第 5 节中 `course_resources`、`parse_runs`、`async_tasks`、`qa_sessions`、`quizzes`、`user_course_progress`、`vector_documents` 等表归杨彩艺主责的表述，是 V1 数据表 owner 口径。V2 中如果这些表或新表涉及复杂 AI 产物、图谱、流式事件、判卷证据链或 B站导入状态机，按 V2 计划重新分工。
- 第 6.1 节“朱春雯直接对接的接口”中大量接口的“后端负责人”为杨彩艺，是 V1 接口联调口径。V2 新增或重做的接口，以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 中的曹乐主责 / 杨彩艺辅助边界为准。
- 第 6.2 节“B 站导入与扫码登录接口预留”中“接口主负责人是杨彩艺”的表述，只适用于 V1 stub，不适用于 V2 真实 B站导入。
- 第 6.3 节“路径、请求字段、响应字段、错误码实现 | 杨彩艺”和“DTO 由杨彩艺整理”的表述，是 V1 默认接口流程。V2 中复杂后端、AI、图谱、流式、判卷的 contract 和核心逻辑由曹乐主责，杨彩艺只整理曹乐已拆清楚的简单 DTO、状态查询和文档。
- 第 8 节“工作包 B/D/E”中杨彩艺作为后端基础骨架、上传解析链路、讲义生成链路主负责人的描述，是 V1 工作包口径。V2 不沿用这些工作包主责划分。
- 第 11 节“owner 以本文档为准”“后端先改 server/schemas 与实现”等流程，是 V1 流程。V2 任务的 owner 与验收口径以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。

## 1. 分工原则

- 单 owner 原则：每个核心模块、表和接口必须有唯一主负责人；协作、确认和实现职责只写在说明列，不在 owner 列混写。
- 契约优先原则：跨人协作先冻结数据结构和接口，再各自实现。
- 页面和接口对齐原则：Flutter 页面、Provider、DTO、API 路径要在本文件中可一一对应。
- 并行但不重复原则：允许同时开发，但禁止两个人同时写同一层核心逻辑。
- 文档分工口径：`docs/v1/weekly-plan.md` 只安排第一版时间和交付节奏，不改变本文档中的 V1 主负责人定义。V2 主负责人定义以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。

## 2. 团队角色

以下角色说明仅适用于第一版（V1）分工。第二版（V2）角色以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。

### 2.1 曹乐

角色：

- 队长
- 产品统筹
- AIGC 方案 owner
- 数据库设计 owner
- OCR / 文档解析策略 owner

对应策划书职责：

- 核心产品链路定义
- 讲义生成、问答、测验生成与复习推荐策略
- 数据库结构设计
- 教材、PPT、PDF、题库解析与保真策略
- 比赛材料与整体推进

### 2.2 朱春雯

角色：

- 移动端开发 owner
- UI / 页面体验 owner

对应策划书职责：

- 页面设计与前端实现
- 移动端交互呈现
- 播放器与讲义联动
- vivo 手机展示效果保障

### 2.3 杨彩艺

角色：

- 后端开发 owner
- 服务部署与联调 owner

对应策划书职责：

- 服务端架构与接口实现
- 文件上传、任务调度、请求处理
- 数据读写接口与检索接口
- 接口稳定性、部署与运行保障

## 3. 模块 owner 对照表

以下表格是第一版（V1）模块 owner 对照表。V2 中 B站真实导入、复杂知识图谱、实时流式输出、主观题判卷和复杂后端任务不沿用本表中的杨彩艺主责口径，按 [docs/v2/phase-plan.md](../v2/phase-plan.md) 执行。

| 模块 | 主负责人 | 协作人 | 说明 |
|---|---|---|---|
| 产品流程、状态机、页面链路 | 曹乐 | 全员 | 以 `docs/v1/architecture.md` 为准 |
| Flutter 页面与交互 | 朱春雯 | 曹乐 | 包括页面布局、主题、路由、Provider 绑定 |
| FastAPI 路由与服务 | 杨彩艺 | 曹乐 | 包括 API、任务入队、聚合状态 |
| `course_catalog` 与推荐契约 | 曹乐 | 杨彩艺 | 目录语义、推荐字段和确认入课流程 |
| B 站导入预留接口与扫码登录预留接口 | 杨彩艺 | 曹乐 | V1 stub 接口主负责人是杨彩艺；第 1 周由曹乐冻结业务 contract、状态语义和错误码，第 2 周由杨彩艺按冻结结果补当前 `501` stub；V2 真实 B站导入以 `docs/v2/phase-plan.md` 为准 |
| AIGC Prompt、赛方 AI 能力业务适配与生成策略 | 曹乐 | 杨彩艺 | 曹乐负责 `server/ai/**`、`server/parsers/**` 内 OCR / ASR / LLM / Embedding 等能力的业务输入输出、prompt、AI 输出 JSON Schema / parse schema、降级和产物策略，不包含 `server/schemas/**` API DTO；杨彩艺负责服务接入与运行时接线 |
| OCR / ASR / 文档解析与结构化策略 | 曹乐 | 杨彩艺 | 解析规则、输出结构和解析侧产物归一化由曹乐主导 |
| 数据库与数据关系 | 曹乐 | 杨彩艺 | 数据关系、业务语义与状态边界由曹乐定义，落库实现由杨彩艺完成 |
| MinIO / Redis / PostgreSQL 接入 | 杨彩艺 | 曹乐 | 第 1 周只完成配置、本地编排、基础迁移和 scaffold；真实读写、持久化仓储与任务链路进入第 2 周实现 |
| 演示内容、比赛材料 | 曹乐 | 全员 | 页面截图、讲解顺序、答辩稿统一管理 |

## 4. 单写 owner 边界

本节是第一版（V1）单写边界。V2 任务若涉及 `server/api/**`、`server/domain/**`、`server/tasks/**`、`server/infra/**` 等困难后端链路，先看 [docs/v2/phase-plan.md](../v2/phase-plan.md) 的曹乐主责 / 杨彩艺辅助边界。

### 4.1 曹乐单写

只允许曹乐主写的内容：

- `server/ai/**`
- `server/parsers/**`
- 赛方 AI 能力在 `server/ai/**` 与 `server/parsers/**` 内的业务适配、输入输出映射、prompt、AI 输出 JSON Schema / parse schema、错误降级、结果校验和产物归一化策略，不包含 `server/schemas/**` API DTO
- `courses`、`learning_preferences`、`handout_versions`、`knowledge_points`、`mastery_records`、`review_task_runs` 的业务字段语义设计
- `parse_runs`、`async_tasks`、`quizzes` 的状态语义与业务边界确认
- 所有 AI 输出 JSON Schema
- B 站单视频导入接口预留 contract、扫码登录接口预留 contract、`bilibili_import_run` 状态语义
- 讲义生成策略、问答策略、测验生成策略、复习推荐策略
- OCR / PDF / PPTX / DOCX 解析后的结构规范
- 引用模型与保真策略
- 比赛文档、演示脚本、产品流程说明

协作方式：

- 如果杨彩艺在实现时发现字段不够，先提 schema 变更，不直接改定义。
- 如果朱春雯在页面上发现状态不足，先提 DTO 补充，不直接改核心业务含义。

### 4.2 朱春雯单写

只允许朱春雯主写的内容：

- `client_flutter/lib/features/**`
- `client_flutter/lib/app/**`
- `client_flutter/lib/core/config/**`
- `client_flutter/lib/core/network/**`
- `client_flutter/lib/core/widgets/**`
- `client_flutter/lib/shared/models/**`
- `client_flutter/lib/shared/providers/**`
- 页面 UI、路由、主题、状态展示、交互动效
- 页面级 mock 数据和交互占位

朱春雯只读不写的内容：

- 后端真实业务逻辑
- 数据库迁移
- AI prompt 与检索逻辑

### 4.3 杨彩艺单写

以下仅适用于第一版（V1）常规后端与运行时任务；V2 困难后端任务不按本小节默认分配给杨彩艺。

只允许杨彩艺主写的内容：

- `server/api/routers/**`
- `server/domain/services/**`
- `server/domain/repositories/**`
- `server/schemas/**`
- `server/tasks/**`
- `server/infra/**`
- 上传、任务调度、缓存、对象存储、部署、日志、监控

杨彩艺只读不写的内容：

- Flutter 页面布局与视觉规范
- `server/ai/**` 与 `server/parsers/**` 内的 AI 策略定义、赛方 AI 能力业务适配和解析 / 生成产物策略；不限制其负责运行时接线、任务调度、仓储 / DB、配置注入和 API 错误返回
- 核心表设计的业务含义

## 5. 数据表 owner 对照

以下数据表 owner 是第一版（V1）口径。V2 若围绕这些表新增 B站导入状态机、图谱 read model、流式事件、主观题判卷证据链或复杂 AI 产物，按 [docs/v2/phase-plan.md](../v2/phase-plan.md) 重新确认主责。

| 表/实体 | 主负责人 | 说明 |
|---|---|---|
| `users` `courses` `course_catalog` | 曹乐 | 业务语义由产品侧定义 |
| `course_resources` | 杨彩艺 | 上传、校验、对象存储回调主导 |
| `parse_runs` `async_tasks` | 杨彩艺 | 任务系统与运行状态主导 |
| `course_segments` `knowledge_points` `segment_knowledge_points` `knowledge_point_evidences` | 曹乐 | 解析结果结构和知识点关系主导 |
| `learning_preferences` | 曹乐 | 问询字段语义由产品/AIGC 主导 |
| `handout_versions` `handout_blocks` `handout_block_knowledge_points` | 曹乐 | 讲义结构主导 |
| `handout_block_refs` `qa_message_refs` `quiz_question_refs` `review_task_refs` | 曹乐 | 引用规范主导，写入时机见第 7 节 |
| `qa_sessions` `qa_messages` | 杨彩艺 | 会话落库和接口主导，内容结构与引用规则由曹乐定义 |
| `quizzes` `quiz_questions` `quiz_attempts` `quiz_attempt_items` | 杨彩艺 | 服务和判分主导，题目结构由曹乐定义 |
| `mastery_records` `review_task_runs` `review_tasks` | 曹乐 | 评分到掌握度、复习规则由曹乐定义，后端实现由杨彩艺完成 |
| `user_course_progress` | 杨彩艺 | 展示字段由朱春雯确认，后端负责落库与接口 |
| `vector_documents` | 杨彩艺 | 投影规则由曹乐确认，写入流程与检索实现由后端负责 |

## 6. API 与页面对应关系

以下 API 与页面对应关系是第一版（V1）联调口径。V2 新增或重做接口，尤其是 B站真实导入、知识图谱、SSE/流式输出和主观题判卷，按 [docs/v2/phase-plan.md](../v2/phase-plan.md) 的责任边界重新拆分。

### 6.1 朱春雯直接对接的接口

| 页面/Provider | 接口 | 后端负责人 |
|---|---|---|
| `HomePage` `courseFlowProvider` | `GET /api/v1/home/dashboard` | 杨彩艺 |
| `CourseRecommendPage` `courseRecommendProvider` | `POST /api/v1/recommendations/courses` | 杨彩艺 |
| `CourseRecommendPage` `courseRecommendProvider` | `POST /api/v1/recommendations/{catalogId}/confirm` | 杨彩艺 |
| `CourseImportPage` | `POST /api/v1/courses` | 杨彩艺 |
| `CourseImportPage` | `POST /api/v1/courses/{courseId}/resources/upload-init` | 杨彩艺 |
| `CourseImportPage` | `POST /api/v1/courses/{courseId}/resources/upload-complete` | 杨彩艺 |
| `CourseImportPage` | `GET /api/v1/courses/{courseId}/resources` | 杨彩艺 |
| `CourseImportPage` | `DELETE /api/v1/courses/{courseId}/resources/{resourceId}` | 杨彩艺 |
| `ParseProgressPage` `courseFlowProvider` | `POST /api/v1/courses/{courseId}/parse/start` | 杨彩艺 |
| `ParseProgressPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/pipeline-status` | 杨彩艺 |
| `InquiryPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/inquiry/questions` | 杨彩艺 |
| `InquiryPage` `courseFlowProvider` | `POST /api/v1/courses/{courseId}/inquiry/answers` | 杨彩艺 |
| `HandoutPage` `courseFlowProvider` | `POST /api/v1/courses/{courseId}/handouts/generate` | 杨彩艺 |
| `HandoutPage` `courseFlowProvider` | `GET /api/v1/handout-versions/{handoutVersionId}/status` | 杨彩艺 |
| `HandoutPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/handouts/latest` | 杨彩艺 |
| `HandoutPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/handouts/latest/outline` | 杨彩艺 |
| `HandoutPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/handouts/latest/blocks` | 杨彩艺 |
| `HandoutPage` `activeBlockProvider` | `POST /api/v1/handout-blocks/{blockId}/generate` | 杨彩艺 |
| `HandoutPage` `activeBlockProvider` | `GET /api/v1/handout-blocks/{blockId}/status` | 杨彩艺 |
| `HandoutPage` `activeBlockProvider` | `GET /api/v1/courses/{courseId}/handouts/current-block` | 杨彩艺 |
| `HandoutPage` `activeBlockProvider` | `GET /api/v1/handout-blocks/{blockId}/jump-target` | 杨彩艺 |
| `HandoutPage` `activeBlockProvider` | `GET /api/v1/course-resources/{resourceId}/playback` | 杨彩艺 |
| `QaPage` `courseFlowProvider` | `POST /api/v1/qa/messages` | 杨彩艺 |
| `QaPage` `courseFlowProvider` | `GET /api/v1/qa/sessions/{sessionId}/messages` | 杨彩艺 |
| `QuizPage` `courseFlowProvider` | `POST /api/v1/courses/{courseId}/quizzes/generate` | 杨彩艺 |
| `QuizPage` `courseFlowProvider` | `GET /api/v1/quizzes/{quizId}` | 杨彩艺 |
| `QuizPage` `courseFlowProvider` | `GET /api/v1/quizzes/{quizId}/status` | 杨彩艺 |
| `QuizPage` `courseFlowProvider` | `POST /api/v1/quizzes/{quizId}/attempts` | 杨彩艺 |
| `ReviewPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/review-tasks` | 杨彩艺 |
| `ReviewPage` `courseFlowProvider` | `POST /api/v1/courses/{courseId}/review-tasks/regenerate` | 杨彩艺 |
| `ReviewPage` `courseFlowProvider` | `GET /api/v1/review-task-runs/{reviewTaskRunId}/status` | 杨彩艺 |
| `ReviewPage` `courseFlowProvider` | `POST /api/v1/review-tasks/{reviewTaskId}/complete` | 杨彩艺 |
| `ReviewPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/progress` | 杨彩艺 |
| `ReviewPage` `courseFlowProvider` | `POST /api/v1/courses/{courseId}/progress` | 杨彩艺 |

### 6.2 辅助接口与使用约束

| 场景 | 接口 | 主负责人 | 约束 |
|---|---|---|---|
| `ParseProgressPage` 辅助展示 | `GET /api/v1/courses/{courseId}/parse/summary` | 杨彩艺 | 可展示摘要，但不能替代 `pipeline-status` 作为主轮询接口 |
| 运维 / 调试 | `POST /api/v1/async-tasks/{taskId}/retry` | 杨彩艺 | 仅后端或演示排障使用，朱春雯不直接依赖 |
| `QaPage` 独立会话页 | `/courses/:courseId/qa/:sessionId` | 朱春雯 | 这是独立 QA 会话页；最终讲义页内嵌 QA 也复用同一后端会话 contract |
| B 站导入与扫码登录接口预留 | `/api/v1/courses/{courseId}/resources/imports/bilibili`、`/api/v1/bilibili-import-runs/{importRunId}/status`、`/api/v1/bilibili/auth/qr/sessions` 等 | 杨彩艺 | V1 stub 接口主负责人是杨彩艺；业务 contract、状态语义和 `bilibili.not_implemented` 错误码由曹乐第 1 周冻结，第 2 周由杨彩艺落地 `501` stub，不作为朱春雯的真实联调入口；V2 真实 B站导入以 `docs/v2/phase-plan.md` 为准 |

### 6.3 接口 contract 责任链

| 环节 | 负责人 | 说明 |
|---|---|---|
| 路径、请求字段、响应字段、错误码实现 | 杨彩艺 | 负责接口文档初稿、DTO 落地和后端实现 |
| 字段业务含义、状态枚举、AI 输出结构确认 | 曹乐 | 负责业务语义、状态枚举和 AI / parse 结构冻结 |
| 页面展示字段和交互期望确认 | 朱春雯 | 负责页面消费字段、交互期望和展示约束确认 |

规则：

- DTO 由杨彩艺整理为接口文档初稿。
- 业务字段含义由曹乐确认。
- 页面消费字段由朱春雯确认后冻结。
- 带路径参数的课程接口一律以 path 中的 `courseId` 为准，请求体不重复传同义字段；当前唯一保留请求体 `courseId` 的场景是 `POST /api/v1/qa/messages`。
- V1 B 站导入路径、扫码登录状态字段和 `bilibili.not_implemented` 错误码语义由曹乐先冻结，V1 stub 接通前不允许前后端各自扩写。
- V1 B 站预留接口对应的 `server/api/routers/**`、`server/domain/services/**`、`server/schemas/**` stub 落地由杨彩艺负责，但不得偏离曹乐冻结的业务 contract。V2 真实 B站导入以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。

## 7. 引用表唯一写入入口

| 引用表 | 只能由谁写 | 写入时机 |
|---|---|---|
| `handout_block_refs` | Handout 生成流程 | 讲义块生成并完成引用反查后写入 |
| `qa_message_refs` | QA 服务 | AI 回答生成并完成引用反查后写入 |
| `quiz_question_refs` | Quiz 生成流程 | 题目生成完成后写入 |
| `review_task_refs` | Review 生成流程 | 复习任务生成完成后写入 |

规则：

- 朱春雯不直接写任何引用表。
- 杨彩艺负责引用表落库实现，但不能改变引用字段语义。
- 曹乐负责定义“哪些场景必须写引用、哪些场景允许无引用”。

## 8. 并行开发顺序

本节描述第一版（V1）开发顺序和工作包，不作为 V2 阶段计划使用。V2 阶段、周计划和验收以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。

## 8.1 第 0 步：先冻结契约

负责人：

- 曹乐
- 杨彩艺
- 朱春雯

必须先冻结：

- 关键表业务语义与状态边界
- 核心状态枚举
- 关键接口路径与 DTO
- 讲义块、问答、测验、复习任务的响应结构

完成标志：

- `docs/v1/architecture.md` 不再改核心命名
- 本文档确认 owner 边界

## 8.2 第 1 步：可并行启动的工作包

### 工作包 A：Flutter 页面骨架

负责人：朱春雯

内容：

- 首页
- 自主导入页
- 智能推荐页
- 解析进度页
- 问询页
- 讲义页
- 测验页
- 复习页

依赖：

- 只依赖冻结后的接口 DTO 和页面字段，不依赖真实后端完成

交付物：

- 路由
- 页面壳子
- Provider 壳子
- 推荐页真实 DTO

### 工作包 B：后端基础骨架

负责人：杨彩艺

内容：

- FastAPI 工程
- 路由文件
- 基础响应封装
- PostgreSQL / Redis / MinIO / Worker 的配置、本地编排与基础迁移 scaffold
- `async_tasks` 根任务/子任务模型、任务 payload 与 worker / scheduler 占位
- demo 用户鉴权与 `course_catalog` seed 装载

依赖：

- 只依赖冻结后的业务语义、状态边界与接口定义

交付物：

- 可启动服务
- 健康检查
- 基础表迁移
- 空实现路由
- 基础设施与 `async_tasks` 当前只按第 1 周 scaffold 验收；真实运行时和状态流转进入第 2 周

### 工作包 C：AI / 解析 / 数据契约

负责人：曹乐

内容：

- OCR / 文档解析输出规范
- 知识点抽取结构
- 讲义块 JSON Schema
- 问答返回结构
- 测验题结构
- 复习任务结构

依赖：

- 不依赖后端代码完成

交付物：

- JSON Schema
- Prompt 输入输出规范
- 解析结果字段说明

## 8.3 第 2 步：必须按依赖解锁的工作包

### 工作包 D：上传与解析链路

主负责人：杨彩艺  
协作：曹乐

前置：

- `course_resources`
- `parse_runs`
- `async_tasks`
- 解析输出结构冻结

协作边界：

- 曹乐负责 `server/ai/**` 与 `server/parsers/**` 内的 parser 内核、赛方 AI 能力业务适配、prompt、AI 输出 JSON Schema / parse schema、解析与生成产物策略。
- 杨彩艺负责 FastAPI router / service、worker 调度、provider 运行时接线、配置注入、仓储落库、状态聚合和稳定性。

解锁后续：

- 解析进度页联调
- 问询页真实数据接入

### 工作包 E：讲义生成链路

主负责人：杨彩艺  
协作：曹乐

前置：

- `learning_preferences`
- `handout_versions`
- `handout_blocks`
- `handout_block_refs`
- 讲义块 JSON Schema

解锁后续：

- 讲义页真实联调
- 块级问答接入
- 跳转视频/页码联动

### 工作包 F：测验与复习链路

主负责人：杨彩艺  
协作：曹乐

前置：

- `quizzes`
- `quiz_questions`
- `quiz_attempts`
- `mastery_records`
- `review_task_runs`
- `review_tasks`

解锁后续：

- 测验结果页
- 复习推荐页
- 首页推荐卡联动

## 9. 前后端联调顺序

1. 先联调导入与解析进度。
2. 再联调问询与讲义生成。
3. 再联调讲义阅读、跳转和问答。
4. 再联调测验提交与结果。
5. 最后联调复习推荐、首页聚合和最近学习恢复。

规则：

- 没有上游稳定 DTO，不进入真实联调。
- 联调时一律使用固定测试课程和固定资料集。
- 每完成一条链路，立即录屏并记录问题。

## 10. 每个人的直接交付物

以下直接交付物是第一版（V1）口径。V2 中曹乐承担困难后端和 AI 主责，杨彩艺承担后端辅助与用户测试调研主责，朱春雯全权负责前端、Android 和页面优化。

### 10.1 曹乐

- 架构文档与分工文档
- 核心表业务语义与状态边界
- `course_catalog` 与推荐字段语义
- 解析输出规范
- AIGC 输入输出 Schema
- 演示脚本和答辩材料

### 10.2 朱春雯

- Flutter 页面
- 页面路由与 Provider
- 页面交互和视觉表现
- vivo 手机演示稳定性

### 10.3 杨彩艺

- FastAPI 服务
- 推荐接口与确认入课接口
- 上传、解析、讲义、问答、测验、复习接口
- 异步任务系统
- 数据库落库与部署脚本

## 11. Schema / Contract 变更流程

1. 先确认任务版本：V1 的接口路径、DTO、错误码以 `docs/contracts/api-contract.md` 为准；V1 的领域语义和状态模型以 `docs/v1/architecture.md` 为准；V1 owner 以本文件为准。V2 的阶段任务、owner 和验收口径以 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准，若与本文档 V1 口径冲突，以 V2 计划为准。
2. 由提出变更的人先改文档：接口字段改 `docs/contracts/api-contract.md`，状态或领域语义改 `docs/v1/architecture.md`，owner 或协作边界改本文件。
3. 文档冻结后再改代码：后端先改 `server/schemas/**` 与实现，Flutter 再按冻结后的 DTO 对齐页面消费。
4. 所有 schema / contract 变更都要补测试：至少覆盖 `server/tests/test_contract_freeze.py`、`server/tests/test_scaffold_consistency.py` 或对应 Flutter 最小契约测试。
5. 若实现发现字段不够，先提文档变更，不允许前后端私自扩写或改义。

## 12. 文档优先级矩阵

| 文档 | 优先级 | 用途 |
|---|---|---|
| `docs/v2/phase-plan.md` | P0 | 第二版阶段计划、每周任务、负责人分工和验收口径 |
| `docs/contracts/api-contract.md` | P0 | 接口路径、请求字段、响应字段、错误码、DTO |
| `docs/v1/architecture.md` | P0 | 第一版状态模型、目录边界、领域语义、主链路设计 |
| `docs/v1/team-division.md` | P1 | 第一版 owner、协作边界、变更流程 |
| `docs/contracts/week1-cao-le-freeze.md` | P1 | 曹乐冻结的业务语义、推荐规则、demo 基线 |
| `docs/engineering/development-scaffold.md` | P1 | 当前完成度、已接通与未接通范围 |
| `docs/v1/weekly-plan.md` | P2 | 排期、阶段目标与每周交付物 |

## 13. 冲突处理规则

以下规则仅适用于第一版（V1）协作。V2 任务若涉及困难后端、AI、B站导入、图谱、SSE/流式或主观题判卷，先按 [docs/v2/phase-plan.md](../v2/phase-plan.md) 确认主责。

- 需要改表结构或状态语义：先找曹乐确认业务含义，再由杨彩艺落到接口和存储实现。
- 需要改接口响应：先找杨彩艺，曹乐确认业务语义，朱春雯确认页面消费。
- 需要改页面字段：先找朱春雯，若涉及接口新增字段，再走第 11 节变更流程。
- 需要改 AIGC 输出格式：先找曹乐，不允许后端或前端私自扩展。

## 14. 开工前检查清单

- `docs/v1/architecture.md` 中表名、接口名、状态名已冻结
- 本文档中的 owner 没有重叠冲突
- 每个页面都能找到对应接口
- 每个生成型实体都能找到对应状态接口
- 每张引用表都能找到唯一写入入口
- 每位成员都明确自己本周的交付物

做到以上几点后，队员可以按本文档直接分工开做，且页面、接口、数据结构和 AI 输出能完全对得上。
