# KnowLink 团队分工与协作方案

本分工文档以策划书《knowlink作品策划文档终稿 (6).docx》为基础，并与 [ARCHITECTURE.md](./ARCHITECTURE.md) 保持一一对应。目标不是只分“谁做前端、谁做后端”，而是让每位队员从开工第一天起就知道：

- 自己负责哪些模块
- 哪些表、接口、页面和任务归自己写
- 哪些内容只能读、不能改
- 什么时候可以并行，什么时候必须等待上游交付

按周排期和每周交付物见 [WEEKLY_PLAN.md](./WEEKLY_PLAN.md)。

## 1. 分工原则

- 单写 owner 原则：每个核心模块、表和接口必须有唯一主负责人。
- 契约优先原则：跨人协作先冻结数据结构和接口，再各自实现。
- 页面和接口对齐原则：Flutter 页面、Provider、DTO、API 路径要在本文件中可一一对应。
- 并行但不重复原则：允许同时开发，但禁止两个人同时写同一层核心逻辑。

## 2. 团队角色

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

| 模块 | 主负责人 | 协作人 | 说明 |
|---|---|---|---|
| 产品流程、状态机、页面链路 | 曹乐 | 全员 | 以 `ARCHITECTURE.md` 为准 |
| Flutter 页面与交互 | 朱春雯 | 曹乐 | 包括页面布局、主题、路由、Provider 绑定 |
| FastAPI 路由与服务 | 杨彩艺 | 曹乐 | 包括 API、任务入队、聚合状态 |
| `course_catalog` 与推荐契约 | 曹乐 | 杨彩艺 | 目录语义、推荐字段和确认入课流程 |
| B 站导入预留接口与扫码登录预留接口 | 曹乐 | 杨彩艺 | 第 1 周由曹乐冻结路径、状态语义、错误码和 DTO，第 2 周由曹乐补当前 `501` stub 实现，真实下载服务接入再由杨彩艺实现 |
| AIGC Prompt 与生成策略 | 曹乐 | 杨彩艺 | 由曹乐定义策略，杨彩艺负责服务接入 |
| OCR / 文档解析与结构化策略 | 曹乐 | 杨彩艺 | 解析规则和输出结构由曹乐主导 |
| 数据库与数据关系 | 曹乐 | 杨彩艺 | 表结构由曹乐定，落库实现由杨彩艺完成 |
| MinIO / Redis / PostgreSQL 接入 | 杨彩艺 | 曹乐 | 基础设施落地与任务链路实现 |
| 演示内容、比赛材料 | 曹乐 | 全员 | 页面截图、讲解顺序、答辩稿统一管理 |

## 4. 单写 owner 边界

### 4.1 曹乐单写

只允许曹乐主写的内容：

- `server/ai/**`
- `server/parsers/**`
- `courses`、`parse_runs`、`handout_versions`、`knowledge_points`、`mastery_records`、`review_task_runs` 的字段设计
- 所有 AI 输出 JSON Schema
- B 站单视频导入接口预留 contract、第 2 周 stub 实现、扫码登录接口预留 contract、第 2 周 stub 实现、`bilibili_import_run` 状态语义
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
- AI 策略定义
- 核心表设计的业务含义

## 5. 数据表 owner 对照

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
| `user_course_progress` | 朱春雯定义展示需求，杨彩艺实现 | 前端决定需要恢复什么，后端负责落库 |
| `vector_documents` | 曹乐定义投影规则，杨彩艺实现 | 检索投影字段与写入流程协同完成 |

## 6. API 与页面对应关系

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
| `HandoutPage` `courseFlowProvider` | `GET /api/v1/courses/{courseId}/handouts/latest/blocks` | 杨彩艺 |
| `HandoutPage` `activeBlockProvider` | `GET /api/v1/handout-blocks/{blockId}/jump-target` | 杨彩艺 |
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
| B 站导入与扫码登录接口预留 | `/api/v1/courses/{courseId}/resources/imports/bilibili`、`/api/v1/bilibili-import-runs/{importRunId}/status`、`/api/v1/bilibili/auth/qr/sessions` 等 | 曹乐 | 第 1 周先冻结 contract，第 2 周由曹乐完成接口预留实现，当前统一返回 `501`，不作为朱春雯的真实联调入口 |

### 6.3 接口 contract owner

| 接口层面 | 主负责人 |
|---|---|
| 路径、请求字段、响应字段、错误码实现 | 杨彩艺 |
| 字段业务含义、状态枚举、AI 输出结构 | 曹乐 |
| 页面展示字段和交互期望 | 朱春雯 |

规则：

- DTO 由杨彩艺整理为接口文档初稿。
- 业务字段含义由曹乐确认。
- 页面消费字段由朱春雯确认后冻结。
- 带路径参数的课程接口一律以 path 中的 `courseId` 为准，请求体不重复传同义字段；当前唯一保留请求体 `courseId` 的场景是 `POST /api/v1/qa/messages`。
- B 站导入路径、扫码登录状态字段和 `bilibili.not_implemented` 错误码语义由曹乐先冻结，接通前不允许前后端各自扩写。

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

## 8.1 第 0 步：先冻结契约

负责人：

- 曹乐
- 杨彩艺
- 朱春雯

必须先冻结：

- 关键表结构
- 核心状态枚举
- 关键接口路径与 DTO
- 讲义块、问答、测验、复习任务的响应结构

完成标志：

- `ARCHITECTURE.md` 不再改核心命名
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
- PostgreSQL / Redis / MinIO 接入
- `async_tasks` 根任务/子任务模型
- demo 用户鉴权与 `course_catalog` seed 装载

依赖：

- 只依赖冻结后的表结构与接口定义

交付物：

- 可启动服务
- 健康检查
- 基础表迁移
- 空实现路由

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

### 10.1 曹乐

- 架构文档与分工文档
- 核心表结构定义
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

## 11. 冲突处理规则

- 需要改表结构：先找曹乐。
- 需要改接口响应：先找杨彩艺，曹乐确认业务语义，朱春雯确认页面消费。
- 需要改页面字段：先找朱春雯，若涉及接口新增字段，再走接口变更流程。
- 需要改 AIGC 输出格式：先找曹乐，不允许后端或前端私自扩展。

## 12. 开工前检查清单

- `ARCHITECTURE.md` 中表名、接口名、状态名已冻结
- 本文档中的 owner 没有重叠冲突
- 每个页面都能找到对应接口
- 每个生成型实体都能找到对应状态接口
- 每张引用表都能找到唯一写入入口
- 每位成员都明确自己本周的交付物

做到以上几点后，队员可以按本文档直接分工开做，且页面、接口、数据结构和 AI 输出能完全对得上。
