# 第 4 周比赛演示脚本与验收清单

适用时间：2026-05-11 至 2026-05-17。

适用范围：固定比赛演示路径和走查口径，不包含录屏产物。录屏时按本文执行即可；若实际接口或页面尚未接通，按对应步骤的验收点定位 owner。

Owner 边界：

- 曹乐：解析 / AI 产物策略、测验生成策略、判分到掌握度规则、复习推荐排序规则、引用可追溯规则、演示讲解顺序。
- 杨彩艺：FastAPI router / service / repository / DB / worker / task 接线、测验和复习运行时状态、落库与接口错误返回。
- 朱春雯：Flutter 页面、路由、Provider、真机展示和录屏体验。

## 1. 演示主线

固定路径：

1. 上传资料
2. 解析
3. 问询
4. 讲义
5. QA
6. 测验
7. 复习

讲解总句式：

KnowLink 把一门课的多源资料统一解析成可引用片段，再围绕这些片段生成个性化讲义、块级问答、测验和 Top3 复习任务。每一步都能回到原始资料，不依赖不可追溯的纯聊天结果。

## 2. 走查脚本

### 2.1 上传资料

展示动作：

- 创建或进入固定联调课程。
- 上传 1 个 MP4、1 个 PDF、1 个 PPTX、1 个 DOCX；SRT 只作为可选辅助输入。

用户价值：

- 用户不需要手工整理视频、讲义和课件，系统统一管理一门课的学习材料。

接口 / 数据验收点：

- `POST /api/v1/courses`
- `POST /api/v1/courses/{courseId}/resources/upload-init`
- `POST /api/v1/courses/{courseId}/resources/upload-complete`
- `course_resources.resource_type` 覆盖 `mp4`、`pdf`、`pptx`、`docx`
- `upload-complete` 响应里的 `ingestStatus`、`validationStatus`、`processingStatus` 分别进入可继续解析的状态
- 课程级状态以 `GET /api/v1/courses/{courseId}/pipeline-status` read model 的 `lifecycleStatus` 为准，不直接用 DB 字段误判

失败排障点：

- 资源上传失败先查 MinIO public endpoint 与 presigned URL。
- `resourceType` 不匹配时以 `docs/demo-assets-baseline.md` 的 MIME 与文件名为准。

### 2.2 解析

展示动作：

- 点击开始解析。
- 展示 pipeline 状态从 `queued/running` 到 `succeeded` 或 `partial_success`。
- 展示 `sourceOverview`、`knowledgeMap`、`highlightSummary`。

用户价值：

- 多源资料被拆成可检索、可引用、可跳转的课程片段。

接口 / 数据验收点：

- `POST /api/v1/courses/{courseId}/parse/start`
- `GET /api/v1/courses/{courseId}/pipeline-status`
- `parse_runs.status`
- `course_segments.segment_key`
- 视频片段带 `start_sec/end_sec`
- PDF / PPTX / DOCX 片段分别带 `page_no`、`slide_no`、`anchor_key`

失败排障点：

- 若 `partial_success`，先确认失败资源是否阻塞后续问询和讲义。
- 若解析结果乱码或空段，优先回查 parser 输出质量，不继续录制下游。

### 2.3 问询

展示动作：

- 进入问询页，回答学习目标、基础水平、时间预算、讲义风格、解释密度。

用户价值：

- 系统不是固定讲义模板，而是按学习目标和基础调整讲义与测验难度。

接口 / 数据验收点：

- `GET /api/v1/courses/{courseId}/inquiry/questions`
- `POST /api/v1/courses/{courseId}/inquiry/answers`
- `learning_preferences.goal_type`
- `learning_preferences.mastery_level`
- `learning_preferences.time_budget_minutes`
- `learning_preferences.handout_style`

失败排障点：

- 问询问题缺字段时先对齐 `docs/contracts/week2-cao-le-parse-inquiry-contract.md`。
- 偏好未保存时不要继续验证个性化讲义和测验难度。

### 2.4 讲义

展示动作：

- 生成或进入讲义目录。
- 点击目录项，按需生成讲义块。
- 展示讲义块的摘要、知识点、引用和跳转。

用户价值：

- 视频和文档被压缩成可学习的章节块，用户可以边看边跳回原始资料。

接口 / 数据验收点：

- `POST /api/v1/courses/{courseId}/handouts/generate`
- `GET /api/v1/courses/{courseId}/handouts/latest/outline`
- `GET /api/v1/courses/{courseId}/handouts/latest/blocks`
- `POST /api/v1/handout-blocks/{blockId}/generate`
- `handout_versions.source_parse_run_id` 等于当前 active parse run
- `handout_block_refs` 只引用当前讲义版本和当前 parse run 的片段

