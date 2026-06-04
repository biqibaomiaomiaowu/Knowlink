# Yang Caiyi Home Dashboard DTO

本文整理任务 5：首页 dashboard DTO 文档。只描述已冻结字段，不新增首页聚合逻辑。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | `GET /api/v1/home/dashboard` contract |
| `server/api/routers/home.py` | router entry |
| `server/domain/services/home.py` | dashboard read model assembly |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/home/dashboard` | 首页聚合数据 |

## Response DTO

| Field | Type | Meaning | Notes |
|---|---|---|---|
| `recentCourses` | array | 最近课程列表 | 结构与 `GET /api/v1/courses/recent` 的 `items[]` 对齐 |
| `topReviewTasks` | array | 首页优先展示的复习任务 | 来自复习任务 read model |
| `recommendationEntryEnabled` | boolean | 是否展示推荐入口 | 当前 contract 示例为 `true` |
| `dailyRecommendedKnowledgePoints` | array | 今日推荐知识点 | 只做展示聚合，不代表 V2 图谱已冻结 |
| `learningStats` | object | 学习统计 | 首页展示用数字聚合 |

## `dailyRecommendedKnowledgePoints[]`

| Field | Type | Meaning |
|---|---|---|
| `knowledgePoint` | string | 知识点展示名 |
| `reason` | string | 推荐原因文案 |
| `targetCourseId` | integer | 跳转课程 |

## `learningStats`

| Field | Type | Meaning |
|---|---|---|
| `streakDays` | integer | 连续学习天数 |
| `completedCourses` | integer | 已完成课程数 |
| `reviewTasksCompleted` | integer | 已完成复习任务数 |
| `totalLearningMinutes` | integer | 总学习分钟数 |

## Integration Notes

| Check | Expected |
|---|---|
| Auth | 除 `/health` 外仍需 `Authorization: Bearer <token>` |
| Empty state | `recentCourses`、`topReviewTasks`、`dailyRecommendedKnowledgePoints` 可为空数组 |
| Android display | 首页可以先展示课程、复习任务和统计；不要把 `dailyRecommendedKnowledgePoints` 当作 V2 知识图谱 contract |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理字段说明和联调记录 | 可做 |
| 新增首页推荐算法或知识图谱字段 | 不做 |
| 修改 service 聚合逻辑 | 不做 |
