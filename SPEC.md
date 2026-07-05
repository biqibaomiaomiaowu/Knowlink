# SPEC.md

## Overview

### 当前分支现状

目标仓库为 `biqibaomiaomiaowu/Knowlink`，目标分支为 `codex/rerecreate`，基准分支为 `main`。`codex/rerecreate` 已经完成大量 Flutter 高保真页面、前端模型、provider、API wrapper 和部分后端/contract 对齐；当前剩余问题主要不是“从零开发后端”，而是前端已露出入口、API wrapper 已存在或后端 contract 已存在，但未完成真实闭环。

已核实的核心断点：

- `CourseWorkbenchPage` 课程级“上传资料”按钮仍是 noop。
- 新建课时弹窗展示 B 站链接、学习目标、掌握程度、时间预算，但提交只传 `title/sourceType`。
- `LessonStudyPage` 能从 lesson detail 恢复 `positionSec`，但未稳定保存播放位置、当前讲义块和阅读进度。
- B 站 preview/import/auth/status/cancel/retry 能力已有，但未接入新建课时流程。
- quiz submit 能取得 `reviewTaskRunId` 并写入 `CourseFlow`，但 `ReviewPage` 未消费该 run id 轮询并刷新 read model。
- 课程库搜索/筛选/排序 UI 是静态展示。
- QA 页面可发消息，但 session list、history messages、continue session 未闭环。
- 课时学习页内嵌 AI QA 只展示 answer，不展示用户 question。
- 本节资料弹窗只读展示。
- 后端和 wrapper 已有课时更新、删除、排序、合并、拆分、设置主视频能力，但 workbench 课时卡片缺管理入口。
- Workbench “历史课程测试”和“重新生成课程测试”语义不完整。
- 后端已有课程 `delete-impact`、`archive`、`restore`，前端未接入。

### 本轮目标

本轮目标是前后端接入收尾，并尽量通过并行 lanes 缩短完成时间：

1. P0：补齐主流程可信度：课程/课时资料上传、课时进度持久化、新建课时字段落库、B 站导入、复习闭环。
2. P1：补齐已露出 UI 的真实交互：课程库筛选、QA 历史、课时 AI QA、本节资料弹窗、课时管理入口。
3. P2：补齐体验一致性和管理能力：quiz history、重新生成语义、删除影响确认、归档/恢复。
4. 用依赖门禁和文件所有权拆分并行工作；同一高冲突文件不得由多个 Codex goal 同时修改。
5. 复用现有 `ApiClient`、`CourseLessonApi`、Riverpod provider、FastAPI service/repository 分层。
6. 所有新增字段/API 同步 `docs/contracts/*.md`。
7. 所有新增行为必须有 Flutter provider/widget tests 和后端 API/service/repository tests。

### Non-goals

Codex 本轮不得实现：

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

`/courses/:courseId/handout` 只允许保留为兼容入口：有 active lesson 时跳到 lesson handout，否则提示选择课时。

---

## Parallel execution model

### 总体结论

这些任务可以并行，但不能按 P0/P1/P2 线性整段并行。最短安全路径是：

1. Phase 0 必须串行完成 contract lock 和测试基线。
2. 之后按文件所有权拆成 6 条 lane 并行推进。
3. 每条 lane 内部对同一文件的任务串行。
4. 跨 lane 只在明确定义的 integration checkpoints 合并。
5. 所有 lane 通过各自 targeted tests 后，再跑全量 regression。

### 推荐并行 lanes

