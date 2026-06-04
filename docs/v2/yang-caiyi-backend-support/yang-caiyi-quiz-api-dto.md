# Yang Caiyi Quiz API DTO

本文整理任务 17：测验接口 DTO 文档。只整理客观题生成、查询、提交和得分返回字段，不扩写主观题字段。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | quiz API contract |
| `server/api/routers/quizzes.py` | router entry |
| `server/domain/services/quizzes.py` | quiz service |

## APIs

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/courses/{courseId}/quizzes/generate` | 创建测验生成任务 |
| `GET` | `/api/v1/quizzes/{quizId}` | 查询测验题目 |
| `GET` | `/api/v1/quizzes/{quizId}/status` | 查询测验生成状态 |
| `POST` | `/api/v1/quizzes/{quizId}/attempts` | 提交客观题答案 |

## Generate Request DTO

| Field | Type | Meaning |
|---|---|---|
| `questionCountLevel` | string | 题量档位；可省略，默认 `medium` |

| Value | Meaning |
|---|---|
| `small` | 1-3 题 |
| `medium` | 3-5 题 |
| `large` | 5-10 题 |

## Async Response DTO

| Field | Type | Meaning |
|---|---|---|
| `taskId` | integer | 异步任务 id |
| `status` | string | async task 状态 |
| `nextAction` | string | 通常为 `poll` |
| `entity.type` | string | 固定为 `quiz` |
| `entity.id` | integer | quiz id |

## Quiz DTO

| Field | Type | Meaning |
|---|---|---|
| `quizId` | integer | 测验 id |
| `courseId` | integer | 课程 id |
| `status` | string | 测验状态 |
| `questionCount` | integer | 实际题目数量 |
| `questions` | array | 客观题列表 |

## `questions[]`

| Field | Type | Meaning |
|---|---|---|
| `questionId` | integer | 题目 id |
| `stemMd` | string | 题干 Markdown |
| `options` | array | 四个选项，顺序对应 `A` / `B` / `C` / `D` |

## Attempt Request DTO

| Field | Type | Meaning |
|---|---|---|
| `answers` | array | 答案列表 |
| `answers[].questionId` | integer | 题目 id |
| `answers[].selectedOption` | string | 稳定选项 key：`A` / `B` / `C` / `D` |

## Attempt Response DTO

| Field | Type | Meaning |
|---|---|---|
| `attemptId` | integer | 作答 id |
| `score` | number | 得分 |
| `totalScore` | number | 总分 |
| `accuracy` | number | 正确率 |
| `reviewTaskRunId` | integer | 触发或关联的复习任务 run |
| `masteryDelta` | array | 掌握度变化 |
| `recommendedReviewAction` | object | 推荐复习动作 |

## Subjective Grading Boundary

V1 `POST /api/v1/quizzes/{quizId}/attempts` 只冻结客观题提交，`selectedOption` 不得复用为主观题答案。V2 主观题需要曹乐先冻结 `questionType`、`textAnswer`、`rubric`、`gradingRunId`、判卷状态、分项分数、证据引用、置信度和 `needsHumanReview` 等字段。

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理客观题 DTO 和联调记录 | 可做 |
| 扩写主观题字段 | 不做 |
| 改 DeepSeek 出题策略或判卷策略 | 不做 |
