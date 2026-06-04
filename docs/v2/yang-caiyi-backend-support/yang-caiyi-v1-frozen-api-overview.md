# 杨彩艺 V1 已冻结接口总表

来源：`docs/contracts/api-contract.md`

用途：把 V1/MVP 已冻结或已预留的接口集中成一张表，方便杨彩艺后续整理 DTO、联调记录、测试数据和待确认项。本文只摘录现有 contract，不新增实现逻辑，不扩写 B站、图谱、SSE、主观题判卷字段。

## 通用约定

| 项目 | 已冻结口径 |
|---|---|
| API 前缀 | `/api/v1` |
| 鉴权 | 除 `/health` 外均需要 `Authorization: Bearer <token>` |
| demo token | `.env` / `.env.example` 中的 `KNOWLINK_DEMO_TOKEN` |
| 统一成功响应 | `code`、`message`、`data`、`requestId`、`timestamp` |
| 统一失败响应 | `code`、`message`、`errorCode`、`data`、`requestId`、`timestamp` |
| 资源类型 | `mp4`、`pdf`、`pptx`、`docx`，`srt` 为可选辅助输入 |
| citation 定位 | PDF 用 `pageNo`，PPTX 用 `slideNo`，DOCX 用 `anchorKey`，视频用 `startSec/endSec` |
| 写接口幂等 | 部分写接口必须支持 `Idempotency-Key` |
| 课程路径参数 | 带 path `courseId` 的接口以 path 为准，请求体不重复传同义 `courseId`，`POST /api/v1/qa/messages` 除外 |

## 核心枚举

| 枚举 | 取值 |
|---|---|
| `lifecycleStatus` | `draft`、`resource_ready`、`inquiry_ready`、`learning_ready`、`archived`、`failed` |
| `pipelineStage` | `idle`、`upload`、`parse`、`inquiry`、`handout` |
| `pipelineStatus` | `idle`、`queued`、`running`、`partial_success`、`succeeded`、`failed` |
| `async_tasks.status` | `queued`、`running`、`succeeded`、`failed`、`retrying`、`canceled`、`skipped` |
| `handout_versions.status` | `draft`、`generating`、`outline_ready`、`ready`、`partial_success`、`failed`、`superseded` |
| 异步实体 `entity.type` | `parse_run`、`handout_version`、`handout_block`、`quiz`、`review_task_run`、`bilibili_import_run` |

## 接口总表

