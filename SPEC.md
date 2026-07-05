# SPEC.md

## Overview

### 当前分支现状

目标分支 `codex/rerecreate` 相对 `main` 主要完成了 Flutter 高保真前端、前端模型、provider、API wrapper 和 contract 文档改造。后端主干能力已经较完整，当前主要缺口不是从零实现后端，而是前端已露出入口、API wrapper 已存在或后端 contract 已存在，但没有形成闭环。

已核实的主要断点：

- `CourseWorkbenchPage` 课程级“上传资料”按钮仍是空操作。
- 新建课时弹窗展示 B 站链接、学习目标、掌握程度、时间预算，但提交只传 `title/sourceType`。
- `LessonStudyPage` 会从 lesson detail 恢复 `positionSec`，但未稳定保存播放位置、当前讲义块和阅读进度。
- B 站 preview/import/auth/status/cancel/retry 能力已有，但未接入新建课时流程。
- quiz submit 能拿到 `reviewTaskRunId` 并写入 `CourseFlow`，但 ReviewPage 未消费该 run id 轮询刷新 read model。
- 课程库搜索/筛选/排序 UI 是静态展示。
- QA 页面能发消息，但 session list、history messages、continue session 未闭环。
- 课时学习页内嵌 AI QA 只展示回答，不展示用户问题。
- 本节资料弹窗只读展示。
- 后端和 wrapper 已有课时管理能力，但 workbench 课时卡片缺管理入口。
- “历史课程测试”和“重新生成课程测试”实际都只是跳当前 quiz 页。
- 后端已有 `delete-impact`、`archive`、`restore`，前端未接入。

### 本轮目标

本轮目标是前后端接入收尾，不做大规模重构：

1. P0：补齐主流程可信度，包括上传资料、课时进度、新建课时字段、B 站导入、复习闭环。
2. P1：补齐已露出 UI 的真实交互，包括课程库筛选、QA 历史、课时 AI QA、本节资料弹窗、课时管理入口。
3. P2：补齐管理能力，包括 quiz history、重新生成语义、删除影响确认、归档/恢复。
4. 复用现有 `ApiClient`、`CourseLessonApi`、Riverpod provider、FastAPI service/repository 分层。
5. 所有新增字段/API 同步 `docs/contracts/*.md`。
6. 所有新增行为必须有 Flutter provider/widget tests 和后端 API/service/repository tests。

### Non-goals

Codex 本轮不得实现以下内容：

1. 知识图谱生成 / 图谱 read model。
2. 课程设置完整功能。
3. 课程导出。
4. 本节复习完整页。
5. 主观题判卷。
6. 学习报告。
7. `/courses/:courseId/handout` 作为课程级讲义页。
8. 大规模 UI 重设计。
9. 更换现有 soft-ui / neumorphism 风格。
10. 重写整个后端架构。

`/courses/:courseId/handout` 只允许作为兼容入口：有 active lesson 时跳到 lesson handout，否则提示选择课时；不得实现课程级讲义页。

---

## Source of truth

### 前端已露出入口

| 区域 | 文件 | 当前状态 | 本轮处理 |
|---|---|---|---|
| 路由 | `client_flutter/lib/app/router/app_router.dart` | 已有课程库、工作台、课时学习、课程/课时 quiz、QA、review、graph、exports 路由；`/courses/:courseId/handout` 是兼容页。 | 保留路由体系，只做 query/path 扩展。 |
| 全局框架 | `client_flutter/lib/core/widgets/app_scaffold.dart` | 依据 active course/lesson 控制导航。 | 不重写。 |
| 课程库 | `client_flutter/lib/features/course_library/course_library_page.dart` | 搜索/状态/排序是静态 `_InsetField`；删除确认是固定文案；无归档/恢复。 | 接真实 query、delete-impact、archive/restore。 |
| 课程库 provider | `client_flutter/lib/shared/providers/course_library_provider.dart` | 无参数 `FutureProvider`，默认 `fetchCourseLibrary()`。 | 增加 query state / family provider。 |
| 课程工作台 | `client_flutter/lib/features/course_workbench/course_workbench_page.dart` | 课程级上传为 `_noop`；quiz 按钮语义不完整；课时卡片缺管理入口。 | P0/P1/P2 分阶段接入。 |
| 新建课时弹窗 | `course_workbench_page.dart` | 表单字段多，但提交只传 `title` 和 `sourceType: manual`。 | 增加 metadata 落库和 B 站导入。 |
| 准备课时页 | `LessonPreparationPage` | 已能上传 lesson-scoped 文件、parse、generate lesson handout、轮询后进入课时学习。 | 复用，不重写。 |
| 课时学习页 | `client_flutter/lib/features/lesson_study/lesson_study_page.dart` | 能加载视频/讲义/当前块；未保存进度；本节资料只读；AI QA 只显示回答。 | 增加进度持久化、QA pair、资料操作。 |
| 课时学习 provider | `client_flutter/lib/shared/providers/lesson_study_provider.dart` | 加载 detail/playback/handout/outline/current-block；`askQuestion` 调 lesson QA。 | 增加 progress flush 与 QA exchange state。 |
| QA 页面 | `client_flutter/lib/features/course_qa/course_qa_page.dart` | 可发消息，session id 仅本地，placeholder 使用 session endpoint 兜底。 | 接 session list/history/continue。 |
| Quiz | `client_flutter/lib/features/quiz/quiz_page.dart`, `quiz_provider.dart` | 可生成/提交 quiz；无 history；workbench regenerate 不触发生成。 | 增加 history 和 auto regenerate。 |
| Review | `client_flutter/lib/features/review/review_page.dart`, `review_provider.dart` | 可 load/regenerate/complete/open handout/enter quiz；不消费 quiz submit run id。 | 增加 existing run polling。 |
| Resource upload | `resource_upload_models.dart`, `course_import_provider.dart` | CourseImportPage 已有完整上传链路。 | 工作台复用该链路或抽 shared upload controller。 |
| B 站导入 | `bilibili_import_provider.dart`, `bilibili_import_models.dart` | 已有 auth/preview/import/status/cancel/retry；前端 create request 缺 bind-existing 字段。 | 扩展并接新建课时。 |

