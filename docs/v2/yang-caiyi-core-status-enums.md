# 杨彩艺 核心状态枚举说明

来源：

- `docs/contracts/api-contract.md`
- `docs/contracts/week1-cao-le-freeze.md`

用途：整理 V1/MVP 已冻结的核心状态枚举，供杨彩艺做 DTO 文档、状态查询接口说明、Android 联调记录和验收材料时统一口径。本文只整理已冻结状态，不新增状态，不扩写 B站、图谱、SSE、主观题判卷字段。

## 状态总览

| 状态组 | 字段名 | 使用对象 | 冻结取值 | 杨彩艺可做事项 |
|---|---|---|---|---|
| 课程生命周期 | `lifecycleStatus` / `lifecycle_status` | `courses`、课程摘要、课程详情、首页、pipeline status | `draft`、`resource_ready`、`inquiry_ready`、`learning_ready`、`archived`、`failed` | 整理课程列表、课程详情、课程切换、首页展示的状态说明 |
| 当前流程阶段 | `pipelineStage` / `pipeline_stage` | `courses`、pipeline status | `idle`、`upload`、`parse`、`inquiry`、`handout` | 整理解析进度、首页状态、Android 联调记录 |
| 当前流程状态 | `pipelineStatus` / `pipeline_status` | `courses`、pipeline status | `idle`、`queued`、`running`、`partial_success`、`succeeded`、`failed` | 整理轮询状态、失败样例、验收截图说明 |
| 异步任务状态 | `async_tasks.status` | `async_tasks`、异步触发接口、任务状态查询、retry | `queued`、`running`、`succeeded`、`failed`、`retrying`、`canceled`、`skipped` | 整理任务查询、B站状态映射、retry 说明 |
| 讲义版本状态 | `handout_versions.status` | `handout_versions`、讲义版本状态、最新讲义 | `draft`、`generating`、`outline_ready`、`ready`、`partial_success`、`failed`、`superseded` | 整理讲义页、讲义状态查询和 block 生成联调记录 |
| 异步实体类型 | `entity.type` | 异步触发接口响应 | `parse_run`、`handout_version`、`handout_block`、`quiz`、`review_task_run`、`bilibili_import_run` | 整理异步返回统一结构，不新增实体类型 |

## 课程生命周期状态

| 取值 | 已冻结含义 | 常见出现位置 | 联调关注点 |
|---|---|---|---|
| `draft` | 课程已创建，但还未满足最低可解析资源条件 | 创建课程、推荐确认入课、最近课程、课程详情 | 前端应展示为可继续导入资料或补充资源 |
| `resource_ready` | 资源已满足最低可解析条件，可进入解析 | 资源上传完成后、课程状态 | 可作为启动解析前的准备状态 |
| `inquiry_ready` | 解析结果已可支撑问询 | pipeline status、课程状态 | 用户可以进入问询入口 |
| `learning_ready` | 讲义版本已 ready，可进入学习闭环 | 讲义生成后、课程状态、首页 | 用户可以进入讲义、QA、测验、复习等学习链路 |
| `archived` | 课程已归档 | 课程管理相关展示 | V1 contract 有枚举，V2 多课程增强前不要自行扩展归档接口字段 |
| `failed` | 课程主链路进入失败状态 | pipeline status、课程状态 | 需要结合 `pipelineStatus`、错误码和具体接口返回定位原因 |

## 流程阶段状态

| 取值 | 含义 | 常见出现位置 | 联调关注点 |
|---|---|---|---|
| `idle` | 当前没有正在推进的主流程阶段 | 新建课程、最近课程、课程详情 | 通常与 `pipelineStatus=idle` 一起出现 |
| `upload` | 当前处于资源上传阶段 | 资源导入、上传相关页面 | 注意 MinIO public endpoint 是否设备可达 |
| `parse` | 当前处于解析阶段 | `GET /api/v1/courses/{courseId}/pipeline-status` | 前端通常轮询 pipeline status |
| `inquiry` | 当前处于问询阶段 | 问询入口和课程流程 | 与 `inquiry_ready` 区分：一个是阶段，一个是生命周期 |
| `handout` | 当前处于讲义生成或讲义学习阶段 | 讲义生成、讲义页 | 结合讲义版本状态判断 outline 或 block 是否可展示 |

## 流程运行状态

| 取值 | 已冻结含义 | 常见出现位置 | 联调关注点 |
|---|---|---|---|
| `idle` | 未开始或当前没有运行中的流程 | 新建课程、空闲课程 | 可展示为等待用户操作 |
| `queued` | 已入队等待执行 | parse start、异步任务触发后 | 前端可继续轮询 |
| `running` | 正在执行 | pipeline status、任务状态 | 需要展示进度或当前步骤 |
| `partial_success` | 部分资料或步骤失败，但最低条件已满足，课程仍可继续往下游推进 | pipeline status、讲义版本状态 | 不应等同于失败；需要展示降级或部分失败提示 |
| `succeeded` | 当前流程成功 | pipeline status、parse run、任务状态 | 可进入下一步 |
| `failed` | 当前流程失败 | pipeline status、任务状态 | 需要保留错误码、失败原因和复测证据 |

## 异步任务状态