| Lane | Owner scope | 可并行原因 | 主要冲突文件 | 内部顺序 |
|---|---|---|---|---|
| A. Backend contract lane | 后端 schema/service/repository/docs | 多数前端交互依赖 contract，但可先由后端 lane 单独落地 | `interfaces.py`, `memory_runtime.py`, `sqlalchemy.py`, `docs/contracts/*` | `metaJson` → QA message question audit → resource PATCH/download → quiz history |
| B. Workbench lane | `course_workbench_page.dart`、workbench upload、新建课时、B 站、课时管理、quiz buttons | 工作台相关 UI 高冲突，应一个 lane 串行处理 | `course_workbench_page.dart`, `course_workbench_provider.dart` | upload → lesson metadata frontend → B 站 import → lesson management → quiz button semantics |
| C. Lesson study lane | `lesson_study_provider.dart`、`lesson_study_page.dart` | 进度、嵌入 QA、本节资料都改同一页面，应 lane 内串行 | `lesson_study_provider.dart`, `lesson_study_page.dart`, `lesson_study_state.dart` | progress → embedded QA pair → materials dialog |
| D. Course library lane | 课程库 query、delete-impact、archive/restore | 主要集中课程库页面/provider；可和 Workbench/LessonStudy 并行 | `course_library_page.dart`, `course_library_provider.dart` | search/filter/sort → delete-impact → archive/restore |
| E. QA page lane | `course_qa_page.dart`、QA history providers | 与 lesson embedded QA 只共享模型，页面冲突少 | `handout_models.dart` if model extended | session models/providers → page refactor → continue session |
| F. Quiz/Review lane | quiz submit review closure、quiz history、regenerate semantics | 与 Workbench lane 会在 quiz buttons/router 有冲突，需 checkpoint | `quiz_page.dart`, `quiz_provider.dart`, `review_provider.dart`, `review_page.dart`, `app_router.dart` | review closure → quiz history backend/frontend → auto regenerate |

### 不能并行的组合

| 不可并行组合 | 原因 | 处理方式 |
|---|---|---|
| Workbench upload、create lesson metadata frontend、B 站 dialog、lesson management | 都高频修改 `course_workbench_page.dart` | 归入 Workbench lane 串行。 |
| Lesson progress、embedded QA、本节资料弹窗 | 都修改 `lesson_study_provider.dart` / `lesson_study_page.dart` | 归入 Lesson study lane 串行。 |
| Course library filters、delete-impact、archive/restore | 都修改 `course_library_page.dart` / provider | 归入 Course library lane 串行。 |
| Quiz history frontend 与 regenerate semantics | 都修改 router/quiz/workbench buttons | 放在 Quiz/Review lane，或等 Workbench lane 合并后处理按钮。 |
| 后端多个 contract 同时修改 `interfaces.py` / `sqlalchemy.py` | repository interface/SQL adapter 文件冲突高 | Backend lane 内串行，或拆 branch 后由单一 integrator 合并。 |

### 并行 checkpoint

- **Checkpoint 0：Baseline lock**。跑基线测试，冻结 contract delta。之后才能开并行 lane。
- **Checkpoint 1：Backend contract ready**。`metaJson`、QA history message 字段、resource PATCH/download、quiz history API 至少完成 contract 和后端 tests。依赖这些 API 的前端 lane 才能进入最终 wiring。
- **Checkpoint 2：Frontend lane integration**。Workbench/LessonStudy/CourseLibrary/QA/QuizReview 各自 targeted tests 通过。
- **Checkpoint 3：Cross-lane regression**。跑完整 `python -m pytest`、`flutter analyze`、`flutter test`。

### 并行执行约束

- 每个 Codex goal 必须声明 allowed/disallowed files。
- 同一时间不得有两个 goal 修改同一个高冲突文件。
- 如果 goal 必须改共享文件，例如 `api_client.dart`，优先由 lane owner 增加 wrapper；其他 lane 只调用已存在 wrapper。
- 如果需要并行修改共享 backend adapters，必须先拆最小 commits，再由 integrator rebase/merge。
- 每个 lane 完成后必须运行 targeted tests，不得等最终总测才发现问题。

---

## Source of truth

### 前端已露出入口