失败排障点：

- 目录能展示但正文未生成时，确认 `handout_versions.status = outline_ready` 是否符合预期。
- 重新解析后旧讲义仍可读时，检查 active parse run 与 handout version 的隔离。

### 2.5 QA

展示动作：

- 在当前讲义块提问一个与块内容相关的问题。
- 展示回答、引用、跳转位置。

用户价值：

- 用户围绕当前学习块追问，回答不跑到课程外，也能回到来源。

接口 / 数据验收点：

- `POST /api/v1/qa/messages`
- `GET /api/v1/qa/sessions/{sessionId}/messages`
- `qa_messages.answer_type`
- `qa_message_refs` 只写 assistant 引用
- 每条引用只包含一组 locator：`pageNo`、`slideNo`、`anchorKey` 或 `startSec/endSec`

失败排障点：

- 引用为空时先判断是否为 `insufficient_evidence`，不要强行录成“有来源回答”。
- 若回答引用课程外资源，停止录制并回查 QA candidates。

### 2.6 测验

展示动作：

- 生成 3 到 5 道单选题。
- 作答并提交。
- 展示分数、逐题对错、解释和掌握度变化。

用户价值：

- 系统把讲义块转成短测，用户立即知道哪些知识点掌握不稳。

接口 / 数据验收点：

- `POST /api/v1/courses/{courseId}/quizzes/generate`
- `GET /api/v1/quizzes/{quizId}`
- `POST /api/v1/quizzes/{quizId}/attempts`
- `quiz_questions.question_type = single_choice`
- `quiz_questions.correct_answer_json` 来自测验策略
- `quiz_question_refs` 由题目来源 block / segment 反查写入，不由 AI 直接生成页码或时间戳
- `quiz_attempt_items.is_correct`
- `masteryDelta[*].delta`

失败排障点：

- 提交答案后全错时，先确认 runtime 是否用 `questionId` 匹配答案。
- 题目无法追溯时，检查 `sourceBlockKey` 和 `sourceSegmentKeys` 是否存在。

### 2.7 复习

展示动作：

- 展示 Top3 复习任务。
- 打开第一条复习任务，跳回讲义块、视频片段或再练入口。

用户价值：

- 系统不是只给分数，而是把错题和低掌握度转成下一步行动。

接口 / 数据验收点：

- `GET /api/v1/courses/{courseId}/review-tasks`
- `POST /api/v1/courses/{courseId}/review-tasks/regenerate`
- `GET /api/v1/review-task-runs/{reviewTaskRunId}/status`
- `mastery_records.mastery_score`
- `mastery_records.confidence_score`
- `review_tasks.priority_score`
- `review_task_refs` 能追溯到题目来源知识点、讲义块或 segment；证据不足时不写虚构引用

失败排障点：

- Top3 排序异常时，检查是否按最终 `priorityScore` 排序，而不是只按未加权的错误次数排序。
- 复习任务无跳转时，先查 `sourceBlockKey/sourceSegmentKeys` 和 `review_task_refs`。

## 3. 最终验收清单

- 固定资料集包含 MP4、PDF、PPTX、DOCX；SRT 可选。
- 课程能从上传进入解析，并产出可引用 `course_segments`。
- 问询结果能保存为 `learning_preferences`。
- 讲义目录和讲义块能生成，且讲义块引用可跳转。
- QA 回答限定在当前课程和当前讲义块候选证据内。
- 测验生成 3 到 5 道单选题，提交后有分数、逐题结果和掌握度变化。
- 掌握度更新遵循：答对提高 mastery 和 confidence；答错降低 mastery，并保持或降低 confidence。
- 复习推荐只展示 Top3，排序综合最近错误、低掌握度、知识点重要度和证据可追溯性。
- `quiz_question_refs` 和 `review_task_refs` 都能追溯到合法 block / segment；证据不足时不虚构引用。
- 重新解析、重新生成讲义或重算复习后，旧版本结果不会污染当前 active parse run。
- 截止 2026-05-17 前不再新增非 MVP 功能，只修阻塞演示闭环的问题。

## 4. 录屏前快速检查

建议顺序：

1. 跑固定资料集 smoke，确认资源存在、checksum 和 MIME 对齐。
2. 启动后端和 Flutter 客户端。
3. 用 demo token 登录或请求接口。
4. 从空课程开始走完整路径。
5. 每一步只展示一个主价值点，不在录屏中展开内部实现。
6. 若某一步失败，停止录屏并记录接口、实体 id、状态、错误码。

不展示内容：

- 不展示真实密钥。
- 不展示数据库连接串。
- 不展示未接通的非 MVP 功能。
- 不承诺多课程、多用户、离线缓存或实时流式输出。
