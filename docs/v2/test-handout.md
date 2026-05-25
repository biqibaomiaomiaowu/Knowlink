# V2 Parse And Handout Integration Record

测试人员：杨彩艺  
记录日期：2026-05-25  
关联文档：

- [yang-caiyi-parse-task-dto.md](./yang-caiyi-parse-task-dto.md)
- [yang-caiyi-handout-api-dto.md](./yang-caiyi-handout-api-dto.md)
- [yang-caiyi-async-task-retry-dto.md](./yang-caiyi-async-task-retry-dto.md)

本文记录解析与讲义相关联调。当前实际执行的是 PDF 资源解析，因此验证重点是 `parse/start`、`parse-runs`、`pipeline-status`、`parse/summary` 和 retry 错误返回；讲义 outline / block / jump-target / playback 需要视频资源或讲义生成后继续补测。

## Handout Expected Flow

Handout 模块采用“目录 + 懒生成 block”模式：

- parse 完成后生成 outline。
- outline 中 child 节点绑定 `blockId`。
- block 内容按需生成，不在 parse 阶段全量生成。
- 每个 block 与视频时间段绑定，通过 jump-target 实现跳转。
- 视频播放通过 playback 接口获取预签名 URL。

联调验证预期：

| Check | Expected |
|---|---|
| `pipeline-status.handoutOutline.status` | `ready` when outline is available |
| outline interface | returns parent items and child nodes |
| child node | contains `blockId` |
| block interface | returns valid `generationStatus` |
| jump-target | returns `videoResourceId` and time range when video exists |
| playback | returns reachable `playbackUrl` for mp4 resource |

## Summary

| Interface | Status | Conclusion |
|---|---|---|
| `POST /api/v1/courses/{courseId}/parse/start` | 已测 | 返回 async task，`entity.type=parse_run` |
| `GET /api/v1/parse-runs/{parseRunId}` | 已测 | PDF 解析结果为 `partial_success`，问题为 `embedding.not_configured` |
| `GET /api/v1/courses/{courseId}/pipeline-status` | 已测 | pipeline 可进入 `inquiry_ready`，`vectorize` 失败但整体 `partial_success` |
| `GET /api/v1/courses/{courseId}/parse/summary` | 已测 | 返回 parse summary；实际包含 `latestParseRunId` |
| `POST /api/v1/async-tasks/{taskId}/retry` | 已测 | 当前 `partial_success` 不可 retry，返回预期错误 |
| Handout outline / blocks / jump-target | 待测 | 需要讲义 outline / block 生成条件满足后补测 |
| Playback | 待测 | 需要上传 mp4 视频资源 |

## 1. Start Parse

接口：`POST /api/v1/courses/{courseId}/parse/start`

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "taskId": 1,
    "status": "queued",
    "nextAction": "poll",
    "entity": {
      "type": "parse_run",
      "id": 1
    }
  },
  "requestId": "req_e9ac576c48da4b549c6e626839f717fc",
  "timestamp": "2026-05-25T07:13:02.558174+00:00"
}
```

字段核对：

| Field | Actual | Result |
|---|---|---|
| `taskId` | `1` | match |
| `status` | `queued` | match |
| `nextAction` | `poll` | match |
| `entity.type` | `parse_run` | match |
| `entity.id` | `1` | match |

## 2. Parse Run

接口：`GET /api/v1/parse-runs/{parseRunId}`

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "parseRunId": 1,
    "courseId": 5,
    "status": "partial_success",
    "triggerType": "user_action",
    "sourceParseRunId": null,
    "progressPct": 100,
    "summaryJson": {
      "issues": [
        {
          "code": "embedding.not_configured"
        }
      ],
      "segmentCount": 11,
      "resourceCount": 1,
      "vectorDocumentCount": 0
    },
    "startedAt": "2026-05-25T07:13:02.754765+00:00",
    "finishedAt": "2026-05-25T07:13:03.096791+00:00",
    "createdAt": "2026-05-25T07:13:02.101307+00:00"
  },
  "requestId": "req_f3e9af8f77fd487aaf806d55ce9803b2",
  "timestamp": "2026-05-25T07:16:58.835468+00:00"
}
```

结论：

| Check | Result |
|---|---|
| parse run reached terminal-like state | yes, `partial_success` |
| progress | `100` |
| issue code | `embedding.not_configured` |
| resource count | `1` |
| vector document count | `0` |

说明：本次是 PDF 资料解析，embedding 未配置导致 `partial_success`，不属于杨彩艺需要修复的后端逻辑。

## 3. Pipeline Status

接口：`GET /api/v1/courses/{courseId}/pipeline-status`