| 区域 | 文件 | 当前状态 | 本轮处理 |
|---|---|---|---|
| 路由 | `client_flutter/lib/app/router/app_router.dart` | 已有课程库、工作台、课时学习、课程/课时 quiz、QA、review、graph、exports 路由；`/courses/:courseId/handout` 是兼容页。 | 保留路由体系，只做必要 query/path 扩展。 |
| 全局框架 | `client_flutter/lib/core/widgets/app_scaffold.dart` | 依据 active course/lesson 控制导航。 | 不重写。 |
| 课程库 | `client_flutter/lib/features/course_library/course_library_page.dart` | 搜索/状态/排序是静态 `_InsetField`；删除确认固定文案；无归档/恢复。 | Course library lane。 |
| 课程库 provider | `client_flutter/lib/shared/providers/course_library_provider.dart` | 无参数 `FutureProvider`，默认 `fetchCourseLibrary()`。 | 增加 query state/family provider。 |
| 课程工作台 | `client_flutter/lib/features/course_workbench/course_workbench_page.dart` | 上传 noop；quiz 按钮语义不完整；课时卡片缺管理入口。 | Workbench lane 串行。 |
| 新建课时弹窗 | `course_workbench_page.dart` | 表单字段多，但提交只传 `title` 和 `sourceType: manual`。 | Workbench lane + Backend contract lane。 |
| 准备课时页 | `LessonPreparationPage` | 已能上传 lesson-scoped 文件、parse、generate lesson handout、轮询后进入课时学习。 | 复用，不重写。 |
| 课时学习页 | `client_flutter/lib/features/lesson_study/lesson_study_page.dart` | 能加载视频/讲义/当前块；未保存进度；资料只读；AI QA 只显示回答。 | Lesson study lane 串行。 |
| QA 页面 | `client_flutter/lib/features/course_qa/course_qa_page.dart` | 可发消息，session id 仅本地。 | QA page lane。 |
| Quiz/Review | `quiz_page.dart`, `quiz_provider.dart`, `review_page.dart`, `review_provider.dart` | quiz submit 已拿 run id；ReviewPage 不消费；history/regenerate 不完整。 | Quiz/Review lane。 |
| Resource upload | `resource_upload_models.dart`, `course_import_provider.dart` | CourseImportPage 已有完整上传链路。 | Workbench lane 复用/抽取。 |
| B 站导入 | `bilibili_import_provider.dart`, `bilibili_import_models.dart` | 已有 auth/preview/import/status/cancel/retry；前端 create request 缺 bind-existing 字段。 | Workbench lane。 |

### 后端已有 contract

| 能力 | 文件 | 状态 |
|---|---|---|
| 课程库查询 | `server/api/routers/courses.py`, `server/domain/services/courses.py` | `GET /courses` 已支持 `q`, `learningStatus`, `source`, `archived`, `sort`。 |
| 删除影响 | `courses.py`, `CourseService.get_course_delete_impact` | `GET /courses/{courseId}/delete-impact` 已存在。 |
| 归档/恢复 | `courses.py`, `CourseService.archive_course/restore_course` | `POST /archive`, `POST /restore` 已存在。 |
| 分层资源上传 | `resources.py`, resource service, requests schema | upload-init/upload-complete/list/delete/playback 已存在。 |
| 课时管理 | `lessons.py`, `LessonService` | create/update/delete/reorder/merge/split/primary-video 已存在。 |
| 课时进度 | `progress.py`, `ProgressService` | `GET/PUT /courses/{courseId}/lessons/{lessonId}/progress` 已存在。 |
| B 站导入 | `bilibili.py`, `BilibiliService`, requests schema | preview/create/list/status/cancel/auth 已存在；后端 request 支持 bind-existing 字段。 |
| QA | `qa.py`, `QaService` | course/lesson session list、create message、session messages 已存在。 |
| Quiz | `quizzes.py` | generate/detail/status/submit 已存在；缺 course quiz history list。 |
| Review | `reviews.py`, review service/repository/tasks | course/lesson review、review-tasks regenerate、run status、complete 已存在。 |
| Contract docs | `docs/contracts/v2-course-lesson-workbench-contract.md` | 多数 V2 contract 已记录，需补本轮新增/扩展字段和并行执行边界。 |

