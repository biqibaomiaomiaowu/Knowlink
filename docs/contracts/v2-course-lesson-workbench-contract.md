# V2 Course-Lesson Workbench Contract

日期：2026-06-02

本文冻结 V2 Phase 2 课程库、节课、课程工作台、分层资料和分层学习产物的 API / DTO / 错误码口径。第二版仍然是单用户多课程，不引入团队共享、权限模型或多用户隔离。所有接口继续使用 `/api/v1` 前缀，状态拼写统一使用 `canceled`。

## 1. Scope And Non-goals

In scope:

- 完整课程库：搜索、筛选、排序、归档、恢复、删除前影响范围预览。
- Lesson 作为一级领域对象：顺序、主视频、节课资料、学习状态、掌握度和下一步动作。
- 课程工作台 read model：课程信息、整体进度、节课列表、课程级资料、全课程 QA、图谱、综合测验、总复习、报告、导出和设置入口。
- 节课详情 read model：主视频、本节资料、本节讲义、本节 QA、本节测验、本节复习、本节图谱、进度、引用、薄弱点和下一步动作。
- 资料必须显式带 `scopeType`、`lessonId` 和 `usageRole`，区分课程级共享资料与单节课独享资料。
- 讲义、QA、测验、复习、掌握度、进度、图谱、报告、导出和推荐入口必须带 scope。
- 本轮允许 graph / streaming / subjective grading / report / export 仅返回 placeholder 状态。

Non-goals:

- 不做多用户、团队课程、权限或共享课程。
- 不做单资料 QA。No single-resource QA: 资料只能作为 evidence source 被课程 QA 或节课 QA 引用。
- 不实现复杂图谱生成算法、图数据库迁移、大规模图检索。
- 不实现生产级 SSE 断线恢复；只冻结事件入口和 placeholder 状态。
- 不实现正式 LLM judge、人审队列或主观题生产策略；只冻结评分结构和占位响应。
- 不做危险级联物理删除；第一轮使用软删除或 blocker 预览。

## 2. Course Library And Workbench APIs

```text
GET    /api/v1/courses
GET    /api/v1/courses/{courseId}
PATCH  /api/v1/courses/{courseId}
GET    /api/v1/courses/{courseId}/delete-impact
POST   /api/v1/courses/{courseId}/archive
POST   /api/v1/courses/{courseId}/restore
DELETE /api/v1/courses/{courseId}
GET    /api/v1/courses/current
POST   /api/v1/courses/{courseId}/switch-current
GET    /api/v1/courses/{courseId}/workbench
```

`GET /api/v1/courses` query:

- `q`
- `learningStatus`
- `source`: `manual_import`、`recommendation`、`bilibili`
- `archived`: `include|only|exclude`
- `sort`: `recent_activity_desc|created_at_desc|exam_at_asc|title_asc`

`CourseLibraryItem`:

- `courseId`
- `title`
- `isCurrent`
- `entryType`
- `learningStatus`
- `lastActivityAt`
- `lessonCount`
- `courseResourceCount`
- `currentLessonId`
- `currentLessonTitle`
- `overallMasteryScore`
- `pendingReviewCount`
- `pipelineStage`
- `pipelineStatus`
- `lifecycleStatus`
- `archivedAt`

`PATCH /api/v1/courses/{courseId}` request:

- `title`
- `goalText`
- `examAt`
- `preferredStyle`

`GET /api/v1/courses/{courseId}/delete-impact` returns blocker counts before deletion. `DELETE /api/v1/courses/{courseId}` either soft deletes a safe course or returns `409 course.delete_blocked` with blockers.

`CourseWorkbenchData`:

- `course`
- `progress`
- `currentLesson`
- `lessons`
- `courseResources`
- `quickEntries`
- `nextActions`
- `placeholderStates`

Quick entries include: `course_qa`、`course_graph`、`comprehensive_quiz`、`course_review`、`report`、`export`、`settings`。

Frozen route tokens for tests and downstream DTO alignment:

- GET /api/v1/courses
- GET /api/v1/courses/{courseId}/workbench

## 3. Lesson APIs And State

```text
GET    /api/v1/courses/{courseId}/lessons
POST   /api/v1/courses/{courseId}/lessons
GET    /api/v1/courses/{courseId}/lessons/{lessonId}
PATCH  /api/v1/courses/{courseId}/lessons/{lessonId}
DELETE /api/v1/courses/{courseId}/lessons/{lessonId}
POST   /api/v1/courses/{courseId}/lessons/reorder
POST   /api/v1/courses/{courseId}/lessons/{lessonId}/primary-video
POST   /api/v1/courses/{courseId}/lessons/merge
POST   /api/v1/courses/{courseId}/lessons/{lessonId}/split
```