| 模块 | 方法 | 路径 | Contract 状态 | 主要请求字段 | 主要响应字段 | 杨彩艺可做事项 |
|---|---|---|---|---|---|---|
| 推荐 | `POST` | `/api/v1/recommendations/courses` | V1 已冻结 | `goalText`、`selfLevel`、`timeBudgetMinutes`、`examAt`、`preferredStyle` | `recommendations[]`、`requestEcho` | 整理推荐 DTO、测试样例、推荐理由文案 |
| 推荐 | `POST` | `/api/v1/recommendations/{catalogId}/confirm` | V1 已冻结 | `goalText`、`examAt`、`preferredStyle`、`titleOverride` | `course`、`createdFromCatalogId` | 整理确认入课 DTO、联调记录 |
| 课程 | `POST` | `/api/v1/courses` | V1 已冻结 | `title`、`entryType`、`goalText`、`examAt`、`preferredStyle` | `course` | 整理课程创建 DTO、幂等说明 |
| 课程 | `GET` | `/api/v1/courses/recent` | V1 已冻结 | 无 | `items[]` | 整理最近课程列表字段 |
| 课程 | `GET` | `/api/v1/courses/{courseId}` | 已写入 contract | path: `courseId` | `course` | 整理课程详情字段；若实现缺口存在，先标待确认 |
| 课程 | `POST` | `/api/v1/courses/{courseId}/switch-current` | 已写入 contract | path: `courseId` | `currentCourseId`、`course` | 整理课程切换字段；不设计复杂多用户语义 |
| 课程 | `GET` | `/api/v1/courses/current` | 已写入 contract | 无 | `course` | 整理当前课程语义和联调记录 |
| 首页 | `GET` | `/api/v1/home/dashboard` | V1 已冻结 | 无 | `recentCourses`、`topReviewTasks`、`recommendationEntryEnabled`、`dailyRecommendedKnowledgePoints`、`learningStats` | 整理首页 dashboard DTO |
| 资源 | `POST` | `/api/v1/courses/{courseId}/resources/upload-init` | V1 已冻结 | `resourceType`、`filename`、`mimeType`、`sizeBytes`、`checksum` | `uploadUrl`、`objectKey`、`headers`、`expiresAt` | 整理上传初始化字段和 Android/浏览器可达性注意事项 |
| 资源 | `POST` | `/api/v1/courses/{courseId}/resources/upload-complete` | V1 已冻结 | `resourceType`、`objectKey`、`originalName`、`mimeType`、`sizeBytes`、`checksum` | `resourceId`、`ingestStatus`、`validationStatus`、`processingStatus` | 整理上传完成 DTO、幂等说明 |
| 资源 | `GET` | `/api/v1/courses/{courseId}/resources` | V1 已冻结 | path: `courseId` | `items[]` | 整理课程资源列表字段 |
| 资源 | `GET` | `/api/v1/course-resources/{resourceId}/playback` | V1 已冻结 | path: `resourceId` | `resourceId`、`resourceType`、`playbackUrl`、`mimeType`、`expiresAt`、`durationSec` | 整理播放地址联调说明，重点记录 URL 可达性 |
| 资源 | `DELETE` | `/api/v1/courses/{courseId}/resources/{resourceId}` | V1 已冻结 | path: `courseId`、`resourceId` | `deleted`、`resourceId` | 整理删除资源错误边界；不做级联删除策略 |
| B站预留 | `POST` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | V1 stub 预留；V2 另有 contract | V1 stub: `videoUrl` | V1 统一 `501 bilibili.not_implemented` | 只整理预留路径和 stub 行为，不扩写 V2 字段 |
| B站预留 | `GET` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | V1 stub 预留；V2 另有 contract | path: `courseId` | V1 无真实列表数据 | 只整理预留路径和待确认项 |
| B站预留 | `GET` | `/api/v1/bilibili-import-runs/{importRunId}/status` | V1 stub 预留；V2 另有 contract | path: `importRunId` | V1 无真实状态数据 | 只整理预留路径和待确认项 |
| B站预留 | `POST` | `/api/v1/bilibili-import-runs/{importRunId}/cancel` | V1 stub 预留；V2 另有 contract | path: `importRunId` | V1 不执行真实取消 | 只整理取消入口，不处理取消副作用 |
| B站预留 | `POST` | `/api/v1/bilibili/auth/qr/sessions` | V1 stub 预留；V2 另有 contract | 无 | V1 不创建真实扫码会话 | 只整理预留路径 |
| B站预留 | `GET` | `/api/v1/bilibili/auth/qr/sessions/{sessionId}` | V1 stub 预留；V2 另有 contract | path: `sessionId` | V1 不查询真实扫码状态 | 只整理预留路径 |
| B站预留 | `GET` | `/api/v1/bilibili/auth/session` | V1 stub 预留；V2 另有 contract | 无 | V1 不查询真实登录态 | 只整理预留路径 |
| B站预留 | `DELETE` | `/api/v1/bilibili/auth/session` | V1 stub 预留；V2 另有 contract | 无 | V1 不执行真实退出登录 | 只整理预留路径 |
| 解析 | `POST` | `/api/v1/courses/{courseId}/parse/start` | V1 已冻结 | path: `courseId` | `taskId`、`status`、`nextAction`、`entity` | 整理异步触发返回结构、幂等说明 |
| 解析 | `GET` | `/api/v1/parse-runs/{parseRunId}` | V1 已冻结 | path: `parseRunId` | `parseRunId`、`courseId`、`status`、`progressPct`、`startedAt`、`finishedAt` | 整理解析运行状态字段 |
| 解析 | `GET` | `/api/v1/courses/{courseId}/pipeline-status` | V1 已冻结 | path: `courseId` | `courseStatus`、`progressPct`、`steps[]`、`nextAction`、`sourceOverview`、`knowledgeMap`、`handoutOutline`、`highlightSummary` | 整理主轮询字段和状态样例 |
| 解析 | `GET` | `/api/v1/courses/{courseId}/parse/summary` | V1 已冻结 | path: `courseId` | `courseId`、`activeParseRunId`、`segmentCount`、`knowledgePointCount`、`generatedKnowledgePointCount`、`handoutOutlineStatus`、`outlineItemCount` | 整理解析摘要辅助接口 |
| 异步任务 | `POST` | `/api/v1/async-tasks/{taskId}/retry` | V1 已冻结 | path: `taskId` | `taskId`、`status`、`nextAction` | 整理 retry 适用状态和错误码 |
| 问询 | `GET` | `/api/v1/courses/{courseId}/inquiry/questions` | V1 已冻结 | path: `courseId` | `version`、`questions[]` | 整理问询题字段和选项结构 |
| 问询 | `POST` | `/api/v1/courses/{courseId}/inquiry/answers` | V1 已冻结 | `answers[]` | `saved`、`answerCount` | 整理问询答案提交 DTO |
| 讲义 | `POST` | `/api/v1/courses/{courseId}/handouts/generate` | V1 已冻结 | path: `courseId` | `taskId`、`status`、`nextAction`、`entity` | 整理讲义生成异步返回结构 |
| 讲义 | `GET` | `/api/v1/handout-versions/{handoutVersionId}/status` | V1 已冻结 | path: `handoutVersionId` | `handoutVersionId`、`status`、`outlineStatus`、`totalBlocks`、`readyBlocks`、`pendingBlocks`、`sourceParseRunId` | 整理讲义版本状态字段 |
| 讲义 | `GET` | `/api/v1/courses/{courseId}/handouts/latest` | V1 已冻结 | path: `courseId` | `handoutVersionId`、`title`、`summary`、`totalBlocks`、`status` | 整理最新讲义摘要字段 |
| 讲义 | `GET` | `/api/v1/courses/{courseId}/handouts/latest/outline` | V1 已冻结 | path: `courseId` | `handoutVersionId`、`title`、`summary`、`items[]` | 整理两级 outline 字段 |
| 讲义 | `GET` | `/api/v1/courses/{courseId}/handouts/latest/blocks` | V1 已冻结 | path: `courseId` | `items[]` | 整理 block、citation、generationMetadata 字段 |
| 讲义 | `POST` | `/api/v1/handout-blocks/{blockId}/generate` | V1 已冻结 | path: `blockId` | `taskId`、`status`、`nextAction`、`entity` | 整理单块懒生成异步返回结构和幂等说明 |
| 讲义 | `GET` | `/api/v1/handout-blocks/{blockId}/status` | V1 已冻结 | path: `blockId` | `blockId`、`outlineKey`、`status`、`generationStatus`、`startSec`、`endSec` | 整理 block 状态查询字段 |
| 讲义 | `GET` | `/api/v1/courses/{courseId}/handouts/current-block` | V1 已冻结 | query: `currentSec` | `blockId`、`outlineKey`、`startSec`、`endSec`、`status`、`generationStatus`、`prefetchBlockId` | 整理播放时间命中和预取字段说明 |
| 讲义 | `GET` | `/api/v1/handout-blocks/{blockId}/jump-target` | V1 已冻结 | path: `blockId` | `blockId`、`videoResourceId`、`startSec`、`endSec`、`docResourceId`、locator 字段 | 整理跳转目标字段 |
| QA | `POST` | `/api/v1/qa/messages` | V1 已冻结 | `courseId`、`handoutBlockId`、`question` | `sessionId`、`messageId`、`answerMd`、`answerType`、`generationMetadata`、`citations[]` | 整理 QA DTO 和 citation 约束 |
| QA | `GET` | `/api/v1/qa/sessions/{sessionId}/messages` | V1 已冻结 | path: `sessionId` | `items[]` | 整理 QA 历史消息字段 |
| 测验 | `POST` | `/api/v1/courses/{courseId}/quizzes/generate` | V1 已冻结 | 可省略；可传 `questionCountLevel` | 异步返回，`entity.type = quiz` | 整理客观题生成 DTO；不扩写主观题 |
| 测验 | `GET` | `/api/v1/quizzes/{quizId}` | V1 已冻结 | path: `quizId` | `quizId`、`courseId`、`status`、`questionCount`、`questions[]` | 整理测验读取字段 |
| 测验 | `POST` | `/api/v1/quizzes/{quizId}/attempts` | V1 已冻结客观题提交 | `answers[].questionId`、`answers[].selectedOption` | `attemptId`、`score`、`totalScore`、`accuracy`、`reviewTaskRunId`、`masteryDelta[]`、`recommendedReviewAction` | 只整理客观题；主观题判卷不扩写 |
| 复习 | `GET` | `/api/v1/courses/{courseId}/review-tasks` | V1 已冻结 | path: `courseId` | `items[]` | 整理复习任务列表字段 |
| 复习 | `POST` | `/api/v1/courses/{courseId}/review-tasks/regenerate` | V1 已冻结 | path: `courseId` | 异步返回，`entity.type = review_task_run` | 整理复习重算异步返回结构 |
| 复习 | `GET` | `/api/v1/review-task-runs/{reviewTaskRunId}/status` | V1 已冻结 | path: `reviewTaskRunId` | `reviewTaskRunId`、`courseId`、`status`、`generatedCount` | 整理复习重算状态字段 |
| 复习 | `POST` | `/api/v1/review-tasks/{reviewTaskId}/complete` | V1 已冻结 | path: `reviewTaskId` | `reviewTaskId`、`completed` | 整理复习任务完成字段 |
| 进度 | `GET` | `/api/v1/courses/{courseId}/progress` | V1 已冻结 | path: `courseId` | `courseId`、`handoutVersionId`、`lastHandoutBlockId`、`lastVideoResourceId`、`lastPositionSec`、`lastDocResourceId`、`lastPageNo`、`lastActivityAt` | 整理最近学习位置读取字段 |
| 进度 | `POST` | `/api/v1/courses/{courseId}/progress` | V1 已冻结 | `handoutVersionId`、`lastHandoutBlockId`、`lastVideoResourceId`、`lastPositionSec`、`lastDocResourceId`、`lastPageNo` | `lastActivityAt` 由服务端补写 | 整理最近学习位置保存字段 |