---

## Functional requirements

## P0：主流程可信度必须补齐

### P0.1 课程工作台：上传课程资料

- **Lane**：Workbench lane。
- **用户故事**：用户在课程工作台点击“上传资料”后，可以上传课程级资料；在课时上下文可以上传/绑定课时级资料。上传完成后，资源立即出现在工作台或本节资料。
- **当前现状**：课程资料卡片按钮为 `_noop`；`CourseImportProvider` 已有完整上传链路；`LessonPreparationPage` 已有 lesson-scoped 上传。
- **目标行为**：课程级默认 `scopeType=course`, `lessonId=null`, `usageRole=course_material`, `lessonPlacement=course_material`, `visibleToCourseQa=true`；课时级默认 `scopeType=lesson`, `lessonId=<current>`, 视频使用 `lessonPlacement=bind_existing`, `usageRole=primary_video`。
- **前端要求**：复用或抽取上传链路；不绕过 `ApiClient` / `CourseLessonApi`；上传状态包含 pending/loading/error/retry/success/partial success；成功后刷新 workbench/lesson。
- **API**：复用 `upload-init`、object PUT、`upload-complete`、resource list/delete。
- **验收标准**：按钮不再 noop；课程级和课时级资源可落库展示；失败可重试；不破坏 CourseImportPage。

### P0.2 课时学习进度持久化

- **Lane**：Lesson study lane。
- **用户故事**：离开课时学习页后再回来，恢复最近视频位置和讲义块；保存不高频压后端。
- **当前现状**：能从 detail 恢复 position，但播放中/暂停/dispose 不保存。
- **目标行为**：进入时恢复 `lastPositionSec`, `lastHandoutBlockId`, `handoutReadPercent`；播放中 throttle/debounce 保存；暂停和 dispose flush；block jump 保存 block/position。
- **前端要求**：不在 build 中请求；video listener 只更新本地 state；PUT 失败不阻塞播放；默认不超过每 10–15 秒一次。
- **API**：复用 `GET/PUT /courses/{courseId}/lessons/{lessonId}/progress`。
- **验收标准**：播放 20 秒暂停刷新后恢复；block jump 刷新后恢复；60 秒播放 PUT 次数符合 throttle。

### P0.3 新建课时表单字段落库

- **Lane**：Backend contract lane + Workbench lane。
- **用户故事**：新建课时时填写学习目标、掌握程度、时间预算和来源信息，这些字段应持久化。
- **当前现状**：UI 展示字段，提交只发送 `title/sourceType`；repository interface 已有 `meta_json`，schema 缺 `metaJson`。
- **目标行为**：`CreateLessonRequest` optional 增加 `metaJson`；前端写入 `learningGoal`, `initialMasteryLevel`, `timeBudgetMinutes`, `bilibiliSourceUrl?`。
- **后端要求**：schema/service/repository memory/sqlalchemy 保存并返回 `lesson.metaJson`；旧请求不传仍可用。
- **验收标准**：请求包含 metadata；后端返回 metadata；非法时间预算不请求；旧测试通过。

### P0.4 新建课时里的 B 站导入

- **Lane**：Workbench lane；依赖 Backend contract lane 对 bind-existing 行为完成审计。
- **用户故事**：新建课时粘贴 B 站链接后，系统 preview、创建 import run、轮询并绑定视频到该课时。
- **当前现状**：B 站 provider/API 已有，但弹窗未使用；前端 create request model 缺 bind-existing 字段。
- **目标行为**：preview → create lesson once → create import with `lessonMode=bind_existing`, `targetLessonId`, `createLessonIfMissing=false` → poll → imported 后刷新 workbench/lesson。
- **状态**：未登录、preview loading/error/success、importing、imported、failed、recoverable、canceled。
- **验收标准**：可 preview；import 成功后 lesson 有 primary video；无登录态不创建假任务；retry 不重复创建 lesson。

