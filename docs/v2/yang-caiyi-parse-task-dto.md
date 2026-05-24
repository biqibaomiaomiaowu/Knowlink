# 杨彩艺 解析任务接口 DTO 文档

来源：`docs/contracts/api-contract.md`

用途：整理解析启动、解析运行状态、课程 pipeline status 和解析摘要接口 DTO，供杨彩艺做状态查询接口说明、联调记录和验收材料。本文只整理 API 请求/响应形态，不改解析策略、worker、AI 或任务队列逻辑。

## 接口清单

| 接口 | 方法 | 路径 | 用途 | 幂等要求 |
|---|---|---|---|---|
| 启动解析 | `POST` | `/api/v1/courses/{courseId}/parse/start` | 为课程启动解析异步任务 | 必须支持 `Idempotency-Key` |
| 解析运行状态 | `GET` | `/api/v1/parse-runs/{parseRunId}` | 查询 parse run 状态 | 无 |
| 课程 pipeline 状态 | `GET` | `/api/v1/courses/{courseId}/pipeline-status` | Flutter 主轮询入口 | 无 |
| 解析摘要 | `GET` | `/api/v1/courses/{courseId}/parse/summary` | 解析完成后的辅助摘要接口 | 无 |

## 启动解析响应 DTO

接口：`POST /api/v1/courses/{courseId}/parse/start`

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `taskId` | number | `7001` | 异步任务 ID |
| `status` | string | `queued` | 异步任务状态 |
| `nextAction` | string | `poll` | 下一步动作 |
| `entity.type` | string | `parse_run` | 异步实体类型 |
| `entity.id` | number | `9001` | parse run ID |

## 解析运行状态 DTO

接口：`GET /api/v1/parse-runs/{parseRunId}`

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `parseRunId` | number | `9001` | 解析运行 ID |
| `courseId` | number | `101` | 所属课程 ID |
| `status` | string | `succeeded` | 解析运行状态 |
| `progressPct` | number | `100` | 进度百分比 |
| `startedAt` | string, datetime | `2026-04-18T15:00:00+00:00` | 开始时间 |
| `finishedAt` | string, datetime/null | `2026-04-18T15:00:05+00:00` | 结束时间 |

## Pipeline Status 响应 DTO

接口：`GET /api/v1/courses/{courseId}/pipeline-status`

| 字段 | 类型 | 说明 |
|---|---|---|
| `courseStatus` | object | 课程生命周期、流程阶段、流程状态 |
| `progressPct` | number | 聚合进度百分比 |
| `steps` | array | 聚合步骤列表 |
| `activeParseRunId` | number/null | 当前解析运行 ID |
| `activeHandoutVersionId` | number/null | 当前讲义版本 ID |
| `nextAction` | string | 下一步动作 |
| `sourceOverview` | object | 解析来源概览 |
| `knowledgeMap` | object | 知识点/段落概览 |
| `handoutOutline` | object | 讲义目录概览 |
| `highlightSummary` | object | 高亮信息摘要 |

`courseStatus`：

| 字段 | 示例 | 说明 |
|---|---|---|
| `lifecycleStatus` | `inquiry_ready` | 课程生命周期状态 |
| `pipelineStage` | `parse` | 当前流程阶段 |
| `pipelineStatus` | `succeeded` | 当前流程状态 |

`steps[]` 固定聚合 code：

| `code` | 说明 |
|---|---|
| `resource_validate` | 资源校验 |
| `caption_extract` | 字幕提取 |
| `document_parse` | 文档解析 |
| `knowledge_extract` | 在视频优先链路中表示生成 `handoutOutline`，不表示全量知识点已生成 |
| `vectorize` | 向量化 |

`pipelineStatus = partial_success` 说明：

| 口径 | 说明 |
|---|---|
| 含义 | 解析产物已满足进入问询或讲义 outline 的最低条件，但存在非关键资源或非关键步骤失败 |
| 下一步 | `nextAction` 仍可为 `enter_inquiry` 或 `enter_handout_outline` |
| 联调记录 | 需要记录失败步骤、可继续入口和截图/响应 JSON |

## 解析摘要 DTO

接口：`GET /api/v1/courses/{courseId}/parse/summary`

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `courseId` | number | `101` | 课程 ID |
| `activeParseRunId` | number/null | `9001` | 当前解析运行 ID |
| `segmentCount` | number | `12` | 段落数量 |
| `knowledgePointCount` | number | `0` | 知识点数量 |
| `generatedKnowledgePointCount` | number | `0` | 已生成知识点数量 |
| `handoutOutlineStatus` | string | `ready` | 讲义目录状态 |
| `outlineItemCount` | number | `3` | 目录项数量 |

说明：Flutter 主轮询入口仍然是 `GET /api/v1/courses/{courseId}/pipeline-status`。

## 联调记录模板

| 记录项 | 填写内容 |
|---|---|
| 测试时间 |  |
| 课程 ID |  |
| 启动解析响应 `taskId` |  |
| `entity.type` | `parse_run` |
| `parseRunId` |  |
| pipeline `lifecycleStatus` |  |
| pipeline `pipelineStage` |  |
| pipeline `pipelineStatus` |  |
| `progressPct` |  |
| `steps[]` 状态 |  |
| `nextAction` |  |
| `sourceOverview` 摘要 |  |
| `handoutOutline` 摘要 |  |
| 错误码 |  |
| 证据 | 响应 JSON、截图或录屏 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理解析接口 DTO | 改解析 pipeline 策略 |
| 整理 pipeline 状态记录 | 改 worker / Dramatiq / dispatcher |
| 记录 `partial_success` 样例 | 改 AI 解析或知识抽取 |
| 准备联调证据 | 新增解析步骤或状态枚举 |