实际返回摘要：

| Field | Actual |
|---|---|
| `courseStatus.lifecycleStatus` | `inquiry_ready` |
| `courseStatus.pipelineStage` | `parse` |
| `courseStatus.pipelineStatus` | `partial_success` |
| `progressPct` | `100` |
| `activeParseRunId` | `1` |
| `activeHandoutVersionId` | `null` |
| `nextAction` | `enter_inquiry` |
| `sourceOverview.videoReady` | `false` |
| `sourceOverview.docTypes` | `["pdf"]` |
| `knowledgeMap.status` | `ready` |
| `highlightSummary.items[0]` | `执行失败` |

步骤状态：

| Step | Status | Message |
|---|---|---|
| `resource_validate` | `succeeded` | `已完成` |
| `caption_extract` | `skipped` | `本课程无需执行` |
| `document_parse` | `succeeded` | `已完成` |
| `knowledge_extract` | `succeeded` | `已完成` |
| `vectorize` | `failed` | `执行失败` |

结论：`vectorize` 失败但整体 pipeline 为 `partial_success`，仍可进入问询。这符合 Week 2 contract 中“最低可用链路可继续”的语义。

待确认项：

| Item | Note |
|---|---|
| `handoutOutline` 字段缺失 | 当前 PDF 样例返回中未出现 `handoutOutline`；如前端依赖该字段，需要后端 owner 确认 PDF-only 场景是否允许省略 |
| `knowledgeMap.segmentCount` | pipeline 返回 `0`，parse run summary 中 `segmentCount=11`；如果展示需要一致，需后端 owner 判断两个字段统计口径 |

## 4. Parse Summary

接口：`GET /api/v1/courses/{courseId}/parse/summary`

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "courseId": 5,
    "activeParseRunId": 1,
    "latestParseRunId": 1,
    "segmentCount": 0,
    "knowledgePointCount": 0
  },
  "requestId": "req_667374c1db124276b7c20ce2b227115a",
  "timestamp": "2026-05-25T07:22:14.474458+00:00"
}
```

结论：

| Field | Actual | Note |
|---|---|---|
| `courseId` | `5` | match |
| `activeParseRunId` | `1` | match |
| `latestParseRunId` | `1` | 实际返回字段，DTO 文档可记录为实现字段 |
| `segmentCount` | `0` | 与 parse run summary 统计口径不同，待确认 |
| `knowledgePointCount` | `0` | match |

## 5. Retry Async Task

接口：`POST /api/v1/async-tasks/{taskId}/retry`

实际返回：

```json
{
  "code": 1,
  "message": "Async task in status 'partial_success' cannot be retried.",
  "errorCode": "pipeline.task_not_retryable",
  "data": null,
  "requestId": "req_d479e9b6c37d40c0877c3c468b7979da",
  "timestamp": "2026-05-25T07:24:02.412673+00:00"
}
```

结论：当前任务状态为 `partial_success`，不属于 retry 接口允许的 `failed` / `queued` 状态，因此返回 `pipeline.task_not_retryable` 符合预期。

## 6. Pending Handout Tests

以下接口本次尚未完成实际返回记录：

| Interface | Reason | Next record |
|---|---|---|
| `POST /api/v1/courses/{courseId}/handouts/generate` | 本次主要验证 parse；尚未触发讲义生成 | 记录 `taskId`、`entity.type=handout_version` |
| `GET /api/v1/handout-versions/{handoutVersionId}/status` | 需要 handout version id | 记录 `status`、block counts |
| `GET /api/v1/courses/{courseId}/handouts/latest` | 需要生成讲义 | 记录 `handoutVersionId`、`status` |
| `GET /api/v1/courses/{courseId}/handouts/latest/outline` | 需要 outline 可用 | 记录 parent / child 结构 |
| `GET /api/v1/courses/{courseId}/handouts/latest/blocks` | 需要 block 数据 | 记录 `generationStatus` |
| `GET /api/v1/handout-blocks/{blockId}/jump-target` | 需要 child `blockId` | 记录 video/doc target |
| `GET /api/v1/course-resources/{resourceId}/playback` | 需要 mp4 resource | 记录 `playbackUrl` 可达性 |

## Boundary

| Yang Caiyi can record | Not in Yang Caiyi scope |
|---|---|
| parse response JSON、pipeline steps、errorCode | 修改解析策略 |
| `partial_success` 样例和说明 | 配置 embedding provider |
| retry 错误返回 | 修改 async task 状态机 |
| handout outline / block / jump-target 返回 | 修改讲义生成、懒生成或 citation 反查 |
