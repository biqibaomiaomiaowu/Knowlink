# KnowLink MVP 4 周开发任务清单

本计划用于 KnowLink 第一版开发排期，周期按 2026 年 4 月 20 日到 2026 年 5 月 17 日拆分为 4 周，对应 [ARCHITECTURE.md](./ARCHITECTURE.md) 和 [TEAM_DIVISION.md](./TEAM_DIVISION.md)。

目标不是平均分配工作量，而是保证三位成员在同一周内做的事情能对上同一条主链路，并且每周都有可演示成果。

## 1. 时间范围

- 第 1 周：2026-04-20 至 2026-04-26
- 第 2 周：2026-04-27 至 2026-05-03
- 第 3 周：2026-05-04 至 2026-05-10
- 第 4 周：2026-05-11 至 2026-05-17

## 2. 总体规则

- 第 1 周结束后，不再改核心表名、接口名、状态名。
- 每周必须至少打通一条真实链路，不能只停留在页面壳子或空接口。
- Flutter 端只对接已冻结 DTO，不反向定义后端字段。
- 后端只实现已冻结业务语义，不临时改 AI 输出结构。
- 每周末必须做一次固定资料集联调，资料集固定为 1 个 MP4、1 个 PDF、1 个 PPTX、1 个 DOCX，`SRT` 作为可选辅助输入。
- MVP 真正承诺打通的文件范围固定为 `MP4 + PDF + PPTX + DOCX`，`SRT` 作为可选辅助输入。
- 智能课程推荐必须在第 1 周进入真实联调，不允许只保留推荐页 mock。

## 2.1 预开工：2026-04-18 至 2026-04-19

- 冻结 demo 用户鉴权方案：单个种子用户 + 固定 Bearer token。
- 冻结 `course_catalog`、推荐请求 DTO、推荐结果 DTO、确认入课返回结构。
- 起 `server/`、`client_flutter/`、`docker-compose.yml`、AI schema、error code 文档骨架。

## 3. 第 1 周：契约冻结与工程骨架

### 3.1 本周目标

- 冻结核心表结构、关键状态枚举、关键接口 DTO。
- 起好 Flutter 和 FastAPI 工程骨架。
- 打通 `智能推荐 -> 确认入课 -> 创建课程` 的真实链路。
- 准备统一演示资料和联调基线。

### 3.2 曹乐

- 冻结核心表定义：`courses`、`course_resources`、`parse_runs`、`async_tasks`、`learning_preferences`、`handout_versions`、`quizzes`、`review_task_runs`。
- 冻结 `course_catalog`、推荐排序字段和推荐理由字段。
- 冻结核心状态：`lifecycle_status`、`pipeline_stage`、`pipeline_status`、`async_tasks.status`。
- 输出 AI 与解析 contract：
  - 讲义块 JSON Schema
  - QA 返回结构
  - 测验题结构
  - 复习任务结构
  - OCR / 文档解析输出规范
- 冻结 demo 鉴权与 demo 课程目录种子数据。
- 准备统一测试资料集和演示课程标题。

### 3.3 朱春雯

- 起 `client_flutter` 工程骨架。
- 完成 `go_router`、主题、网络层、全局错误态和 loading 组件。
- 接入智能推荐页真实交互：
  - `POST /api/v1/recommendations/courses`
  - `POST /api/v1/recommendations/{catalogId}/confirm`
- 建好 9 个页面壳子：
  - 首页
  - 自主导入页
  - 智能推荐页
  - 解析进度页
  - 问询页
  - 讲义页
  - QA 页
  - 测验页
  - 复习页
- 建立 Provider 骨架：
  - `courseFlowProvider`
  - `activeCourseIdProvider`
  - `activeBlockProvider`
  - `playerStateProvider`
  - `courseRecommendProvider`
  - handout / quiz / review feature 内请求态 provider

### 3.4 杨彩艺

- 起 `server` 工程骨架。
- 接入 FastAPI、PostgreSQL、Redis、MinIO。
- 建第一批 migration 骨架。
- 建立基础响应结构、健康检查、日志、配置读取。
- 建立 `async_tasks` 根任务 / 子任务模型和基础 router 空实现。
- 实现 demo 用户鉴权和 `course_catalog` seed 装载。
- 实现推荐接口：
  - `POST /api/v1/recommendations/courses`
  - `POST /api/v1/recommendations/{catalogId}/confirm`
- 输出接口文档初稿，覆盖请求字段、响应字段、错误码。

### 3.5 本周交付物