`lessonStatus`: `draft|resource_ready|learning_ready|completed|stale|deleted`

`sourceType`: `manual|local_video|bilibili_part|bilibili_collection_item|bilibili_bangumi_item`

`handoutStatus`: `not_generated|generating|ready|partial_success|failed|stale`

`quizStatus`: `not_generated|ready|completed|failed|stale`

`reviewStatus`: `not_due|due|in_progress|completed`

`CreateLessonRequest`:

- `title`
- `sourceType`
- `sourceRefJson`
- `primaryVideoResourceId`
- `primaryVideoStartSec`
- `primaryVideoEndSec`

`primaryVideoStartSec` / `primaryVideoEndSec` 必须随 `primaryVideoResourceId` 一起提交；`end` 必须大于 `start` 且不得超过视频时长。

`UpdateLessonRequest`:

- `title`
- `lessonStatus`
- `metaJson`

`UpdateLessonRequest.lessonStatus` 只允许 `draft|resource_ready|learning_ready|completed|stale`；`deleted` 只能通过 `DELETE /api/v1/courses/{courseId}/lessons/{lessonId}` 产生，以保证 `deletedAt` 和排序压缩一致。

`ReorderLessonsRequest`:

- `lessonIds`: 同课程内全部未删除 lesson id，缺失、重复或外课 id 返回 `409 lesson.order_conflict`。

`SetPrimaryVideoRequest`:

- `resourceId`
- `startSec`（可选）
- `endSec`（可选）

`SetPrimaryVideoRequest.startSec` / `endSec` 用于设置可选视频片段；两者同时存在时 `end` 必须大于 `start` 且不得超过视频时长。只提交 `resourceId` 时表示绑定完整视频或未知区间。

`MergeLessonsRequest`:

- `lessonIds`: 只允许同课程内相邻节课。
- `targetTitle`

`SplitLessonRequest`:

- `splitAtSec`
- `firstTitle`
- `secondTitle`

Merge side effects:

- 第一个 `lessonId` 是 target lesson；其余 lesson 软删除。
- 非 target lesson 的 lesson-scoped resources 必须迁移到 target lesson，不创建重复 resource row。
- 受影响 lesson-scoped artifacts 标记 stale。

Split side effects:

- 拆分后的两段 lesson 共享同一个 `primaryVideoResourceId`，通过 `primaryVideoStartSec` / `primaryVideoEndSec` 区分片段。
- 如果原主视频 resource 是 lesson scope，拆分时必须提升为 course scope，使两段 lesson 可以引用同一 resource。
- 不创建重复视频 resource row；原 lesson-scoped artifacts 标记 stale。

`LessonSummary`:

- `lessonId`
- `courseId`
- `title`
- `orderIndex`
- `lessonStatus`
- `primaryVideoResourceId`
- `primaryVideoStartSec`
- `primaryVideoEndSec`
- `handoutStatus`
- `quizStatus`
- `reviewStatus`
- `masteryScore`
- `lastPositionSec`
- `lastActivityAt`
- `nextAction`

`LessonDetailData`:

- `lesson`
- `primaryVideo`
- `lessonResources`
- `artifactSummaries`
- `progress`
- `citations`
- `sourceOverview`
- `knowledgePointPlaceholders`
- `weaknessPlaceholders`
- `nextAction`

Merge / split 不物理删除已生成产物；受影响的 lesson-scoped artifacts 必须标记 `stale` 或写入等价 stale metadata。响应返回 `staleArtifacts` 详情和类型化 `staleArtifactIds`，`staleArtifactIds` 使用 `{artifactType}:{artifactId}` 格式，避免 SQL 多表 id 重叠。

Frozen route tokens:

- GET /api/v1/courses/{courseId}/lessons
- POST /api/v1/courses/{courseId}/lessons
- GET /api/v1/courses/{courseId}/lessons/{lessonId}
- PATCH /api/v1/courses/{courseId}/lessons/{lessonId}
- DELETE /api/v1/courses/{courseId}/lessons/{lessonId}
- POST /api/v1/courses/{courseId}/lessons/reorder
- POST /api/v1/courses/{courseId}/lessons/{lessonId}/primary-video
- POST /api/v1/courses/{courseId}/lessons/merge
- POST /api/v1/courses/{courseId}/lessons/{lessonId}/split

## 4. Resource Scope And Import Placement