### 后端已有 contract

| 能力 | 文件 | 状态 |
|---|---|---|
| 课程库查询 | `server/api/routers/courses.py`, `server/domain/services/courses.py` | `GET /courses` 已支持 `q`, `learningStatus`, `source`, `archived`, `sort`。 |
| 删除影响 | `courses.py`, `CourseService.get_course_delete_impact` | `GET /courses/{courseId}/delete-impact` 已存在。 |
| 归档/恢复 | `courses.py`, `CourseService.archive_course/restore_course` | `POST /archive`, `POST /restore` 已存在。 |
| 分层资源上传 | `resources.py`, `resources service`, `server/schemas/requests.py` | upload-init/upload-complete/list/delete/playback 已存在；scope 字段已存在。 |
| 课时管理 | `lessons.py`, `LessonService` | create/update/delete/reorder/merge/split/primary-video 已存在。 |
| 课时进度 | `progress.py`, `ProgressService` | `GET/PUT /courses/{courseId}/lessons/{lessonId}/progress` 已存在。 |
| B 站导入 | `bilibili.py`, `BilibiliService`, requests schema | preview/create/list/status/cancel/auth 已存在；后端 request 支持 `lessonMode`, `targetLessonId`, `partLessonMap`, `createLessonIfMissing`。 |
| QA | `qa.py`, `QaService` | course/lesson session list、create message、session messages 已存在。 |
| Quiz | `quizzes.py` | generate course/lesson、current lesson quiz、detail/status、submit 已存在；缺 course quiz history list。 |
| Review | `reviews.py`, review service/repository/tasks | course/lesson review、review-tasks regenerate、run status、complete 已存在。 |
| Contract docs | `docs/contracts/v2-course-lesson-workbench-contract.md` | 多数 V2 contract 已记录，需补本轮新增/扩展字段。 |

### 已存在但未充分使用的 wrapper

- `initResourceUpload`, `uploadObject`, `completeResourceUpload`, `fetchCourseResources`, `deleteCourseResource`：工作台和本节资料未充分使用。
- `fetchLessonProgress`, `updateLessonProgress`：课时学习页未使用。
- `previewBilibiliImport`, `createBilibiliImport`, `fetchBilibiliImportRunStatus`, `cancelBilibiliImportRun`, `retryAsyncTask`：新建课时流程未使用。
- `fetchQaSessionMessages`：QA 页面未使用。
- `updateLesson`, `deleteLesson`, `reorderLessons`, `setLessonPrimaryVideo`, `mergeLessons`, `splitLesson`：Workbench 课时管理未使用。
- `fetchCourseReview`, `regenerateReviewTasks`, `fetchReviewRunStatus`, `completeReviewTask`：未接 quiz submit 的 existing run id。
- `fetchCourseLibrary` 参数：provider 未使用。
- `archive/restore/delete-impact`：后端已有，前端 wrapper 缺失。

---

## Functional requirements

## P0：主流程可信度必须补齐

### P0.1 课程工作台：上传课程资料

#### 用户故事

用户在课程工作台点击“上传资料”，可以上传课程级资料；在课时上下文中也可以上传/绑定课时级资料。上传完成后，资源立即出现在工作台或本节资料，并能参与后续 QA/讲义/测试/复习。

#### 当前代码现状

