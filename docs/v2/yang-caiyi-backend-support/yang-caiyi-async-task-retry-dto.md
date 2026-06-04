# Yang Caiyi Async Task Retry DTO

本文整理任务 13：异步任务 retry 接口文档。只整理 retry 适用状态、返回字段和错误码，不修改 dispatcher、broker 或 worker。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | `POST /api/v1/async-tasks/{taskId}/retry` contract |
| `server/api/routers/pipelines.py` | retry router entry |
| `server/domain/services/pipelines.py` | retry service entry |
| `server/domain/services/async_tasks.py` | async task helper |
| `server/tasks/payloads.py` | task payload type source |

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/async-tasks/{taskId}/retry` | 将可重试异步任务重新入队 |

## Response DTO

| Field | Type | Meaning |
|---|---|---|
| `taskId` | integer | 异步任务 id |
| `status` | string | 重置后的任务状态，成功为 `queued` |
| `nextAction` | string | 前端下一步动作，通常为 `poll` |

## Retry Rules

| Item | Contract |
|---|---|
| Retryable status | `failed`、`queued` |
| Non-retryable status | `succeeded`、`canceled`、`retrying`、未知状态 |
| Supported task types | `parse_pipeline`、`handout_generate`、`handout_block_generate`、`quiz_generate`、`review_refresh`、`bilibili_import` |
| Reset behavior | 状态重置为 `queued`，清空旧错误，`progressPct` 置 0 |
| Enqueue failure | 返回 `503 async_task.enqueue_failed`，任务记录保留失败原因 |

## Errors

| HTTP | `errorCode` | Meaning |
|---|---|---|
| 404 | `pipeline.task_not_found` | 任务不存在 |
| 409 | `pipeline.task_not_retryable` | 当前状态不可重试 |
| 409 | `pipeline.task_retry_unsupported` | 任务类型不支持 retry |
| 409 | `pipeline.task_retry_stale` | 重置时发现任务记录已变化或不可写 |
| 503 | `async_task.enqueue_failed` | 入队失败 |

## Integration Record Template

| Field | Value |
|---|---|
| Test time |  |
| Tester | Yang Caiyi |
| Environment | local / docker / Android emulator / real device |
| `taskId` |  |
| Before status |  |
| Response `status` |  |
| Response `nextAction` |  |
| Follow-up poll API |  |
| Conclusion | pass / fail / blocked |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理 retry DTO、错误码和联调记录模板 | 可做 |
| 修改 dispatcher、broker、worker 派发逻辑 | 不做 |
| 定义新的 task type 或 payload 结构 | 需曹乐先冻结 |