| 取值 | 含义 | 常见出现位置 | 联调关注点 |
|---|---|---|---|
| `queued` | 任务已创建，等待执行 | 异步触发接口、任务查询、retry 后 | 可轮询；retry 接口允许 `failed`、`queued` 状态重试 |
| `running` | 任务正在执行 | 解析、讲义、测验、复习任务 | 需要记录进度字段和阶段字段 |
| `succeeded` | 任务成功完成 | parse、handout、quiz、review 等任务 | 与具体实体结果一起验收 |
| `failed` | 任务失败 | 任务查询、pipeline status | 需要记录错误码和失败原因 |
| `retrying` | 任务正在重试 | 异步任务状态 | retry 中不应重复触发新的重试 |
| `canceled` | 任务已取消 | B站导入映射、任务状态 | V2 拼写统一为 `canceled`，不要写 `cancelled` |
| `skipped` | 任务被跳过 | 异步任务状态 | 需要结合业务上下文说明为何跳过 |

## 讲义版本状态

| 取值 | 已冻结含义 | 常见出现位置 | 联调关注点 |
|---|---|---|---|
| `draft` | 讲义版本草稿状态 | 讲义版本表 | 一般不作为可学习状态 |
| `generating` | 讲义正在生成 | 讲义版本状态、block 状态 | 前端可展示生成中 |
| `outline_ready` | 目录可展示，但 block 正文未全部生成 | `GET /api/v1/handout-versions/{handoutVersionId}/status`、`GET /api/v1/courses/{courseId}/handouts/latest` | 允许先展示目录，再按需生成 block |
| `ready` | 必要 block 已 ready | 最新讲义、讲义版本状态 | 可进入完整学习链路 |
| `partial_success` | 目录可用，但部分 block 失败或降级 | 讲义版本状态 | 不等同于全失败，需要记录哪些 block 失败 |
| `failed` | 讲义生成失败 | 讲义版本状态 | 需要记录失败原因和重试方式 |
| `superseded` | 已被新版本替代 | 讲义版本表 | 前端一般不展示为当前版本 |

## 异步实体类型

| `entity.type` | 对应实体 | 常见触发接口 | 杨彩艺记录重点 |
|---|---|---|---|
| `parse_run` | 解析运行 | `POST /api/v1/courses/{courseId}/parse/start` | 记录 `taskId`、`parseRunId`、轮询入口 |
| `handout_version` | 讲义版本 | `POST /api/v1/courses/{courseId}/handouts/generate` | 记录 `taskId`、`handoutVersionId`、状态查询入口 |
| `handout_block` | 单个讲义块 | `POST /api/v1/handout-blocks/{blockId}/generate` | 记录 block 生成幂等和状态查询 |
| `quiz` | 测验 | `POST /api/v1/courses/{courseId}/quizzes/generate` | 只记录客观题测验生成，不扩写主观题 |
| `review_task_run` | 复习任务重算 | `POST /api/v1/courses/{courseId}/review-tasks/regenerate` | 记录重算任务和状态查询 |
| `bilibili_import_run` | B站导入运行 | B站导入预留 / V2 真实导入 | 只记录已冻结映射和待确认项，不实现下载合并 |

## B站导入状态到异步任务状态的过渡摘要

说明：`api-contract.md` 中明确 V2 B站真实导入 contract 以单独冻结文档为准；下表只整理当前 `api-contract.md` 保留的过渡摘要，杨彩艺不要据此扩写 B站真实 DTO 字段。

| `bilibili_import_run.status` | 映射到 `async_tasks.status` | 说明 |
|---|---|---|
| `pending`、`waiting_download` | `queued` | 等待元数据、排队或等待下载槽位 |
| `fetching_metadata`、`downloading`、`merging`、`uploading` | `running` | 任务正在执行 |
| `imported` | `succeeded` | 已创建课程资源 |
| `failed` | `failed` | 不可恢复失败 |
| `recoverable` | `failed` | 可恢复失败，响应中必须带可重试原因 |
| `canceled` | `canceled` | 用户或系统取消 |

## 联调记录模板

| 记录项 | 示例 | 说明 |
|---|---|---|
| 接口 | `GET /api/v1/courses/{courseId}/pipeline-status` | 写明方法和路径 |
| 课程状态 | `lifecycleStatus=...` | 从响应里原样记录 |
| 流程阶段 | `pipelineStage=...` | 从响应里原样记录 |
| 流程状态 | `pipelineStatus=...` | 从响应里原样记录 |
| 异步任务 | `taskId=...`、`async_tasks.status=...` | 如果接口返回异步任务，则记录 |
| 实体类型 | `entity.type=...` | 只允许使用冻结白名单 |
| 下一步 | `nextAction=...` | 从响应里原样记录，不自行发明 |
| 错误码 | `errorCode=...` | 失败时必须记录 |
| 证据 | 截图、录屏、响应 JSON | 验收时保留 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理状态枚举表 | 新增状态 |
| 整理状态字段说明 | 改复杂状态机 |
| 整理查询接口联调记录 | 实现 B站下载、ffmpeg 合并、取消副作用 |
| 整理失败状态和错误码样例 | 设计图谱生成、SSE 事件协议、主观题判卷策略 |
| 对齐前端展示用字段 | 把 V1 stub 当成 V2 真实导入字段来源 |