```text
POST /api/v1/courses/{courseId}/resources/upload-init
POST /api/v1/courses/{courseId}/resources/upload-complete
GET  /api/v1/courses/{courseId}/resources?scopeType=&lessonId=
```

新增字段:

- `scopeType`: `course|lesson`
- `lessonId`: `scopeType=lesson` 时必填；MP4 使用 `lessonPlacement=auto_create` 时可为空。
- `usageRole`: `course_material|primary_video|lesson_material|transcript|supplement`
- usage role values include `course_material`、`primary_video`、`lesson_material`、`transcript`、`supplement`
- `lessonPlacement`: `auto_create|bind_existing|course_material`
- `lessonTitle`
- `visibleToCourseQa`
- `sourcePartId`
- `durationSec`
- `sortOrder`

规则:

- PDF / PPTX / DOCX / SRT 必须传 `scopeType`；缺失返回 `400 resource.scope_required`。
- `scopeType=lesson` 时 `lessonId` 必须存在且属于当前课程；不匹配返回 `400 resource.lesson_mismatch`。
- `scopeType=course` 时 `lessonId=null`，默认 `usageRole=course_material`。
- MP4 默认 `lessonPlacement=auto_create`，创建 lesson 并设置 `usageRole=primary_video`；也可以 `bind_existing` 绑定已有 lesson。
- `upload-init` 返回的 `headers` 必须包含 `x-amz-meta-scope-type`；当请求已确定 `lessonId` 时，还必须包含 `x-amz-meta-lesson-id`。
- `upload-complete` 返回资源行必须携带 `scopeType`、`lessonId`、`usageRole`、`sourceType`、`sourcePartId`、`visibleToCourseQa`、`durationSec`。
- 课程级资料可被全课程 QA、课程总讲义、综合测验、总复习和课程图谱读取，也可作为节课产物的辅助证据。
- 节课独享资料默认只被本节讲义、本节 QA、本节测验、本节复习读取。

Bilibili import fields:

- `lessonMode`: `auto_per_video|bind_existing|course_material`
- `targetLessonId`
- `partLessonTitles`
- `partLessonMap`: 可选的 part-level 初始映射，键为 `sourcePartId`，值可包含 `lessonId`、`sourcePartId`。
- 请求期 `partLessonMap` 不允许客户端提交 `resourceId`；`resourceId` 只能由导入 runner 在资源落库后写入。
- `createLessonIfMissing`
- import item 必须记录 `sourcePartId`、`lessonId`，导入完成后记录 `resourceId`。
- import run list/status 响应必须返回 `partLessonMap` 与 `items`，其中 `items[*]` 至少包含 `itemKey`、`lessonId`、`resourceId`、`status`、`progressPct`、`metadataJson.sourcePartId`。
- import run 的 `selection.partLessonMap` 记录 part-level 映射，键为 `sourcePartId`，值至少包含 `lessonId`，导入完成后包含 `resourceId`。

单视频、多 P、合集、番剧默认一视频一节课。重试不得为同一 import run item 重复创建 lesson。

Frozen route token:

- POST /api/v1/courses/{courseId}/resources/upload-init

## 5. Handout Scope

```text
GET  /api/v1/courses/{courseId}/handouts/course-summary
POST /api/v1/courses/{courseId}/handouts/course-summary/generate
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/handout
POST /api/v1/courses/{courseId}/lessons/{lessonId}/handout/generate
```

`handout_versions` scope fields:

- `scopeType`: `course|lesson`
- `lessonId`
- `artifactKind`: `lesson_handout|course_summary_handout`

Placeholder response:

- `scopeType`
- `lessonId`
- `status`: `not_generated|generating|ready|partial_success|failed|stale|placeholder`
- `canGenerate`
- `requiredSources`
- `message`
- `availableActions`
- `citations`

Lesson handout 默认读取本节主视频、本节资料和必要课程级资料。Course summary handout 可读取所有 lesson、课程级资料和已生成 lesson handout。

## 6. Course QA And Lesson QA

```text
GET  /api/v1/courses/{courseId}/qa/sessions
POST /api/v1/courses/{courseId}/qa/messages
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/qa/sessions
POST /api/v1/courses/{courseId}/lessons/{lessonId}/qa/messages
GET  /api/v1/qa/sessions/{sessionId}/messages
```

`qa_sessions` scope fields:

- `scopeType`: `course|lesson`
- `lessonId`
- `title`
- `lastMessageAt`

Course QA 检索范围:

- 所有节课
- 课程级资料
- 已生成讲义
- 测验结果
- 复习记录
- 知识图谱 read model

Lesson QA 检索范围:

- 当前节课主视频
- 当前节课独享资料
- 当前节课讲义
- 必要课程级资料

课程 QA 和节课 QA 历史会话互不混用。`qa.scope_invalid` 用于 scope 与 session、lesson 或 course 不匹配。明确不做单资料 QA；No single-resource QA.

Frozen route tokens:

- GET /api/v1/courses/{courseId}/qa/sessions
- GET /api/v1/courses/{courseId}/lessons/{lessonId}/qa/sessions

## 7. Quiz Scope And Subjective Grading Placeholder

```text
POST /api/v1/courses/{courseId}/lessons/{lessonId}/quizzes/generate
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/quizzes/current
POST /api/v1/courses/{courseId}/quizzes/stage/generate
POST /api/v1/courses/{courseId}/quizzes/comprehensive/generate
GET  /api/v1/quizzes/{quizId}
POST /api/v1/quizzes/{quizId}/submit
GET  /api/v1/courses/{courseId}/subjective-grading/placeholder
```

`quizzes` scope fields:

- `scopeType`: `lesson|lesson_range|course`
- allowed values include `lesson`、`lesson_range`、`course`
- `lessonId`
- `startLessonId`
- `endLessonId`
- `quizMode`: `objective|subjective_placeholder|mixed_placeholder`

Subjective grading placeholder:

- `answerText`
- `gradingStatus`: `placeholder|not_submitted|grading|graded|failed`
- `totalScore`
- `dimensionScores`
- `deductions`
- `feedbackMd`
- `citations`
- `confidenceScore`
- `needsHumanReview`

正式 LLM judge 和人审队列不在本轮实现。

Frozen route token:

- POST /api/v1/courses/{courseId}/quizzes/stage/generate

## 8. Review Scope And Evidence Chain

```text
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/review
POST /api/v1/courses/{courseId}/lessons/{lessonId}/review/regenerate
GET  /api/v1/courses/{courseId}/review
POST /api/v1/courses/{courseId}/review/regenerate
GET  /api/v1/courses/{courseId}/exam-review
```

`review_tasks` and `review_task_runs` scope fields:

- `scopeType`: `course|lesson`
- `lessonId`
- `evidenceChainJson`

`mastery_records` stores course-scope rows as `lessonId=null` and lesson-scope rows with a concrete `lessonId`. Course-scope uniqueness is `(userId, courseId, knowledgePointKey)` where `lessonId=null`; lesson-scope uniqueness is `(userId, courseId, lessonId, knowledgePointKey)`.

Review task fields:

- `reasonText`
- `sourceAttemptId`
- `sourceQuestionKeys`
- `lessonId`
- `knowledgePointKey`
- `recommendedSegment`
- `recommendedHandoutBlock`
- `evidenceChain`

Course review aggregates weak lessons and cross-lesson weak points. Lesson review only returns lesson-scoped tasks and necessary course-level evidence.

## 9. Graph Report Export And Streaming Placeholders

```text
GET  /api/v1/courses/{courseId}/graph
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/graph
GET  /api/v1/courses/{courseId}/reports/summary
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/reports/summary
GET  /api/v1/courses/{courseId}/exports
POST /api/v1/courses/{courseId}/exports
GET  /api/v1/courses/{courseId}/recommendations/next-actions
GET  /api/v1/courses/{courseId}/lessons/{lessonId}/recommendations/next-actions
GET  /api/v1/async-tasks/{taskId}/events
```

Placeholder DTO:

- `status`: `not_generated|generating|ready|placeholder`
- `scopeType`: `course|lesson`
- `lessonId`
- `message`
- `availableActions`
- `citations`

Graph read model placeholder uses shared node / edge DTO names for course graph and lesson graph. Streaming placeholder reuses `async_tasks.id` as the task truth source.

Export placeholder:

- `availableExportTypes`: `course_summary|lesson_summary|qa_transcript|quiz_report|review_plan`
- `status=placeholder`
- `downloadUrl=null`

Report placeholder:

- `summaryStatus=placeholder`
- `metrics=[]`
- `message`

Frozen route tokens:

- GET /api/v1/courses/{courseId}/graph
- POST /api/v1/courses/{courseId}/exports

## 10. Home Continue Learning And Progress APIs

```text
GET /api/v1/home/dashboard
GET /api/v1/courses/{courseId}/progress
PUT /api/v1/courses/{courseId}/progress
GET /api/v1/courses/{courseId}/lessons/{lessonId}/progress
PUT /api/v1/courses/{courseId}/lessons/{lessonId}/progress
```