- 课程资料卡片按钮 `onPressed: _noop`。
- `CourseImportProvider` 已实现 file picker、checksum、upload-init、object PUT、upload-complete、refresh resources。
- `LessonPreparationPage` 已实现 lesson-scoped 上传。
- 后端 upload request/complete request 已支持 scope 字段。

#### 目标行为

课程级上传默认写入：

- `scopeType=course`
- `lessonId=null`
- `usageRole=course_material`
- `lessonPlacement=course_material`
- `visibleToCourseQa=true`

课时级上传默认写入：

- 非视频：`scopeType=lesson`, `lessonId=<current>`, `usageRole=lesson_material`
- 视频：`scopeType=lesson`, `lessonPlacement=bind_existing`, `lessonId=<current>`, `usageRole=primary_video`
- `visibleToCourseQa=false`，UI 可提供 opt-in。

#### 前端要求

- 不绕过 `ApiClient` / `CourseLessonApi`。
- 优先复用或抽取 `CourseImportProvider` 的上传链路。
- 上传状态包括选择中、队列为空、单文件上传中、单文件失败、全部成功、部分成功。
- 上传按钮在 active upload 时禁用或显示“上传中”。
- `upload-complete` 必须有稳定 idempotency key。
- 成功后 invalidate `courseWorkbenchProvider(courseId)`；lesson scope 下刷新 lesson detail。

#### 后端/API contract

已有可复用：

- `POST /api/v1/courses/{courseId}/resources/upload-init`
- object storage `PUT uploadUrl`
- `POST /api/v1/courses/{courseId}/resources/upload-complete`
- `GET /api/v1/courses/{courseId}/resources?scopeType=&lessonId=`
- `DELETE /api/v1/courses/{courseId}/resources/{resourceId}`

#### 状态处理

- Loading：队列和单项进度。
- Empty：无选择文件、无课程资料。
- Error：init/object upload/complete 任一步失败，保留失败 item。
- Retry：只重试失败 item。
- Success：刷新 workbench。
- Partial success：成功资源显示，失败资源保留。

#### 验收标准

- 工作台“上传资料”不再是空操作。
- 上传 PDF/DOCX/PPTX/SRT 后显示在课程资料卡片。
- 上传 lesson-scoped 文件后显示在该课时本节资料。
- 重复点击不创建重复资源。
- 失败可重试。
- 不破坏 CourseImportPage 既有上传流程。

---

### P0.2 课时学习进度持久化

#### 用户故事

用户离开课时学习页后再回来，应恢复到最近视频位置和讲义块；保存进度不能高频压后端。

#### 当前代码现状

- 视频初始化后 seek 到 `detail.positionSec`。
- `LessonStudyProvider` 能按 position 获取 current handout block。
- `ApiClient` / `CourseLessonApi` 已有 lesson progress GET/PUT。
- 播放中、暂停、离开页面没有保存。

#### 目标行为

- 进入页面时从 lesson detail/progress 恢复 `lastPositionSec`, `lastHandoutBlockId`, `handoutReadPercent`。
- 播放中 throttle/debounce 保存 `lastPositionSec`。
- current block 变化时保存 `lastHandoutBlockId`。
- 暂停和 dispose 时 flush。
- 跳转讲义块后保存 block id 与 position。
- 默认保存频率不超过每 10–15 秒一次，或 position delta 超过 15 秒/讲义块变化触发。

#### 前端要求

- 在 `lesson_study_provider.dart` 增加 progress save 方法，或新增 `lessonProgressControllerProvider(courseId, lessonId)`。
- 不在 widget build 中请求。
- video listener 只更新本地 state，不高频请求 API。
- PUT 失败不阻塞播放。
- dispose flush 处理 mounted/disposed 安全。

#### API contract

已有可复用：

- `GET /api/v1/courses/{courseId}/lessons/{lessonId}/progress`
- `PUT /api/v1/courses/{courseId}/lessons/{lessonId}/progress`

Request 关键字段：

- `lastPositionSec`
- `lastHandoutBlockId`
- `handoutReadPercent`
- `quizStatus`
- `reviewStatus`

Response 关键字段：

- `courseId`, `lessonId`, `lastPositionSec`, `lastHandoutBlockId`, `handoutReadPercent`, `quizStatus`, `reviewStatus`, `lastActivityAt`

#### 验收标准

- 播放 20 秒暂停后刷新，恢复到接近暂停位置。
- 点击讲义块后刷新，恢复到该 block。
- 连续播放 60 秒，PUT 次数符合 throttle。
- 后端错误不影响播放。
- 不破坏 lesson handout/outline/current-block 加载。

---

### P0.3 新建课时表单字段落库

#### 用户故事

用户填写学习目标、掌握程度、时间预算和来源信息后，这些字段应作为课时 metadata 持久化，后续可用于推荐、复习和 UI 展示。

