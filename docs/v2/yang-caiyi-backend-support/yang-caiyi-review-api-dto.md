# Yang Caiyi Review API DTO

本文整理任务 18：复习接口 DTO 文档。只整理 review tasks、regenerate、run status 和 complete 字段，不改复习推荐算法。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | review API contract |
| `server/api/routers/reviews.py` | router entry |
| `server/domain/services/reviews.py` | review service |

## APIs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/courses/{courseId}/review-tasks` | 查询复习任务列表 |
| `POST` | `/api/v1/courses/{courseId}/review-tasks/regenerate` | 重新生成复习任务 |
| `GET` | `/api/v1/review-task-runs/{reviewTaskRunId}/status` | 查询复习任务生成 run 状态 |
| `POST` | `/api/v1/review-tasks/{reviewTaskId}/complete` | 标记复习任务完成 |

## Review Task DTO

| Field | Type | Meaning |
|---|---|---|
| `reviewTaskId` | integer | 复习任务 id |
| `taskType` | string | 任务类型，例如 `revisit_block` |
| `priorityScore` | integer | 优先级分数 |
| `reasonText` | string | 推荐原因 |
| `recommendedMinutes` | integer | 建议学习分钟数 |
| `recommendedSegment` | object | 建议回看片段 |
| `practiceEntry` | object | 练习入口 |
| `reviewOrder` | integer | 展示顺序 |
| `intensity` | string | 复习强度 |

## `recommendedSegment`

| Field | Type | Meaning |
|---|---|---|
| `blockId` | integer | 建议回看的讲义块 |
| `startSec` / `endSec` | integer | 视频片段 |
| `label` | string | 展示文案 |

## `practiceEntry`

| Field | Type | Meaning |
|---|---|---|
| `type` | string | 入口类型，例如 `quiz` |
| `targetId` | integer | 目标实体 id |
| `label` | string | 展示文案 |

## Regenerate Response DTO

| Field | Type | Meaning |
|---|---|---|
| `taskId` | integer | 异步任务 id |
| `status` | string | async task 状态 |
| `nextAction` | string | 通常为 `poll` |
| `entity.type` | string | 固定为 `review_task_run` |
| `entity.id` | integer | review task run id |

## Run Status DTO

| Field | Type | Meaning |
|---|---|---|
| `reviewTaskRunId` | integer | 复习任务 run id |
| `courseId` | integer | 课程 id |
| `status` | string | run 状态 |
| `generatedCount` | integer | 已生成任务数 |

## Complete Response DTO

| Field | Type | Meaning |
|---|---|---|
| `reviewTaskId` | integer | 复习任务 id |
| `completed` | boolean | 是否完成 |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理复习接口 DTO 和联调记录 | 可做 |
| 修改复习推荐算法、掌握度计算或排序策略 | 不做 |