### P0.5 复习功能接入收尾

- **Lane**：Quiz/Review lane。
- **用户故事**：quiz submit 后，review page 根据 `reviewTaskRunId` 展示生成状态并刷新复习任务。
- **当前现状**：QuizProvider 写入 run id；ReviewPage 不消费。
- **目标行为**：ReviewPage 读取 query `runId` 或 CourseFlow run id，调用 `fetchReviewRunStatus` 轮询，terminal 后 `fetchCourseReview`；无 run id 时正常 load；手动 regenerate 保持独立。
- **约束**：不自动 regenerate；生产轮询 interval 2 秒；测试可 override。
- **验收标准**：submit 后进入 review 会 poll existing run；`reviewTaskRunId=null` 正常空态；mark complete 刷新统计。

---

## P1：已露出 UI，但体验/状态不完整

### P1.6 课程库搜索、筛选、排序

- **Lane**：Course library lane。
- **目标**：静态 `_InsetField` 改为真实控件，驱动 `GET /courses?q=&learningStatus=&source=&archived=&sort=`。
- **要求**：新增 query state/family provider；搜索 debounce；loading/empty/error/retry；筛选变化清理不可见 selection。
- **验收**：query 参数正确；空结果不显示旧数据；`archived=only` 能显示归档课程。

### P1.7 QA 会话历史

- **Lane**：QA page lane；依赖 Backend contract lane 对 message question 字段审计。
- **目标**：课程级/课时级 QA 显示 session list、读取历史消息、继续历史 session。
- **要求**：新增 `QaSessionModel`；扩展 `QaMessageModel` 支持 question；新增 session/messages providers；active session 用 provider state。
- **验收**：session list 加载；点击 session 显示 question+answer；继续提问复用 session id；scope 不串。

### P1.8 课时学习页 AI 问答展示

- **Lane**：Lesson study lane。
- **目标**：嵌入 QA 展示用户问题、AI 回答、引用、失败重试。
- **要求**：新增 `qaExchangesByBlockId`；optimistic question + pending answer；retry 不重复 append。
- **验收**：问题立即可见；pending/success/error/retry 状态完整；按 block 分组。

### P1.9 本节资料弹窗

- **Lane**：Lesson study lane；增强项依赖 Backend contract lane resource PATCH/download。
- **最小闭环**：展示资料详情、刷新、删除、mp4 playback 预览；非视频 download 未实现时明确 disabled。
- **增强项**：新增 generic download endpoint；新增 resource PATCH，支持 rebind/visibleToCourseQa。
- **验收**：删除成功刷新；409 blocker 可读；mp4 获取 playback URL；增强项如实现必须有测试。

### P1.10 课时管理入口

- **Lane**：Workbench lane。
- **MVP**：重命名、删除、上移/下移排序。
- **增强**：合并相邻课时、按时间拆分、设置主视频。
- **要求**：管理入口与继续学习分离；合并只允许相邻课时；设置主视频只列当前课程 mp4 resources；`resourceId` 用 int。
- **验收**：rename/delete/reorder 持久化；merge/split/primary-video 有错误处理；继续学习不破坏。

---

## P2：体验一致性和管理能力

### P2.11 课程测试历史

- **Lane**：Quiz/Review lane + Backend contract lane。
- **目标**：新增 `GET /api/v1/courses/{courseId}/quizzes`，Workbench “历史课程测试”进入真实 history 页面。
- **Response item**：`quizId`, `courseId`, `scopeType`, `lessonId`, `status`, `quizMode`, `questionCount`, `createdAt`, `updatedAt`, `latestAttempt`。
- **验收**：history page 列出课程 quiz；点击 item 进入 `/quizzes/:quizId`；空态可用。

### P2.12 “重新生成课程测试”语义