#### 当前代码现状

- 弹窗展示 B 站链接、学习目标、掌握程度、时间预算、课时资料。
- 提交只发送 `title` 和 `sourceType: manual`。
- `LessonRepository.create_lesson` interface 已有 `meta_json` 参数，但 `CreateLessonRequest` 缺 `metaJson`。
- `UpdateLessonRequest` 已有 `metaJson`。

#### 目标行为

`CreateLessonRequest` backward-compatible 增加 optional `metaJson`。

新建课时提交时写入：

- `learningGoal`
- `initialMasteryLevel`
- `timeBudgetMinutes`
- `bilibiliSourceUrl`，仅用户填写时保留。

如果 B 站导入成功，`sourceType/sourceRefJson` 应反映 B 站来源；如果只是保存链接但未导入，则仍可 `sourceType=manual` 并在 `metaJson.bilibiliSourceUrl` 中保留。

#### 前端要求

- create lesson request 不得再忽略表单字段。
- 时间预算解析为正整数分钟；空值允许不传。
- 学习目标、掌握程度使用稳定 key，不依赖中文 label。
- 校验失败时阻止提交并显示错误。

#### 后端/API contract

已有但需扩展：

`POST /api/v1/courses/{courseId}/lessons`

Request 增加：

```json
{
  "title": "线性表基础",
  "sourceType": "manual",
  "sourceRefJson": null,
  "metaJson": {
    "learningGoal": "exam_review",
    "initialMasteryLevel": "beginner",
    "timeBudgetMinutes": 45,
    "bilibiliSourceUrl": "https://www.bilibili.com/video/..."
  }
}
```

Response：

- `lesson.metaJson` 可原样返回。
- 旧客户端不传 `metaJson` 时行为不变。

#### 验收标准

- 新建课时请求包含 `metaJson`。
- 后端保存并在 lesson detail 或 summary 返回。
- 不传 `metaJson` 的旧测试仍通过。
- 非法时间预算不发请求。

---

### P0.4 新建课时里的 B 站导入

#### 用户故事

用户在新建课时弹窗粘贴 B 站链接后，系统应 preview、创建导入任务、轮询导入状态，并把导入视频绑定到新建课时。

#### 当前代码现状

- 前端已有 B 站模型/provider。
- 后端已有 preview/import/auth/status/cancel。
- 新建课时表单的 B 站链接未使用。
- 前端 `BilibiliImportCreateRequestModel` 缺 `lessonMode`, `targetLessonId`, `partLessonMap`, `createLessonIfMissing`。

#### 目标行为

最小闭环：

1. 用户粘贴 B 站 URL。
2. 点击预览或提交时自动 preview。
3. 用户确认默认 part。
4. 前端先创建 lesson，带 `sourceType=bilibili_part` 或合理 B 站 source type，并写入 `sourceRefJson/metaJson`。
5. 创建 B 站 import：
   - `lessonMode=bind_existing`
   - `targetLessonId=<created lesson id>`
   - `createLessonIfMissing=false`
   - `selectionMode=current_part` 或 `selected_parts`
   - `selectedPartIds=[selected part]`
6. 轮询 import run status。
7. `imported` 后刷新 workbench/lesson，课时有 primary video resource。
8. 失败提供重试；可取消时提供取消。

#### 前端要求

- 扩展 `BilibiliImportCreateRequestModel`。
- 新建课时弹窗显示未登录/preview loading/error/success/importing/imported/failed/recoverable/canceled。
- 无登录态显示登录入口，不创建假任务。
- import create 带 idempotency key。
- 失败后保留已创建 lesson，retry 不重复创建 lesson。
- 多 P/合集复杂选择不在本轮弹窗内实现；需要时引导到完整导入页。

#### API contract

已有可复用：

