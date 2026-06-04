# Yang Caiyi Inquiry API DTO

本文整理任务 14：问询接口 DTO 文档。只整理问题列表和答案提交字段，不改问询生成或偏好推导逻辑。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | inquiry API contract |
| `docs/contracts/week2-cao-le-parse-inquiry-contract.md` | 问询题 key 到 `learning_preferences` 映射 |
| `server/api/routers/inquiry.py` | router entry |
| `server/domain/services/inquiry.py` | inquiry service |

## APIs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/courses/{courseId}/inquiry/questions` | 获取问询题列表 |
| `POST` | `/api/v1/courses/{courseId}/inquiry/answers` | 提交问询答案 |

## Question DTO

| Field | Type | Meaning |
|---|---|---|
| `version` | integer | 问询模板版本 |
| `questions` | array | 问题列表 |

## `questions[]`

| Field | Type | Meaning |
|---|---|---|
| `key` | string | 问题 key，提交答案时原样使用 |
| `label` | string | 展示标题 |
| `type` | string | 题型，例如 `single_select`、`number` |
| `required` | boolean | 是否必填 |
| `options` | array | 选项列表；number 类型可为空数组 |
| `minValue` | integer | 数字题最小值，仅 `time_budget_minutes` 使用 |
| `maxValue` | integer | 数字题最大值，仅 `time_budget_minutes` 使用 |

## Frozen Keys

| Key | Allowed values / type | Target meaning |
|---|---|---|
| `goal_type` | `final_review`、`exam_sprint`、`daily_learning`、`knowledge_gap_fix` | 学习目标 |
| `mastery_level` | `beginner`、`intermediate`、`advanced` | 当前掌握程度 |
| `time_budget_minutes` | integer, 30 to 600 | 本轮学习时间预算 |
| `handout_style` | `exam`、`balanced`、`detailed` | 讲义风格 |
| `explanation_granularity` | `quick`、`balanced`、`detailed` | 解释粒度 |

## Submit DTO

| Field | Type | Meaning |
|---|---|---|
| `answers` | array | 答案列表 |
| `answers[].key` | string | 必须命中服务端下发的 key |
| `answers[].value` | string / number / array | 答案值，按题型校验 |

## Submit Response

| Field | Type | Meaning |
|---|---|---|
| `saved` | boolean | 是否保存成功 |
| `answerCount` | integer | 保存的答案数量 |

## Errors

| `errorCode` | Meaning |
|---|---|
| `inquiry.course_not_ready` | 课程未进入可问询状态 |
| `common.validation_error` | 必填缺失、未知 key、枚举非法或时间预算非法 |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理字段、key、提交样例和联调记录 | 可做 |
| 修改问询模板生成逻辑 | 不做 |
| 修改 `learning_preferences` 推导规则 | 不做 |