- 冻结版表结构。
- 冻结版关键 DTO。
- Flutter 页面壳子可运行。
- FastAPI 服务可启动。
- 推荐页可返回真实推荐结果并确认入课。
- demo Bearer token 与 `course_catalog` 种子数据准备完成。
- 固定联调资料集准备完成。

### 3.6 本周验收

- 三个人对 owner 边界没有歧义。
- README、架构文档、分工文档、周计划文档互相能对上。
- 第 2 周开发不再需要讨论核心命名。
- 推荐页不再依赖 mock 数据。

## 4. 第 2 周：上传、解析、问询链路

### 4.1 本周目标

- 打通 `确认入课或自主创建课程 -> 上传资源 -> 发起解析 -> 查看解析进度 -> 进入问询`。

### 4.2 曹乐

- 输出解析结果字段说明：
  - `course_segments`
  - `knowledge_points`
  - `segment_knowledge_points`
  - `knowledge_point_evidences`
  - `vector_documents`
- 定义解析步骤映射：
  - 资源校验
  - 字幕提取 / ASR
  - 文档解析
  - 知识点抽取
  - 向量化
- 定义问询题模板和 `learning_preferences` 字段语义。
- 与杨彩艺确认 `parse_run` 聚合状态和 `pipeline-status` 返回结构。

### 4.3 朱春雯

- 接入导入页真实交互。
- 接入上传链路：
  - `POST /api/v1/courses`
  - `POST /api/v1/courses/{courseId}/resources/upload-init`
  - 文件直传对象存储
  - `POST /api/v1/courses/{courseId}/resources/upload-complete`
- 接入解析进度页轮询：
  - `POST /api/v1/courses/{courseId}/parse/start`
  - `GET /api/v1/courses/{courseId}/pipeline-status`
- 接入问询页：
  - `GET /api/v1/courses/{courseId}/inquiry/questions`
  - `POST /api/v1/courses/{courseId}/inquiry/answers`
- 保留讲义页、测验页、复习页为 mock 占位，但路由需可跳转。

### 4.4 杨彩艺

- 实现创建课程、上传初始化、上传完成、资源列表接口。
- 实现 `parse_runs`、`async_tasks`、`course_resources` 的最小可用链路。
- 实现解析接口：
  - `POST /api/v1/courses/{courseId}/parse/start`
  - `GET /api/v1/courses/{courseId}/pipeline-status`
  - `GET /api/v1/parse-runs/{parseRunId}`
- 实现问询接口：
  - `GET /api/v1/courses/{courseId}/inquiry/questions`
  - `POST /api/v1/courses/{courseId}/inquiry/answers`
- 落库基础解析结果，至少能写入 `course_segments` 和 `knowledge_points`。

### 4.5 本周交付物

- 能创建一门课程并上传资料。
- 能看到真实解析进度。
- 解析完成后能进入问询页并保存答案。
- 数据库中能看到真实 `parse_run`、`async_task`、`segment`、`knowledge_point` 数据。

### 4.6 本周验收

- 固定资料集可稳定跑通上传和解析。
- 解析失败时前端能看到明确错误，不会卡死在 loading。
- 问询字段和后续讲义生成字段完全对齐。

## 5. 第 3 周：讲义、联动、问答链路

### 5.1 本周目标

- 打通 `问询 -> 生成讲义 -> 讲义阅读 -> 跳视频/页码 -> 围绕当前块问答`。

### 5.2 曹乐

- 定稿讲义生成策略：
  - 讲义块数量
  - 标题 / 摘要 / 正文结构
  - 来源引用规则
  - 失败兜底策略
- 定稿 QA 策略：
  - 当前块上下文边界
  - 相邻块扩展边界
  - 证据不足返回规范
- 定义 `handout_block_refs` 和 `qa_message_refs` 写入规则。
- 确认 `vector_documents` 在 `handout_version` 范围下的检索约束。

### 5.3 朱春雯

- 完成讲义页真实接入：
  - 视频区
  - 讲义块列表
  - 当前块正文
  - 引用展示
  - QA 面板
- 接入讲义生成和讲义状态轮询：
  - `POST /api/v1/courses/{courseId}/handouts/generate`
  - `GET /api/v1/handout-versions/{handoutVersionId}/status`
- 接入讲义数据：
  - `GET /api/v1/courses/{courseId}/handouts/latest`
  - `GET /api/v1/courses/{courseId}/handouts/latest/blocks`
  - `GET /api/v1/handout-blocks/{blockId}/jump-target`
- 接入 QA：
  - `POST /api/v1/qa/messages`
- 做播放器与讲义块联动、高亮和引用点击跳转。

### 5.4 杨彩艺

- 实现讲义生成根任务和状态接口。
- 落库并返回：
  - `handout_versions`
  - `handout_blocks`
  - `handout_block_refs`