- `GET /api/v1/bilibili/auth/session`
- `POST /api/v1/bilibili/auth/qr/sessions`
- `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`
- `DELETE /api/v1/bilibili/auth/session`
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview`
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili`
- `GET /api/v1/courses/{courseId}/resources/imports/bilibili`
- `GET /api/v1/bilibili-import-runs/{importRunId}/status`
- `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

#### 验收标准

- 新建课时填写 B 站 URL 后能 preview。
- 提交后创建 lesson，并创建 bind-existing import run。
- import 成功后 lesson 有 primary video resource。
- auth inactive 时 UI 明确提示登录。
- recoverable run 可重试且不重复创建课时。
- 本地文件新建流程不受影响。

---

### P0.5 复习功能接入收尾

#### 用户故事

用户完成测验后，系统应根据测验结果生成或刷新复习任务；进入复习中心能看到任务生成状态、任务列表，并可回到讲义、进入测试、标记完成并刷新统计。

#### 当前代码现状

- `QuizProvider.submit` 会解析 `reviewTaskRunId` 并写入 `CourseFlow`。
- `ReviewProvider.regenerateAndPoll` 能主动创建 review run、轮询并刷新 review。
- `ReviewPage` 能展示 read model、回讲义、进测试、标记完成。
- `ReviewPage` 初始化只 `load(courseId)`，未消费 existing `reviewTaskRunId`。
- `ReviewPage` regenerate 调用传了 `Duration(milliseconds: 20)`，不适合作为生产默认。

#### 目标行为

- Quiz submit 后，若 `reviewTaskRunId != null`，写入 CourseFlow，并显示进入复习中心 CTA。
- ReviewPage 进入时，若 route query 或 CourseFlow 有 pending run id：
  - 调 `fetchReviewRunStatus(reviewTaskRunId)` 轮询到 terminal。
  - terminal 后调 `fetchCourseReview(courseId)`。
  - 不自动调用 regenerate。
- 若 run id 为空，只加载 `fetchCourseReview(courseId)`。
- 手动“重新生成复习”继续使用 existing regenerate flow。
- 生产默认轮询间隔 2 秒；测试通过参数/override 使用短间隔。

#### 前端要求

- `ReviewProvider` 增加 `pollExistingRunAndLoad(courseId, reviewTaskRunId)`。
- `ReviewPage` on init 检查 query `runId` 和 `courseFlowProvider.reviewTaskRunId`。
- 成功处理 run 后清理或标记 consumed。
- `QuizPage` review CTA 可携带 `?runId=<id>`，但不得只依赖 query。

#### API contract

已有可复用：

- `POST /api/v1/quizzes/{quizId}/submit`
- `GET /api/v1/review-task-runs/{reviewTaskRunId}/status`
- `GET /api/v1/courses/{courseId}/review`
- `POST /api/v1/review-tasks/{reviewTaskId}/complete`
- `POST /api/v1/courses/{courseId}/review-tasks/regenerate`

#### 验收标准

- quiz submit 后进入 review page 会先显示生成状态再显示 review tasks。
- `reviewTaskRunId=null` 时正常加载空态或已有 read model。
- 手动重新生成仍可用。
- 标记完成后统计刷新。
- 回讲义能定位 linked handout block。
- 不重写复习后端。

---

## P1：已露出 UI，但体验/状态不完整

### P1.6 课程库搜索、筛选、排序

目标：把静态 `_InsetField` 改为真实控件，驱动 `GET /api/v1/courses?q=&learningStatus=&source=&archived=&sort=`。

前端要求：

- 新增 `CourseLibraryQueryState`。
- `courseLibraryProvider` 改为 family 或 query 派生 provider。
- 搜索输入 debounce。
- 支持 loading、empty、error、retry、clear filters。
- 删除/归档/恢复成功后 invalidate 当前查询。

验收标准：

- 输入关键词调用带 `q` 的 API。
- 切换状态/source/sort/archived 调用对应 query。
- 空结果不显示旧数据。
- `archived=only` 能显示归档课程。

---

### P1.7 QA 会话历史

目标：课程级和课时级 QA 能显示 session list、读取历史消息、继续历史 session。

前端要求：

- 新增 `QaSessionModel`。
- 丰富 `QaMessageModel`，支持 `question`, `answerMd`, `createdAt`, `citations`, `messageId`, `sessionId`。
- 新增 `qaSessionsProvider(QaScopeArgs)` 和 `qaSessionMessagesProvider(sessionId)`。
- active session 使用 provider state，不再只存在 widget local map。
- 发送消息带 active `sessionId`。

后端要求：

- `GET /api/v1/qa/sessions/{sessionId}/messages` 必须返回 question；若当前 repository 丢失该字段，扩展 response。

验收标准：

- 课程 QA 和课时 QA 各自列出历史 session。
- 点击 session 能恢复 question + answer 历史。
- 继续提问复用原 session id。
- 新建会话创建新 session。
- scope 不串。

---

### P1.8 课时学习页 AI 问答展示

目标：内嵌 QA 显示用户问题、AI 回答、引用、失败重试。

前端要求：

- `lesson_study_state.dart` 新增或替换为 `qaExchangesByBlockId`。
- exchange 包含 `localId`, `question`, `answer`, `status`, `errorText`, `sessionId`, `handoutBlockId`。
- `askQuestion` optimistic append question/pending answer，再更新结果。
- retry 不重复 append question。

验收标准：

- 发送后立即显示用户问题。
- 回答生成中显示 pending。
- 成功后显示 answer/citations。
- 失败后可 retry。
- 切换 block 时只显示该 block 的 QA。

---

### P1.9 本节资料弹窗

目标：本节资料弹窗从只读列表变为可操作入口。

最小闭环：

- 展示文件名、类型、usage role、scope、是否参与课程 QA。
- 支持刷新。
- 支持删除，删除前确认，成功后刷新 lesson detail，409 blocker 显示错误。
- 支持 mp4 预览，通过 existing playback endpoint。
- 非视频若无 download endpoint，UI 显示 disabled 和明确提示。

增强项：

- 新增 `GET /api/v1/course-resources/{resourceId}/download`。
- 新增 `PATCH /api/v1/courses/{courseId}/resources/{resourceId}`，支持 `scopeType`, `lessonId`, `usageRole`, `visibleToCourseQa`, `sortOrder`。

验收标准：

- 弹窗不再只读。
- 删除 lesson-scoped 资料成功后列表刷新。
- blocker 显示 409 错误。
- mp4 可获取 playback URL。
- 下载/toggle/rebind 若实现，必须有测试；若不实现，必须明确 disabled。

---

### P1.10 课时管理入口

目标：Workbench 课时卡片提供管理菜单，不破坏继续学习入口。

MVP：

- 重命名。
- 删除。
- 上移/下移排序。

增强：

- 合并相邻课时。
- 按时间点拆分。
- 设置主视频。

前端要求：

- 管理入口与“继续学习”分离。
- 删除前确认。
- 排序可用 up/down，不强制拖拽。
- 合并只允许相邻课时。
- 拆分只在有 primary video 时可用。
- 设置主视频只列出当前课程 mp4 resources。
- `setLessonPrimaryVideo` request 中 `resourceId` 应为 int。

验收标准：

- 重命名、删除、排序持久化。
- 合并非相邻时 UI 阻止或后端 409 可读。
- 拆分非法时间点可读提示。
- 设置主视频后课时学习页能播放。
- 继续学习仍进入 lesson handout。

---

## P2：体验一致性和管理能力

### P2.11 课程测试历史

目标：新增课程 quiz history 列表，Workbench “历史课程测试”不再跳当前 quiz 页。

需要新增 API：

`GET /api/v1/courses/{courseId}/quizzes`

Query：

- `scopeType?=course|lesson`
- `lessonId?`
- `status?`
- `limit?`
- `cursor?` 可后续；MVP 可无 cursor。

Response item：

- `quizId`
- `courseId`
- `scopeType`
- `lessonId`
- `status`
- `quizMode`
- `questionCount`
- `createdAt`
- `updatedAt`
- `latestAttempt.attemptId`
- `latestAttempt.score`
- `latestAttempt.totalScore`
- `latestAttempt.accuracy`
- `latestAttempt.submittedAt`

前端要求：

- 新增 `QuizHistoryPage` 或 history mode；推荐独立页面。
- 新增 `/courses/:courseId/quizzes` route。
- 点击 history item 进入 `/quizzes/:quizId`。

验收标准：

- 历史按钮进入 history 页面。
- 能列出当前课程生成过的 quiz。
- 点击 item 进入 detail。
- 无历史时显示空态。

---

### P2.12 “重新生成课程测试”语义

推荐实现真实 regenerate：

- Workbench 按钮进入 `/courses/{courseId}/quiz?regenerate=1`。
- Router/QuizPage 识别 `autoRegenerate`。
- 首次进入后只触发一次 `generateAndPoll(courseId)`。
- 普通“开始课程测试”进入 `/courses/{courseId}/quiz`，不自动生成。

验收标准：

- 点击“重新生成课程测试”调用 generate API。
- 普通进入 quiz 不自动生成。
- rebuild 不重复 generate。
- lesson quiz 不受影响。

---

### P2.13 课程删除影响确认

目标：删除前展示真实 impact，不再使用固定文案。

前端要求：

- `ApiClient` / `CourseLessonApi` 增加 `fetchCourseDeleteImpact`。
- 新增 `CourseDeleteImpactModel`，兼容 flat counts 与 `counts` map。
- 删除 dialog loading impact 时显示 loading。
- 多选删除展示 aggregate counts 和每门课程详情。
- 删除支持部分成功/失败。

后端 response 建议锁定：

- `courseId`
- `canDelete`
- `counts.lessons/resources/progressRecords/qaSessions/quizzes/quizAttempts/reviewTasks/artifacts`
- `blockers`

验收标准：

- 删除确认 dialog 显示真实 impact。
- impact 请求失败时不能直接删除。
- 多选删除部分失败时成功项移除、失败项有错误。
- 409 blocker 可读。

---

### P2.14 课程归档 / 恢复

目标：课程可归档、查看归档、恢复。

前端要求：

- `ApiClient` / `CourseLessonApi` 增加 `archiveCourse`, `restoreCourse`。
- 课程库筛选支持 `archived=exclude|include|only`。
- 课程卡片显示“已归档”和恢复按钮。
- 归档/恢复成功后 invalidate 当前查询。
- 当前 active course 被归档时清理 active state 或提示选择其他课程。

验收标准：

- 归档后默认列表不显示该课程。
- `archived=only` 能看到归档课程。
- 恢复后回到默认列表。
- 归档/恢复失败不改变本地状态。

---

## Data/API contracts

| API | 状态 | 用途 | 本轮动作 |
|---|---|---|---|
| `GET /api/v1/courses` | 已有 | 课程库 query | 接前端筛选。 |
| `GET /api/v1/courses/{courseId}/delete-impact` | 已有后端，前端缺 | 删除确认 | 加 wrapper/model/dialog。 |
| `POST /api/v1/courses/{courseId}/archive` | 已有后端，前端缺 | 归档 | 加 wrapper/UI。 |
| `POST /api/v1/courses/{courseId}/restore` | 已有后端，前端缺 | 恢复 | 加 wrapper/UI。 |
| `DELETE /api/v1/courses/{courseId}` | 已有 | 删除课程 | 删除前先 impact。 |
| `GET /api/v1/courses/{courseId}/workbench` | 已有 | 工作台 read model | mutation 后 invalidate。 |
| `POST /api/v1/courses/{courseId}/resources/upload-init` | 已有 | 上传初始化 | 工作台上传复用。 |
| object PUT | 已有 | 上传对象 | 复用 `uploadObject`。 |
| `POST /api/v1/courses/{courseId}/resources/upload-complete` | 已有 | 资源落库 | 工作台上传复用。 |
| `GET /api/v1/courses/{courseId}/resources` | 已有 | 资源列表 | 本节资料刷新。 |
| `DELETE /api/v1/courses/{courseId}/resources/{resourceId}` | 已有 | 删除资源 | 本节资料删除。 |
| `GET /api/v1/course-resources/{resourceId}/playback` | 已有 | 视频播放 | mp4 预览。 |
| `GET /api/v1/course-resources/{resourceId}/download` | 需要新增 | 非视频下载 | P1 增强。 |
| `PATCH /api/v1/courses/{courseId}/resources/{resourceId}` | 需要新增 | 重绑定/QA 可见性 | P1 增强。 |
| `POST /api/v1/courses/{courseId}/lessons` | 已有但需扩展 | 新建课时 | 加 optional `metaJson`。 |
| `PATCH /api/v1/courses/{courseId}/lessons/{lessonId}` | 已有 | 重命名/更新 | 管理入口使用。 |
| `DELETE /api/v1/courses/{courseId}/lessons/{lessonId}` | 已有 | 删除课时 | 管理入口使用。 |
| `POST /api/v1/courses/{courseId}/lessons/reorder` | 已有 | 排序 | 管理入口使用。 |
| `POST /api/v1/courses/{courseId}/lessons/merge` | 已有 | 合并 | 管理入口使用。 |
| `POST /api/v1/courses/{courseId}/lessons/{lessonId}/split` | 已有 | 拆分 | 管理入口使用。 |
| `POST /api/v1/courses/{courseId}/lessons/{lessonId}/primary-video` | 已有 | 设置主视频 | 修正前端 request 类型。 |
| `GET /api/v1/courses/{courseId}/lessons/{lessonId}/progress` | 已有 | 读取课时进度 | 课时学习恢复。 |
| `PUT /api/v1/courses/{courseId}/lessons/{lessonId}/progress` | 已有 | 保存课时进度 | debounce/flush。 |
| B 站 auth/preview/import/status/cancel | 已有 | B 站导入 | 新建课时接入。 |
| QA sessions/messages | 已有但需核实字段 | QA history | 若 messages 缺 question，扩展。 |
| `POST /api/v1/courses/{courseId}/quizzes/generate` | 已有 | 课程 quiz 生成 | regenerate 语义。 |
| `GET /api/v1/courses/{courseId}/quizzes` | 需要新增 | quiz history | P2 实现。 |
| `GET /api/v1/quizzes/{quizId}` | 已有 | quiz detail | history 打开。 |
| `POST /api/v1/quizzes/{quizId}/submit` | 已有 | quiz submit | review run closure。 |
| `GET /api/v1/review-task-runs/{reviewTaskRunId}/status` | 已有 | review run status | quiz submit 后使用。 |
| `GET /api/v1/courses/{courseId}/review` | 已有 | review read model | review 展示。 |
| `POST /api/v1/review-tasks/{reviewTaskId}/complete` | 已有 | 标记完成 | refresh stats。 |

---

## State management

### Provider 组织

- Course library：新增 `courseLibraryQueryProvider` 和参数化 `courseLibraryProvider(query)`。
- Workbench upload：新增或抽取 `resourceUploadControllerProvider(scope)`，上传成功后 invalidate workbench/lesson。
- Lesson study：继续使用 `LessonStudyProvider`，增加 progress save state 和 QA exchange state。
- New lesson/Bilibili：表单字段可本地 state；B 站状态复用/扩展 `BilibiliImportProvider`；已创建 lesson id/import run id 必须保存在 flow state，避免 retry 重复创建。
- QA history：新增 `qaSessionsProvider(QaScopeArgs)`、`qaMessagesProvider(sessionId)`，active session 属于 provider state。
- Quiz/Review：`CourseFlowProvider` 继续保存 active course/lesson/quiz/attempt/reviewTaskRunId；`ReviewProvider` 增加 poll existing run。

### 本地 UI 状态

以下允许保持页面本地：弹窗输入、搜索框 debounce 前文本、dialog open、展开菜单、多选临时选择、snackbar/error banner。

### 必须后端持久化

课程归档/删除、资源、课时 metadata、B 站 import run/items、课时进度、QA session/message、quiz attempt、review task run/tasks/completion、课时排序/合并/拆分/主视频。

### Active state 同步

- 进入 `/courses/:courseId/**`：`courseFlowProvider.startCourse(courseId)`。
- 进入 lesson route：设置 `activeLessonProvider`。
- review → handout：设置 `activeBlockProvider` 和 `handoutResumeTargetProvider`。
- quiz submit：设置 `quizAttemptId` 和 `reviewTaskRunId`。
- review run terminal：标记 consumed 或清理 run id。
- active course 被归档/删除：清理 active state 或跳回课程库。

---

## Testing requirements

### Flutter provider tests

- Workbench upload：init → uploadObject → complete → refresh；失败 retry；idempotency。
- Lesson progress：debounce PUT、pause flush、dispose flush、block change save。
- Create lesson metadata：字段进入 request；非法预算不请求。
- Bilibili lesson import：preview、auth inactive、bind-existing import、recoverable retry 不重复 lesson。
- Review closure：quiz submit run id → ReviewProvider poll existing run → fetch review。
- Course library query：q/status/source/archived/sort 参数正确。
- QA history：session list、messages、continue session。
- Quiz regenerate：auto regenerate 只触发一次。

### Flutter widget tests

- CourseLibraryPage：筛选控件、delete impact dialog、archive/restore。
- CourseWorkbenchPage：上传按钮、新建课时 metadata、B 站状态、课时管理 menu、quiz history/regenerate。
- LessonStudyPage：进度恢复/保存 hook、QA pair、本节资料操作。
- CourseQaPage：session list、点击 session、继续历史。
- ReviewPage：existing run polling、complete refresh、回讲义/进测试。

### Backend tests

- Lesson create `metaJson` optional/persist/return。
- Resource download/PATCH if implemented。
- Course delete-impact/archive/restore/list archived。
- Quiz history list and latest attempt。
- QA session messages include question and scope isolation。
- Lesson progress upsert。
- Bilibili bind-existing validation and retry no duplicate lesson。
- Review run status and complete semantics。

### 必须跑的命令

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

### 手工验收路径

1. 打开课程工作台，上传课程级 PDF，确认课程资料出现。
2. 新建课时，填写目标/掌握程度/时间预算并上传文件，确认字段落库、资料绑定、讲义生成。
3. 新建课时填写 B 站链接，完成 preview/import/poll，确认 primary video 可播放。
4. 进入课时学习，播放 20 秒暂停，刷新后恢复位置。
5. 点击讲义块跳转，刷新后恢复 block。
6. 课时学习页提问，确认 question + answer + citation。
7. 打开本节资料，删除资料，确认刷新和错误处理。
8. 完成 quiz，进入 review，确认 run polling、任务展示、回讲义、进测试、标记完成。
9. 课程库搜索/筛选/排序，归档/恢复课程。
10. 删除课程前查看 impact，再确认删除。
11. 打开课程测试历史，进入历史 quiz detail。
12. 点击“重新生成课程测试”，确认真实生成。

---

## Risks and constraints

- 幂等性：upload-complete、B 站 create import、quiz generate、review regenerate 都必须带 idempotency key。
- 重复点击：所有 mutation button 需要 disabled/loading。
- 轮询：必须有 terminal 判断和 maxAttempts；生产 interval 不低于 1–2 秒。
- 进度保存：不得每 tick 请求后端；pause/dispose flush 要去重。
- 旧数据兼容：`metaJson` optional；历史 QA 缺 question 时要 fallback 或 migration；`archivedAt=null` 表示未归档。
- 空状态兼容：无课程、无课时、无资源、无主视频、无 handout、无 quiz、无 review task、无 QA session、B 站未登录、`reviewTaskRunId=null`。
- 测试环境：file picker、video player、object storage、B 站外部请求必须 mock/fake。