- **Lane**：Quiz/Review lane，需与 Workbench lane 在按钮 route 上做 checkpoint。
- **推荐实现**：Workbench 按钮进入 `/courses/{courseId}/quiz?regenerate=1`；QuizPage 识别 `autoRegenerate` 并只触发一次 `generateAndPoll(courseId)`。
- **验收**：regenerate 按钮真实调用 generate；普通 quiz route 不自动生成；rebuild 不重复触发。

### P2.13 课程删除影响确认

- **Lane**：Course library lane。
- **目标**：删除前展示真实 `delete-impact`，支持部分成功/失败。
- **要求**：新增 frontend wrapper/model；impact loading 期间不能确认删除；多选 aggregate counts；409 blocker 可读。
- **验收**：dialog 显示真实 impact；impact 失败不能直接删除；partial failure 清晰。

### P2.14 课程归档 / 恢复

- **Lane**：Course library lane。
- **目标**：课程可归档、查看归档、恢复。
- **要求**：新增 `archiveCourse`, `restoreCourse` wrapper；query state 支持 `archived=exclude|include|only`；归档课程显示恢复按钮。
- **验收**：归档后默认列表消失；archived-only 显示归档课程；恢复后回默认列表。

---

## Data/API contracts

| API | 状态 | 用途 | 本轮动作 |
|---|---|---|---|
| `GET /api/v1/courses` | 已有 | 课程库 query | Course library lane 接前端筛选。 |
| `GET /api/v1/courses/{courseId}/delete-impact` | 已有后端，前端缺 | 删除确认 | Course library lane 加 wrapper/model/dialog。 |
| `POST /api/v1/courses/{courseId}/archive` | 已有后端，前端缺 | 归档 | Course library lane。 |
| `POST /api/v1/courses/{courseId}/restore` | 已有后端，前端缺 | 恢复 | Course library lane。 |
| `POST /api/v1/courses/{courseId}/resources/upload-init` | 已有 | 上传初始化 | Workbench lane 复用。 |
| object PUT | 已有 | 上传对象 | Workbench lane 复用。 |
| `POST /api/v1/courses/{courseId}/resources/upload-complete` | 已有 | 资源落库 | Workbench lane 复用。 |
| `DELETE /api/v1/courses/{courseId}/resources/{resourceId}` | 已有 | 删除资源 | Lesson study lane materials 使用。 |
| `GET /api/v1/course-resources/{resourceId}/playback` | 已有 | 视频播放 | Lesson study lane materials 使用。 |
| `GET /api/v1/course-resources/{resourceId}/download` | 需要新增 | 非视频下载 | Backend contract lane + Lesson study lane。 |
| `PATCH /api/v1/courses/{courseId}/resources/{resourceId}` | 需要新增 | 重绑定/QA 可见性 | Backend contract lane + Lesson study lane。 |
| `POST /api/v1/courses/{courseId}/lessons` | 已有但需扩展 | 新建课时 | Backend lane 加 optional `metaJson`；Workbench lane 调用。 |
| lesson update/delete/reorder/merge/split/primary-video | 已有 | 课时管理 | Workbench lane。 |
| `GET/PUT /api/v1/courses/{courseId}/lessons/{lessonId}/progress` | 已有 | 课时进度 | Lesson study lane。 |
| B 站 auth/preview/import/status/cancel | 已有 | B 站导入 | Workbench lane。 |
| QA sessions/messages | 已有但需核实字段 | QA history | Backend lane + QA page lane。 |
| `POST /api/v1/courses/{courseId}/quizzes/generate` | 已有 | 课程 quiz 生成 | Quiz/Review lane regenerate。 |
| `GET /api/v1/courses/{courseId}/quizzes` | 需要新增 | quiz history | Backend lane + Quiz/Review lane。 |
| `POST /api/v1/quizzes/{quizId}/submit` | 已有 | quiz submit | Quiz/Review lane review closure。 |
| `GET /api/v1/review-task-runs/{reviewTaskRunId}/status` | 已有 | review run status | Quiz/Review lane。 |
| `GET /api/v1/courses/{courseId}/review` | 已有 | review read model | Quiz/Review lane。 |
| `POST /api/v1/review-tasks/{reviewTaskId}/complete` | 已有 | 标记完成 | Quiz/Review lane。 |