## 写接口幂等清单

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/courses` | 创建课程 |
| `POST` | `/api/v1/recommendations/{catalogId}/confirm` | 确认入课 |
| `POST` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | B站导入预留；V2 真实字段以单独 contract 为准 |
| `POST` | `/api/v1/courses/{courseId}/resources/upload-complete` | 上传完成 |
| `POST` | `/api/v1/courses/{courseId}/parse/start` | 启动解析 |
| `POST` | `/api/v1/courses/{courseId}/handouts/generate` | 生成讲义 |
| `POST` | `/api/v1/handout-blocks/{blockId}/generate` | 生成单个讲义块 |
| `POST` | `/api/v1/courses/{courseId}/quizzes/generate` | 生成测验 |
| `POST` | `/api/v1/courses/{courseId}/review-tasks/regenerate` | 重算复习任务 |

## 杨彩艺后续整理建议

| 优先级 | 下一步 | 产出 |
|---|---|---|
| 1 | 按模块拆出 DTO 字段表 | `推荐 / 课程 / 资源 / B站预留 / 解析 / 讲义 / QA / 测验 / 复习 / 进度` 字段文档 |
| 2 | 标注当前可联调接口和仅预留接口 | 联调 checklist |
| 3 | 给每个查询接口准备 1 个成功样例和 1 个失败样例 | 测试数据清单 |
| 4 | 对 B站、图谱、SSE、主观题判卷只列待冻结项 | 待曹乐确认问题清单 |
| 5 | 把 Android 联调关注点单独摘出 | 后端地址、MinIO public endpoint、播放 URL 可达性记录 |
