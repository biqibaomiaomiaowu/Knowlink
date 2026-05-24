# Yang Caiyi Query Field Alignment

本文整理任务 24：简单查询接口字段对齐记录。只记录已冻结查询 DTO 的字段对齐情况，不进入实现。

## Scope

| Category | APIs |
|---|---|
| Course query | `GET /api/v1/courses/recent`、`GET /api/v1/courses/{courseId}`、`GET /api/v1/courses/current` |
| Resource query | `GET /api/v1/courses/{courseId}/resources`、`GET /api/v1/course-resources/{resourceId}/playback` |
| Pipeline query | `GET /api/v1/parse-runs/{parseRunId}`、`GET /api/v1/courses/{courseId}/pipeline-status`、`GET /api/v1/courses/{courseId}/parse/summary` |
| Bilibili query | `GET /api/v1/courses/{courseId}/resources/imports/bilibili`、`GET /api/v1/bilibili-import-runs/{importRunId}/status` |
| Handout query | `GET /api/v1/courses/{courseId}/handouts/latest`、`outline`、`blocks`、`current-block`、`jump-target` |
| QA query | `GET /api/v1/qa/sessions/{sessionId}/messages` |
| Quiz query | `GET /api/v1/quizzes/{quizId}`、`GET /api/v1/quizzes/{quizId}/status` |
| Review query | `GET /api/v1/courses/{courseId}/review-tasks`、`GET /api/v1/review-task-runs/{reviewTaskRunId}/status` |
| Progress query | `GET /api/v1/courses/{courseId}/progress` |

## Common Field Alignment

| Field | Expected style | Notes |
|---|---|---|
| ids | camelCase with domain prefix | `courseId`、`resourceId`、`taskId`、`quizId` |
| status | frozen enum string | Do not invent new status without contract |
| timestamps | ISO 8601 datetime | Include timezone when applicable |
| arrays | empty array allowed | Prefer `[]` over missing for list responses |
| nullable fields | explicit `null` allowed where contract says so | Example: `durationSec: null` |
| citations | public citation only | No `segmentId` / `segmentKey` in public response |

## Alignment Table

| API area | Key fields | Current conclusion | Pending |
|---|---|---|---|
| Courses | `courseId`、`title`、`entryType`、`catalogId`、`lifecycleStatus`、`pipelineStage`、`pipelineStatus`、`updatedAt` | Contract clear | none |
| Resources | `resourceId`、`resourceType`、`originalName`、`objectKey`、`ingestStatus`、`validationStatus`、`processingStatus` | Contract clear | none |
| Playback | `playbackUrl`、`mimeType`、`expiresAt`、`durationSec` | Contract clear | Android reachable URL needs environment check |
| Pipeline | `parseRunId`、`progressPct`、`steps[]`、`nextAction`、`sourceOverview` | Contract clear | Week 2 semantic source should be referenced |
| Bilibili import | `importRunId`、`sourceType`、`status`、`stage`、`progressPct`、`nextAction` | V2 contract clear | real public sample acceptance belongs to Cao Le |
| Handout | `handoutVersionId`、`items[]`、`children[]`、`blockId`、`generationStatus` | Contract clear | Flutter adaptation record can be added later |
| QA | `sessionId`、`messageId`、`answerMd`、`answerType`、`citations` | Contract clear | AI answer quality not in Yang scope |
| Quiz | `quizId`、`status`、`questions[]`、`selectedOption` | Objective quiz clear | subjective grading contract not frozen |
| Review | `reviewTaskId`、`priorityScore`、`recommendedSegment`、`practiceEntry` | Contract clear | algorithm quality not in Yang scope |
| Progress | `lastHandoutBlockId`、`lastVideoResourceId`、`lastPositionSec`、`lastDocResourceId`、`lastPageNo` | Contract clear | none |

## Record Template

| Field | Value |
|---|---|
| API |  |
| Test environment |  |
| Request path |  |
| Response fields match contract | yes / no |
| Unexpected missing fields |  |
| Unexpected extra fields |  |
| Enum values valid | yes / no |
| Android display issue |  |
| Conclusion | pass / fail / blocked |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理字段对齐表、联调结论和待确认项 | 可做 |
| 因字段未冻结而自行新增 DTO 字段 | 不做 |
| 修改复杂查询、AI、图谱、SSE 或判卷实现 | 不做 |