`continueLearning` must point to:

- `courseId`
- `lessonId`
- `lastPositionSec`
- `lastHandoutBlockId`
- `nextRoute`
- `nextAction`

Course progress remains an aggregate. `user_lesson_progress` stores lesson position, handout reading position, quiz status and review status.
`lastHandoutBlockId` must reference a handout block visible to the current course or lesson scope; unknown or cross-course block ids are invalid.

`user_lesson_progress` fields:

- `userId`
- `courseId`
- `lessonId`
- `lastPositionSec`
- `lastHandoutBlockId`
- `handoutReadPercent`
- `quizStatus`
- `reviewStatus`
- `updatedAt`

Frozen route token:

- GET /api/v1/home/dashboard

## 11. Error Codes And Deletion Blockers

Required error codes:

- `lesson.not_found`: 节课不存在或不属于当前课程。
- `lesson.scope_required`: 请求需要明确 lesson scope 或 lesson id。
- `lesson.order_conflict`: 节课排序请求缺失、重复、跨课程或违反同课程唯一顺序。
- `lesson.has_dependents`: 节课存在无法安全级联的资源、产物、进度或引用。
- `resource.scope_required`: 上传或导入资料未声明 `scopeType`。
- `resource.lesson_mismatch`: 资料声明的 lesson 不存在或不属于当前课程。
- `course.delete_blocked`: 删除课程前发现 blocker，不能安全删除。
- `artifact.scope_invalid`: 讲义、测验、复习、图谱、报告或导出请求 scope 非法。
- `qa.scope_invalid`: QA session 或消息请求 scope 与 course / lesson 不匹配。

Deletion blocker DTO:

- `blockerType`
- `count`
- `message`
- `affectedIds`
- `safeAction`

第一轮删除策略：优先软删除；若引用链不能安全保留，返回 blocker，不静默破坏 evidence chain。

## 12. Response Examples

Course library item:

```json
{
  "courseId": 101,
  "title": "数据库系统",
  "isCurrent": true,
  "entryType": "bilibili",
  "learningStatus": "learning_ready",
  "lastActivityAt": "2026-06-02T10:00:00+08:00",
  "lessonCount": 8,
  "courseResourceCount": 2,
  "currentLessonId": 301,
  "currentLessonTitle": "关系模型",
  "overallMasteryScore": 72,
  "pendingReviewCount": 3,
  "pipelineStage": "handout",
  "pipelineStatus": "partial_success",
  "lifecycleStatus": "learning_ready",
  "archivedAt": null
}
```

Lesson detail:

```json
{
  "lesson": {
    "lessonId": 301,
    "courseId": 101,
    "title": "关系模型",
    "orderIndex": 2,
    "lessonStatus": "learning_ready",
    "masteryScore": 68
  },
  "primaryVideo": {
    "resourceId": 9001,
    "resourceName": "02-relational-model.mp4",
    "startSec": 0,
    "endSec": 3600
  },
  "lessonResources": [],
  "artifactSummaries": [
    {
      "type": "lesson_handout",
      "scopeType": "lesson",
      "lessonId": 301,
      "status": "ready"
    }
  ],
  "progress": {
    "lastPositionSec": 1120,
    "lastHandoutBlockId": "hb_2",
    "quizStatus": "not_generated",
    "reviewStatus": "due"
  },
  "citations": [],
  "sourceOverview": {
    "scopeType": "lesson",
    "lessonId": 301,
    "resourceCount": 1
  },
  "knowledgePointPlaceholders": [],
  "weaknessPlaceholders": [],
  "nextAction": {
    "type": "continue_video",
    "label": "继续本节视频",
    "route": "/courses/101/lessons/301"
  }
}
```

Resource scope:

```json
{
  "resourceId": 9001,
  "courseId": 101,
  "scopeType": "lesson",
  "lessonId": 301,
  "usageRole": "primary_video",
  "visibleToCourseQa": true,
  "sourcePartId": "bvid:BV1xx:p2",
  "durationSec": 3600,
  "sortOrder": 2
}
```

QA citation:

```json
{
  "scopeType": "lesson",
  "lessonId": 301,
  "lessonTitle": "关系模型",
  "resourceId": 9001,
  "resourceName": "02-relational-model.mp4",
  "refLabel": "第 2 节课：关系模型 / 视频 18:40",
  "startSec": 1120,
  "endSec": 1148,
  "confidenceScore": 0.84
}
```