---

## State management

- **Course library**：新增 `CourseLibraryQueryState`、`courseLibraryQueryProvider`、参数化 `courseLibraryProvider(query)`；delete/archive/restore 成功后 invalidate 当前 query。
- **Workbench upload**：新增或抽取 `resourceUploadControllerProvider(scope)`；上传成功后 invalidate workbench/lesson。
- **Lesson study**：`LessonStudyProvider` 增加 progress save state 和 QA exchange state；`playerStateProvider` 仍只表示本地播放器状态。
- **New lesson/Bilibili**：表单字段可本地 state；B 站状态复用/扩展 `BilibiliImportProvider`；已创建 lesson id/import run id 必须保存在 flow state，避免 retry 重复创建。
- **QA history**：新增 `qaSessionsProvider(QaScopeArgs)`、`qaMessagesProvider(sessionId)`；active session 进入 provider state。
- **Quiz/Review**：`CourseFlowProvider` 继续保存 active course/lesson/quiz/attempt/reviewTaskRunId；`ReviewProvider` 增加 poll existing run。

### 必须后端持久化的状态

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

### Lane targeted tests

| Lane | 必跑 targeted tests |
|---|---|
| Backend contract | `python -m pytest server/tests/test_lessons.py server/tests/test_resources.py server/tests/test_qa.py server/tests/test_quizzes.py server/tests/test_courses.py` |
| Workbench | `cd client_flutter && flutter test test/features/course_workbench` |
| Lesson study | `cd client_flutter && flutter test test/features/lesson_study` |
| Course library | `cd client_flutter && flutter test test/features/course_library` |
| QA page | `cd client_flutter && flutter test test/features/course_qa` |
| Quiz/Review | `cd client_flutter && flutter test test/features/quiz test/features/review` |

### Full regression commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

### 手工验收路径

1. 工作台上传课程级 PDF，确认课程资料出现。
2. 新建课时，填写目标/掌握程度/时间预算并上传文件，确认 metadata 落库、资料绑定、讲义生成。
3. 新建课时填写 B 站链接，完成 preview/import/poll，确认 primary video 可播放。
4. 课时学习播放 20 秒暂停，刷新后恢复位置。
5. 点击讲义块跳转，刷新后恢复 block。
6. 课时学习页提问，确认 question + answer + citation。
7. 本节资料删除资料，确认刷新和错误处理。
8. 完成 quiz，进入 review，确认 run polling、任务展示、回讲义、进测试、标记完成。
9. 课程库搜索/筛选/排序，归档/恢复课程。
10. 删除课程前查看 impact，再确认删除。
11. 打开课程测试历史，进入历史 quiz detail。
12. 点击“重新生成课程测试”，确认真实生成。

---

## Risks and constraints

- **共享文件冲突**：`course_workbench_page.dart`、`lesson_study_page.dart`、`course_library_page.dart`、`api_client.dart`、`interfaces.py`、`sqlalchemy.py` 是高冲突文件；必须按 lane 所有权控制。
- **幂等性**：upload-complete、B 站 create import、quiz generate、review regenerate 都必须带 idempotency key。
- **重复点击**：所有 mutation button 需要 disabled/loading。
- **轮询**：必须有 terminal 判断和 maxAttempts；生产 interval 不低于 1–2 秒；测试用短 interval 必须可 override。
- **进度保存**：不得每 tick 请求后端；pause/dispose flush 要去重。
- **旧数据兼容**：`metaJson` optional；历史 QA 缺 question 时要 fallback 或 migration；`archivedAt=null` 表示未归档。
- **空状态兼容**：无课程、无课时、无资源、无主视频、无 handout、无 quiz、无 review task、无 QA session、B 站未登录、`reviewTaskRunId=null`。
- **测试环境**：file picker、video player、object storage、B 站外部请求必须 mock/fake。