- 实现讲义接口：
  - `POST /api/v1/courses/{courseId}/handouts/generate`
  - `GET /api/v1/handout-versions/{handoutVersionId}/status`
  - `GET /api/v1/courses/{courseId}/handouts/latest`
  - `GET /api/v1/courses/{courseId}/handouts/latest/blocks`
  - `GET /api/v1/handout-blocks/{blockId}/jump-target`
- 实现 QA 接口与落库：
  - `qa_sessions`
  - `qa_messages`
  - `qa_message_refs`
- 接入最小可用 RAG，确保回答携带结构化 citations。

### 5.5 本周交付物

- 问询提交后能真实生成讲义。
- 讲义块可联动视频和文档页码。
- 当前块提问可返回答案和引用。
- 讲义页达到可录屏演示状态。

### 5.6 本周验收

- 同一课程重生成讲义时，旧版与新版数据不串。
- QA 回答的引用能跳到正确资源。
- 第 3 周周末必须录制一版“问询 -> 讲义 -> 提问”的完整演示视频。

## 6. 第 4 周：测验、复习、首页聚合与最终联调

### 6.1 本周目标

- 打通 `测验 -> 判分 -> 掌握度 -> 复习推荐`。
- 完成首页聚合、最近学习恢复、整体验收和比赛演示准备。

### 6.2 曹乐

- 定稿测验生成策略和判分映射规则。
- 定稿 `mastery_records` 更新逻辑和复习推荐排序规则。
- 定义 `quiz_question_refs`、`review_task_refs` 写入规则。
- 输出最终演示脚本、讲解顺序和验收清单。
- 组织全链路走查，固定比赛演示路径。

### 6.3 朱春雯

- 完成测验页、结果页、复习页、首页推荐卡的真实接入。
- 接入接口：
  - `POST /api/v1/courses/{courseId}/quizzes/generate`
  - `GET /api/v1/quizzes/{quizId}`
  - `GET /api/v1/quizzes/{quizId}/status`
  - `POST /api/v1/quizzes/{quizId}/attempts`
  - `GET /api/v1/courses/{courseId}/review-tasks`
  - `POST /api/v1/courses/{courseId}/review-tasks/regenerate`
  - `GET /api/v1/review-task-runs/{reviewTaskRunId}/status`
  - `GET /api/v1/home/dashboard`
  - `GET /api/v1/courses/{courseId}/progress`
  - `POST /api/v1/courses/{courseId}/progress`
- 完成最近学习恢复、复习任务跳转讲义 / 视频 / 再练。
- 做真机适配、键盘冲突检查和录屏演示优化。

### 6.4 杨彩艺

- 实现测验生成、测验详情、测验状态、提交答案接口。
- 落库并更新：
  - `quizzes`
  - `quiz_questions`
  - `quiz_attempts`
  - `quiz_attempt_items`
  - `quiz_question_refs`
- 实现 `mastery_records` 更新和 `review_task_runs` / `review_tasks` 生成。
- 实现首页聚合接口和最近学习进度接口。
- 做部署脚本、联调修复、日志排障和性能兜底。

### 6.5 本周交付物

- 测验页面可做题、提交并看到结果。
- 掌握度能更新，复习任务能生成。
- 首页能展示最近学习和 Top3 复习任务。
- 真机上能完整演示一条 MVP 主链路。

### 6.6 本周验收

- 固定资料集可跑完整闭环：
  - 上传
  - 解析
  - 问询
  - 讲义
  - 问答
  - 测验
  - 复习
- 比赛演示脚本、录屏和答辩顺序确定。
- 截止 2026-05-17 前不再新增非 MVP 功能。

## 7. 每周站会最少要确认的 5 件事

- 这周要打通的主链路是什么。
- 当前是否存在阻塞下游的 DTO 或表结构未冻结项。
- 哪个接口已可联调，哪个接口仍只能用 mock。
- 固定资料集跑到哪一步，报错点在哪里。
- 本周末录屏演示由谁准备，演示路径是否已经固定。

## 8. 最终验收清单

- 上传 1 个 MP4、1 个 PDF、1 个 PPTX、1 个 DOCX 后可完成解析，`SRT` 作为可选辅助输入。
- 问询后能生成 8 到 15 个讲义块。
- 点击讲义块可跳视频时间戳或文档页码。
- 围绕当前块发问可返回结构化 citations。
- 完成 3 到 5 道题后可看到分数、掌握度变化和复习建议。
- 首页能展示最近学习和 Top3 复习任务。
- 重新生成讲义或重算复习时，旧结果不会污染新结果。
