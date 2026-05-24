# Yang Caiyi QA API DTO

本文整理任务 16：QA 接口 DTO 文档。只整理 QA 请求、消息查询和 citation 字段，不改 AI 回答策略。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | QA API contract |
| `docs/contracts/week2-cao-le-parse-inquiry-contract.md` | QA 候选证据与 citation 约束 |
| `server/api/routers/qa.py` | router entry |
| `server/domain/services/qa.py` | QA service |

## APIs

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/qa/messages` | 创建 QA 消息并返回回答 |
| `GET` | `/api/v1/qa/sessions/{sessionId}/messages` | 查询会话消息 |

## Request DTO

| Field | Type | Meaning |
|---|---|---|
| `courseId` | integer | 课程 id；该接口是唯一在 body 传 `courseId` 的例外 |
| `handoutBlockId` | integer | 当前讲义块 id |
| `question` | string | 用户问题 |

## Message Response DTO

| Field | Type | Meaning |
|---|---|---|
| `sessionId` | integer | QA 会话 id |
| `messageId` | integer | 消息 id |
| `answerMd` | string | Markdown 回答 |
| `answerType` | string | 回答类型 |
| `generationMetadata` | object | 生成元数据 |
| `citations` | array | 引用列表 |

## Enums

| Field | Values |
|---|---|
| `answerType` | `direct_answer`、`clarification`、`insufficient_evidence` |
| `generationMetadata.source` | `model`、`fallback` |

## Citation DTO

| Field | Type | Meaning |
|---|---|---|
| `resourceId` | integer | 来源资源 id |
| `refLabel` | string | 展示引用标签 |
| `pageNo` | integer | PDF 页码 |
| `slideNo` | integer | PPTX 页码 |
| `anchorKey` | string | DOCX anchor |
| `startSec` / `endSec` | integer | 视频定位 |

每条 citation 必须且只能带一组合法定位字段：`pageNo`、`slideNo`、`anchorKey` 或 `startSec + endSec`。

## Integration Notes

| Check | Expected |
|---|---|
| `insufficient_evidence` | `citations` 固定为空数组 |
| AI provider | vivo / DeepSeek 接入不改变请求和响应 DTO |
| Citation identity | public response 不暴露 `segmentId` 或 `segmentKey` |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理 QA DTO 和 citation 联调说明 | 可做 |
| 改 AI 回答策略、候选证据反查或 fallback 策略 | 不做 |
