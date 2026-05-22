# KnowLink API Contract

本文件冻结第一版（V1/MVP）前后端共享的请求字段、响应字段、异步返回结构和 demo 鉴权策略。曹乐 owner 的 Week 1 冻结项与固定联调资料集基线见 [week1-cao-le-freeze.md](./week1-cao-le-freeze.md) 和 [../v1/demo-assets-baseline.md](../v1/demo-assets-baseline.md)；Week 2 解析与问询业务 contract 见 [week2-cao-le-parse-inquiry-contract.md](./week2-cao-le-parse-inquiry-contract.md)。若与其他 V1 文档冲突，以本文件为准。V2 功能范围、负责人分工和验收口径以根目录 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准；V2 进入实现前必须同步更新本文件或新增 V2 contract 文档，不能用本文的 V1 stub 口径否定 V2 计划。

## 1. 通用约定

- 所有业务接口前缀为 `/api/v1`。
- 除 `/health` 外，所有接口都要求 `Authorization: Bearer <token>`。
- MVP 鉴权策略固定为单 demo 用户；token 来自 `.env` 中的 `KNOWLINK_DEMO_TOKEN`。
- MVP 资料类型承诺为 `mp4`、`pdf`、`pptx`、`docx`，`srt` 作为可选辅助输入。
- 引用字段约定：
  - `pageNo` 用于 PDF
  - `slideNo` 用于 PPTX
  - `anchorKey` 用于 DOCX
  - `startSec` / `endSec` 用于视频定位
  - 每条 citation 必须且只能带一组合法定位字段：`pageNo` / `slideNo` / `anchorKey` / `startSec+endSec`
  - handout block / jump-target 可以同时暴露视频时间与文档跳转信息，但这些字段不能混在同一条 citation 里
  - 每条 normalized segment 也必须且只能带与 `resourceType` 匹配的定位字段
  - API public citations 只暴露 `resourceId`、`refLabel` 和 locator 字段；`segmentId` / `segmentKey` 仅作为服务端反查、落库和 AI 策略内部 identity，不出现在 public citation 响应中
- 以下写接口必须支持 `Idempotency-Key`：
  - `POST /api/v1/courses`
  - `POST /api/v1/recommendations/{catalogId}/confirm`
  - `POST /api/v1/courses/{courseId}/resources/imports/bilibili`
  - `POST /api/v1/courses/{courseId}/resources/upload-complete`
  - `POST /api/v1/courses/{courseId}/parse/start`
  - `POST /api/v1/courses/{courseId}/handouts/generate`
  - `POST /api/v1/handout-blocks/{blockId}/generate`
  - `POST /api/v1/courses/{courseId}/quizzes/generate`
  - `POST /api/v1/courses/{courseId}/review-tasks/regenerate`
- 幂等 key 的匹配范围为具体业务 scope，不是全局 key；带 `courseId`、`blockId`、`quizId` 等路径 identity 的接口必须把 identity 纳入 scope。
- 服务端必须保存请求体规范化后的 request fingerprint；同一 scope + `Idempotency-Key` + 相同请求体可回放，同一 scope + `Idempotency-Key` + 不同请求体必须返回 `409 idempotency.body_mismatch`。
- 已开始但尚未完成的同一 scope + `Idempotency-Key` 请求必须返回 `409 common.idempotency_replay`，不得创建第二份业务实体。
- 带路径参数的课程接口一律以 path 中的 `courseId` 为准；请求体不再重复传同义 `courseId`，`POST /api/v1/qa/messages` 是唯一例外。
- Docker / runtime 默认任务队列为 `KNOWLINK_TASK_QUEUE=dramatiq`；`noop` dispatcher 只允许通过显式设置 `KNOWLINK_TASK_QUEUE=noop` 用于本地测试或开发，不得作为运行时默认。未知 `KNOWLINK_TASK_QUEUE` 值必须启动失败。
- Dramatiq actor 默认使用 `KNOWLINK_DRAMATIQ_QUEUE`；可通过 `KNOWLINK_DRAMATIQ_PARSE_QUEUE`、`KNOWLINK_DRAMATIQ_CONTENT_QUEUE`、`KNOWLINK_DRAMATIQ_QUIZ_QUEUE`、`KNOWLINK_DRAMATIQ_REVIEW_QUEUE` 分别覆盖 parse / content / quiz / review actor 队列。`KNOWLINK_DRAMATIQ_IMPORT_QUEUE`、`KNOWLINK_DRAMATIQ_MAINTENANCE_QUEUE` 为 V2 后续 import / maintenance actor 预留队列变量。未设置覆盖变量时必须回落到默认队列。
- `KNOWLINK_ENV=production` / `prod` / `staging` 时，demo 鉴权 token、MinIO 默认凭据、`KNOWLINK_TASK_QUEUE=noop`、非 `sql` 的 `KNOWLINK_RUNTIME_REPOSITORY_BACKEND`，以及 `demo` / `fake` / `memory` / `local` / `disabled` 等非持久化或禁用型 `KNOWLINK_STORAGE_BACKEND` 必须启动前 fail-fast；本地 `development` / test 仍可使用 `.env.example` 的 demo 默认值。
- scheduler 当前没有真实生产定时任务，默认 `KNOWLINK_SCHEDULER_ENABLED=false`，且默认 compose 不启动 scheduler 服务；如需手动运行，必须显式启用该环境变量。

### 1.1 Week 1 冻结入口

- 曹乐负责的表语义、状态枚举、推荐理由文案和固定联调资料集基线，以 [week1-cao-le-freeze.md](./week1-cao-le-freeze.md) 为验收入口。
- 固定联调资料集只版本化清单与规范，不在仓库中提交 `mp4/pdf/pptx/docx` 二进制样例。
- demo 鉴权变量名固定为 `.env` / `.env.example` 中的 `KNOWLINK_DEMO_TOKEN`。

### 1.2 Week 2 解析与问询冻结入口

- 曹乐负责的解析产物字段说明、解析步骤映射、`pipeline-status` 进度 / 状态 / 失败 / `partial_success` 语义，以及问询题到 `learning_preferences` 的映射，以 [week2-cao-le-parse-inquiry-contract.md](./week2-cao-le-parse-inquiry-contract.md) 为验收入口。
- 本文件中的 API 示例只展示接口形态；解析产物和问询落库的业务含义以 Week 2 冻结入口为准。

### 1.3 V2 contract 过渡口径

- `docs/v2/phase-plan.md` 是第二版的规划和责任口径，不直接等同于已实现 API。
- V2 新增或重做 B站真实导入、知识图谱、实时流式输出、主观题自动判卷时，必须先补充对应 API / DTO / schema / 错误码 contract，再实施代码。
- V2 B站真实导入 contract 已单独冻结在 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md)；该文档覆盖本文 B站 V1 `501` stub 的历史口径。
- V2 B站导入不再受本文 B站 `501` stub 约束；V1 stub 仅表示当前第一版实现状态。
- V2 状态拼写统一使用 `canceled`，不使用 `cancelled`。外部资料或旧 spec 中出现 `cancelled` 时，进入 API contract 前统一归一化为 `canceled`。
- V2 B站导入细分状态到 `async_tasks.status` 的完整冻结映射以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准；本文仅保留过渡摘要：

| `bilibili_import_run.status` | `async_tasks.status` | 说明 |
|---|---|---|
| `pending`、`waiting_download` | `queued` | 等待元数据、排队或等待下载槽位 |
| `fetching_metadata`、`downloading`、`merging`、`uploading` | `running` | 任务正在执行 |
| `imported` | `succeeded` | 已创建课程资源 |
| `failed` | `failed` | 不可恢复失败 |
| `recoverable` | `failed` | 可恢复失败，响应中必须带可重试原因 |
| `canceled` | `canceled` | 用户或系统取消 |

- V2 实时输出默认复用 `async_tasks.id` 作为任务真相源；SSE 订阅优先使用 `/api/v1/async-tasks/{taskId}/events`，若后续增加 `/api/v1/tasks` 聚合层，只能作为 `async_tasks` 的只读适配层。
- V2 知识图谱需要补充 graph read model contract，至少冻结节点、边、证据引用、置信度、审核状态和跳转目标。
- V2 主观题判卷需要补充主观题 schema、attempt/grading API、判卷状态、评分结果、证据引用和低置信度人审字段。

### 1.4 核心状态枚举

- `lifecycleStatus`: `draft` `resource_ready` `inquiry_ready` `learning_ready` `archived` `failed`
- `pipelineStage`: `idle` `upload` `parse` `inquiry` `handout`
- `pipelineStatus`: `idle` `queued` `running` `partial_success` `succeeded` `failed`
- `async_tasks.status`: `queued` `running` `succeeded` `failed` `retrying` `canceled` `skipped`
- `handout_versions.status`: `draft` `generating` `outline_ready` `ready` `partial_success` `failed` `superseded`
- 异步触发接口返回的 `entity.type` 白名单：`parse_run` `handout_version` `handout_block` `quiz` `review_task_run` `bilibili_import_run`

讲义版本状态语义：

- `outline_ready`：目录可展示但 block 正文未全生成。
- `ready`：必要 block 全 ready。
- `partial_success`：目录可用但部分 block 失败或降级。

## 2. 统一成功响应

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "req_8d9d...",
  "timestamp": "2026-04-18T15:00:00+00:00"
}
```

## 3. 统一失败响应

```json
{
  "code": 1,
  "message": "Authorization token is missing.",
  "errorCode": "auth.token_missing",
  "data": null,
  "requestId": "req_8d9d...",
  "timestamp": "2026-04-18T15:00:00+00:00"
}
```

完整错误码见 [error-codes.md](./error-codes.md)。

## 4. 推荐链路

### `POST /api/v1/recommendations/courses`

请求：

```json
{
  "goalText": "高等数学期末复习",
  "selfLevel": "intermediate",
  "timeBudgetMinutes": 240,
  "examAt": "2026-06-15T09:00:00+08:00",
  "preferredStyle": "exam"
}
```

响应 `data`：

```json
{
  "recommendations": [
    {
      "catalogId": "math-final-01",
      "title": "高等数学期末冲刺",
      "provider": "KnowLink Seed",
      "level": "intermediate",
      "estimatedHours": 4,
      "fitScore": 96,
      "reasons": [
        "难度与当前基础匹配",
        "时长可在当前预算内完成",
        "目标关键词与课程主题高度一致"
      ],
      "reasonMaterials": [
        "覆盖高频考点",
        "适合考前冲刺",
        "讲义和视频能组成完整复习闭环"
      ],
      "nextAction": {
        "type": "confirm_course",
        "label": "确认入课并导入资料"
      },
      "defaultResourceManifest": [
        {
          "resourceType": "mp4",
          "required": true,
          "description": "主课程视频"
        },
        {
          "resourceType": "pdf",
          "required": true,
          "description": "配套讲义 PDF"
        },
        {
          "resourceType": "pptx",
          "required": false,
          "description": "配套课件 PPTX"
        },
        {
          "resourceType": "docx",
          "required": false,
          "description": "补充讲义 DOCX"
        },
        {
          "resourceType": "srt",
          "required": false,
          "description": "字幕文件"
        }
      ]
    }
  ],
  "requestEcho": {
    "goalText": "高等数学期末复习",
    "selfLevel": "intermediate",
    "timeBudgetMinutes": 240,
    "examAt": "2026-06-15T09:00:00+08:00",
    "preferredStyle": "exam"
  }
}
```

排序与理由约束：

- `recommendations` 按 `fitScore` 降序返回。
- 若 `fitScore` 相同，保持 `server/seeds/course_catalog.json` 中的种子顺序。
- `reasons[]` 优先使用 Week 1 冻结文案；V2 若匹配上下文不足 3 条，可从当前 catalog 的 `reasonMaterials[]` 补足展示理由：
  - `难度与当前基础匹配`
  - `难度可控，适合作为过渡课程`
  - `时长可在当前预算内完成`
  - `需要拆分学习节奏，但仍可安排`
  - `目标关键词与课程主题高度一致`
  - `讲义风格与当前偏好一致`
- `reasonMaterials[]` 来自 `server/seeds/course_catalog.json`，用于课程详情页和推荐卡片解释，不参与排序。
- `nextAction.type = confirm_course` 表示前端下一步调用 `POST /api/v1/recommendations/{catalogId}/confirm`。

### `POST /api/v1/recommendations/{catalogId}/confirm`

请求：

```json
{
  "goalText": "高等数学期末复习",
  "examAt": "2026-06-15T09:00:00+08:00",
  "preferredStyle": "exam",
  "titleOverride": "高数期末冲刺课"
}
```

响应 `data`：

```json
{
  "course": {
    "courseId": 101,
    "title": "高数期末冲刺课",
    "entryType": "recommendation",
    "catalogId": "math-final-01",
    "lifecycleStatus": "draft",
    "pipelineStage": "idle",
    "pipelineStatus": "idle",
    "updatedAt": "2026-04-18T15:00:00+00:00"
  },
  "createdFromCatalogId": "math-final-01"
}
```

说明：

- `resourceType` 可取 `mp4`、`pdf`、`pptx`、`docx`、`srt`。
- `pptx` 与 `docx` 在 MVP 已经占位到 contract 和代码骨架，真实解析保真可渐进增强。

## 5. 课程与首页

### `POST /api/v1/courses`

请求：

```json
{
  "title": "KnowLink 固定联调课",
  "entryType": "manual_import",
  "goalText": "期末复习",
  "examAt": "2026-06-20T09:00:00+08:00",
  "preferredStyle": "balanced"
}
```

响应 `data.course` 与推荐确认接口保持同结构。

### `GET /api/v1/courses/recent`

响应 `data`：

```json
{
  "items": [
    {
      "courseId": 101,
      "title": "高数期末冲刺课",
      "entryType": "recommendation",
      "catalogId": "math-final-01",
      "lifecycleStatus": "draft",
      "pipelineStage": "idle",
      "pipelineStatus": "idle",
      "updatedAt": "2026-04-18T15:00:00+00:00"
    }
  ]
}
```

### `GET /api/v1/courses/{courseId}`

响应 `data`：

```json
{
  "course": {
    "courseId": 101,
    "title": "高数期末冲刺课",
    "entryType": "recommendation",
    "catalogId": "math-final-01",
    "goalText": "高等数学期末复习",
    "examAt": "2026-06-20T09:00:00+08:00",
    "preferredStyle": "exam",
    "lifecycleStatus": "draft",
    "pipelineStage": "idle",
    "pipelineStatus": "idle",
    "updatedAt": "2026-05-19T12:00:00+00:00"
  }
}
```

### `POST /api/v1/courses/{courseId}/switch-current`

响应 `data`：

```json
{
  "currentCourseId": 101,
  "course": {
    "courseId": 101,
    "title": "高数期末冲刺课",
    "entryType": "recommendation",
    "catalogId": "math-final-01",
    "lifecycleStatus": "draft",
    "pipelineStage": "idle",
    "pipelineStatus": "idle",
    "updatedAt": "2026-05-19T12:00:00+00:00"
  }
}
```

### `GET /api/v1/courses/current`

响应 `data.course` 与课程详情接口保持同结构。阶段一当前课程语义为单用户基础语义：显式切换后返回该课程；若没有显式切换，返回最近更新课程。

### `GET /api/v1/home/dashboard`

响应 `data`：

```json
{
  "recentCourses": [],
  "topReviewTasks": [],
  "recommendationEntryEnabled": true,
  "dailyRecommendedKnowledgePoints": [
    {
      "knowledgePoint": "极限定义",
      "reason": "高频考点且建议今天优先回看",
      "targetCourseId": 101
    }
  ],
  "learningStats": {
    "streakDays": 3,
    "completedCourses": 1,
    "reviewTasksCompleted": 2,
    "totalLearningMinutes": 95
  }
}
```

## 6. 上传与解析

解析产物、步骤聚合、`partial_success` 判定和问询偏好落库规则见 [week2-cao-le-parse-inquiry-contract.md](./week2-cao-le-parse-inquiry-contract.md)。本节只冻结 API 请求 / 响应形态。

### `POST /api/v1/courses/{courseId}/resources/upload-init`

请求：

```json
{
  "resourceType": "pdf",
  "filename": "chapter-1.pdf",
  "mimeType": "application/pdf",
  "sizeBytes": 32768,
  "checksum": "sha256:demo"
}
```

响应 `data`：

```json
{
  "uploadUrl": "http://127.0.0.1:9000/knowlink/raw/1/101/temp/chapter-1.pdf?...",
  "objectKey": "raw/1/101/temp/chapter-1.pdf",
  "headers": {
    "x-amz-meta-course-id": "101"
  },
  "expiresAt": "2026-04-18T15:15:00+00:00"
}
```

本地 Docker 联调时，`uploadUrl` 必须使用浏览器可访问的 `KNOWLINK_MINIO_PUBLIC_ENDPOINT`
签名，例如 `http://127.0.0.1:9000/...`；不能返回容器内 hostname `minio:9000`。

### `POST /api/v1/courses/{courseId}/resources/upload-complete`

说明：

- 该接口只确认对象存储中上传结果并登记 `course_resources`；不得同步执行解析、OCR、向量化、讲义生成、B站下载合并或 AI 调用。
- 成功返回后，前端可以立即刷新资源列表；解析仍由 `POST /api/v1/courses/{courseId}/parse/start` 或后续后台策略显式触发。

请求：

```json
{
  "resourceType": "pdf",
  "objectKey": "raw/1/101/temp/chapter-1.pdf",
  "originalName": "chapter-1.pdf",
  "mimeType": "application/pdf",
  "sizeBytes": 32768,
  "checksum": "sha256:demo"
}
```

响应 `data`：

```json
{
  "resourceId": 501,
  "ingestStatus": "ready",
  "validationStatus": "passed",
  "processingStatus": "pending"
}
```

### `GET /api/v1/courses/{courseId}/resources`

响应 `data`：

```json
{
  "items": [
    {
      "resourceId": 501,
      "resourceType": "pdf",
      "originalName": "chapter-1.pdf",
      "objectKey": "raw/1/101/temp/chapter-1.pdf",
      "ingestStatus": "ready",
      "validationStatus": "passed",
      "processingStatus": "pending"
    }
  ]
}
```

### `GET /api/v1/course-resources/{resourceId}/playback`

说明：

- 讲义页通过 `GET /api/v1/handout-blocks/{blockId}/jump-target` 拿到 `videoResourceId` 后，使用该接口换取真实可播放地址。
- `playbackUrl` 是对象存储预签名 GET 地址，默认 1 小时有效；本地 Docker 联调必须返回 `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 对应的浏览器可访问 host，例如 `http://127.0.0.1:9000/...`，不能返回容器内 `minio:9000`。
- `durationSec` 当前没有稳定字段时返回 `null`，不为播放接口新增数据库字段。

响应 `data`：

```json
{
  "resourceId": 501,
  "resourceType": "mp4",
  "playbackUrl": "http://127.0.0.1:9000/knowlink/raw/1/101/temp/video.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256",
  "mimeType": "video/mp4",
  "expiresAt": "2026-04-18T16:00:00+00:00",
  "durationSec": null
}
```

错误：

- `404 resource.not_found`：资源不存在或不属于当前用户可访问课程
- `409 resource.not_video`：资源存在但 `resourceType` 不是 `mp4`
- `503 resource.playback_unavailable`：对象存储不可用或播放地址生成失败

### `DELETE /api/v1/courses/{courseId}/resources/{resourceId}`

响应 `data`：

```json
{
  "deleted": true,
  "resourceId": 501
}
```

错误：

- `404 resource.not_found`：资源不存在或不属于当前课程
- `409 resource.has_dependents`：资源已被解析段落、向量文档、讲义引用、QA 引用、测验引用、复习引用或学习进度等后端产物引用；当前接口不做级联删除，需先清理或重建依赖产物后再删除资源

### B 站导入预留接口（V1/MVP）

以下接口参考 `bilidown` 的“单视频 + 登录态 + 任务状态”分层方式冻结 V1/MVP contract，但当前 V1 服务统一返回 `501 Not Implemented`，不创建真实任务、不触发 MinIO 写入，也不接通扫码登录。V2 将按 [docs/v2/phase-plan.md](../v2/phase-plan.md) 接通真实扫码登录、下载、合并、MinIO 上传和课程资源导入；V2 B站真实导入 contract 已冻结在 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md)，本文下方示例只作为 V1 历史 stub 形状保留，不作为 V2 字段来源。

stub 阶段约束：

- 鉴权通过后，所有 B 站预留接口统一返回 `501 bilibili.not_implemented`
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili` 在 stub 阶段不因请求体缺失或 `videoUrl` 为空而改为返回 `422`
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili` 的 OpenAPI 仍保留 `videoUrl` 请求字段，便于前端和生成客户端对齐预留 contract

### `POST /api/v1/courses/{courseId}/resources/imports/bilibili`

请求：

```json
{
  "videoUrl": "https://www.bilibili.com/video/BV1LLDCYJEU3/"
}
```

说明：

- V1 stub 阶段会保留上述 `requestBody` 结构，但暂不收紧为必填校验；鉴权通过后统一返回 `501`。

V2 B站真实导入创建响应、请求字段和选择语义以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准；本文不再复制 V2 示例，避免旧 `videoUrl` stub 字段被误用为 V2 contract。

V1 约束：

- 第一版只冻结单个公开视频链接，不覆盖番剧、合集、收藏夹和批量导入。
- 支持范围只包含标准视频页链接、`BV` 链接和 `b23.tv` 短链。
- V2 真实导入的异步导入实体类型、范围和 DTO 字段以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`

V1 历史 stub 阶段没有真实列表数据；V2 列表响应字段以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `GET /api/v1/bilibili-import-runs/{importRunId}/status`

V1 历史 stub 阶段没有真实状态数据；V2 状态响应字段以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

V1 历史 stub 阶段不会执行真实取消；V2 取消响应和副作用清理语义以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `POST /api/v1/bilibili/auth/qr/sessions`

V1 历史 stub 阶段不会创建真实扫码会话；V2 QR DTO 以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`

V1 历史 stub 阶段不会查询真实扫码状态；V2 QR DTO 以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `GET /api/v1/bilibili/auth/session`

V1 历史 stub 阶段不会查询真实 B站登录态；V2 auth session DTO 以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

### `DELETE /api/v1/bilibili/auth/session`

V1 历史 stub 目标响应形状如下；当前未实现阶段仍统一返回 `501`，V2 auth session 删除 DTO 以 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md) 为准。

```json
{
  "deleted": true
}
```

V1 当前未实现阶段统一返回：

```json
{
  "code": 1,
  "message": "Bilibili import and auth contract is reserved but not implemented yet.",
  "errorCode": "bilibili.not_implemented",
  "data": null,
  "requestId": "req_8d9d...",
  "timestamp": "2026-04-18T15:00:00+00:00"
}
```

### `POST /api/v1/courses/{courseId}/parse/start`

响应 `data`：

```json
{
  "taskId": 7001,
  "status": "queued",
  "nextAction": "poll",
  "entity": {
    "type": "parse_run",
    "id": 9001
  }
}
```

### `GET /api/v1/parse-runs/{parseRunId}`

响应 `data`：

```json
{
  "parseRunId": 9001,
  "courseId": 101,
  "status": "succeeded",
  "progressPct": 100,
  "startedAt": "2026-04-18T15:00:00+00:00",
  "finishedAt": "2026-04-18T15:00:05+00:00"
}
```

### `GET /api/v1/courses/{courseId}/pipeline-status`

响应 `data`：

```json
{
  "courseStatus": {
    "lifecycleStatus": "inquiry_ready",
    "pipelineStage": "parse",
    "pipelineStatus": "succeeded"
  },
  "progressPct": 100,
  "steps": [
    {
      "code": "resource_validate",
      "label": "资源校验",
      "status": "succeeded"
    }
  ],
  "activeParseRunId": 9001,
  "activeHandoutVersionId": null,
  "nextAction": "enter_handout_outline",
  "sourceOverview": {
    "videoReady": true,
    "outlineReady": true,
    "outlineItemCount": 3,
    "docTypes": ["pdf", "pptx", "docx"],
    "organizedSourceCount": 3
  },
  "knowledgeMap": {
    "status": "deferred",
    "knowledgePointCount": 0,
    "segmentCount": 12
  },
  "handoutOutline": {
    "status": "ready",
    "outlineItemCount": 3,
    "generatedBlockCount": 0
  },
  "highlightSummary": {
    "status": "ready",
    "items": [
      "视频目录已生成，可进入讲义页",
      "完整讲义与知识点将在点击目录后按段生成"
    ]
  }
}
```

说明：

- `steps[].code` 固定聚合为 `resource_validate`、`caption_extract`、`document_parse`、`knowledge_extract`、`vectorize`。
- `knowledge_extract` 在视频优先链路中表示生成 `handoutOutline`，不表示全量 `knowledge_points` 已生成；完整知识点随讲义 block 逐段补齐。
- `pipelineStatus = partial_success` 表示解析产物已满足进入问询或讲义 outline 的最低条件，但存在非关键资源或非关键步骤失败；此时 `nextAction` 仍可为 `enter_inquiry` 或 `enter_handout_outline`。
- `progressPct`、步骤权重、失败条件和 `partial_success` 细则以 [week2-cao-le-parse-inquiry-contract.md](./week2-cao-le-parse-inquiry-contract.md) 第 3 节为准。

### `GET /api/v1/courses/{courseId}/parse/summary`

响应 `data`：

```json
{
  "courseId": 101,
  "activeParseRunId": 9001,
  "segmentCount": 12,
  "knowledgePointCount": 0,
  "generatedKnowledgePointCount": 0,
  "handoutOutlineStatus": "ready",
  "outlineItemCount": 3
}
```

说明：

- 这是解析完成后的辅助摘要接口。
- Flutter 主轮询入口仍然是 `GET /api/v1/courses/{courseId}/pipeline-status`。

### `POST /api/v1/async-tasks/{taskId}/retry`

响应 `data`：

```json
{
  "taskId": 7001,
  "status": "queued",
  "nextAction": "poll"
}
```

说明：

- 这是后端和演示排障用辅助接口，不作为页面主流程依赖。
- 只有 `failed`、`queued` 状态可通过该接口重新入队；`succeeded`、`canceled`、`retrying` 或未知状态不得重试。
- 重新入队前会把任务状态重置为 `queued`、清空旧错误并将 `progressPct` 置 0；如果 enqueue 失败，任务会被标记为 `failed` 且写入 `async_task.enqueue_failed`，客户端可继续展示重试入口。

错误：

- `404 pipeline.task_not_found`：任务不存在
- `409 pipeline.task_not_retryable`：任务当前状态不可重试
- `409 pipeline.task_retry_unsupported`：任务类型不支持该 retry 接口
- `409 pipeline.task_retry_stale`：任务状态重置为 `queued` 时发现记录已变化或不可写
- `503 async_task.enqueue_failed`：任务创建或 retry 时写入成功但派发到队列失败；响应代表后端未能把任务交给 dispatcher / broker，任务记录会保留失败原因

## 7. 问询与讲义

### `GET /api/v1/courses/{courseId}/inquiry/questions`

响应 `data`：

```json
{
  "version": 1,
  "questions": [
    {
      "key": "goal_type",
      "label": "当前学习目标",
      "type": "single_select",
      "required": true,
      "options": [
        {
          "label": "期末复习",
          "value": "final_review"
        },
        {
          "label": "考研冲刺",
          "value": "exam_sprint"
        }
      ]
    },
    {
      "key": "mastery_level",
      "label": "当前掌握程度",
      "type": "single_select",
      "required": true,
      "options": [
        {
          "label": "零基础",
          "value": "beginner"
        },
        {
          "label": "基础一般",
          "value": "intermediate"
        },
        {
          "label": "已经学过，想查漏补缺",
          "value": "advanced"
        }
      ]
    },
    {
      "key": "time_budget_minutes",
      "label": "本轮学习时间预算",
      "type": "number",
      "required": true,
      "options": [],
      "minValue": 30,
      "maxValue": 600
    },
    {
      "key": "handout_style",
      "label": "讲义风格偏好",
      "type": "single_select",
      "required": true,
      "options": [
        {
          "label": "考试冲刺",
          "value": "exam"
        },
        {
          "label": "平衡讲解",
          "value": "balanced"
        },
        {
          "label": "详细解释",
          "value": "detailed"
        }
      ]
    },
    {
      "key": "explanation_granularity",
      "label": "解释粒度",
      "type": "single_select",
      "required": true,
      "options": [
        {
          "label": "只看重点",
          "value": "quick"
        },
        {
          "label": "关键步骤",
          "value": "balanced"
        },
        {
          "label": "完整推导",
          "value": "detailed"
        }
      ]
    }
  ]
}
```

说明：`number` 类型题目当前仅用于 `time_budget_minutes`，服务端下发并强制校验 `minValue: 30`、`maxValue: 600`。

### `POST /api/v1/courses/{courseId}/inquiry/answers`

请求：

```json
{
  "answers": [
    {
      "key": "goal_type",
      "value": "final_review"
    }
  ]
}
```

响应 `data`：

```json
{
  "saved": true,
  "answerCount": 1
}
```

### `POST /api/v1/courses/{courseId}/handouts/generate`

响应 `data`：

```json
{
  "taskId": 7101,
  "status": "queued",
  "nextAction": "poll",
  "entity": {
    "type": "handout_version",
    "id": 3001
  }
}
```

### `GET /api/v1/handout-versions/{handoutVersionId}/status`

响应 `data`：

```json
{
  "handoutVersionId": 3001,
  "status": "outline_ready",
  "outlineStatus": "ready",
  "totalBlocks": 3,
  "readyBlocks": 0,
  "pendingBlocks": 3,
  "sourceParseRunId": 9001
}
```

### `GET /api/v1/courses/{courseId}/handouts/latest`

响应 `data`：

```json
{
  "handoutVersionId": 3001,
  "title": "高数期末冲刺讲义",
  "summary": "按考试优先级整理的知识块",
  "totalBlocks": 3,
  "status": "outline_ready"
}
```

说明：

- `status = outline_ready` 表示目录已可展示，但并不要求所有 block 正文已生成。
- block 正文生成完成后，可进入 `ready`；部分失败时返回 `partial_success` 并在 block 级暴露失败状态。

### `GET /api/v1/courses/{courseId}/handouts/latest/outline`

响应 `data`：

```json
{
  "handoutVersionId": 3001,
  "title": "集合的初见",
  "summary": "按视频时间线组织的讲义目录",
  "items": [
    {
      "outlineKey": "section-1",
      "title": "集合的概念与表示",
      "summary": "从集合定义过渡到集合表示方法",
      "startSec": 0,
      "endSec": 360,
      "sortNo": 1,
      "children": [
        {
          "outlineKey": "outline-1",
          "blockId": 4001,
          "title": "集合的基本概念",
          "summary": "介绍集合、元素和属于关系",
          "startSec": 0,
          "endSec": 180,
          "sortNo": 1,
          "generationStatus": "pending",
          "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
          "topicTags": ["集合"]
        },
        {
          "outlineKey": "outline-2",
          "blockId": 4002,
          "title": "集合的表示方法",
          "summary": "从列举法过渡到描述法",
          "startSec": 180,
          "endSec": 360,
          "sortNo": 2,
          "generationStatus": "pending",
          "sourceSegmentKeys": ["mp4-c3"],
          "topicTags": []
        }
      ]
    }
  ]
}
```

说明：

- 这是视频优先讲义页的首屏读取接口；本轮为破坏性两级 outline API 改动，Flutter 需后续单独适配。
- `items[]` 是大标题，只负责语义分组和展开；大标题没有 `blockId`，不可直接生成讲义块，也不作为点击、跳转、高亮或 QA 的目标。
- `items[*].children[]` 是小标题，也是唯一 leaf item；只有 child 绑定 `blockId`、`generationStatus`、`sourceSegmentKeys` 和 `topicTags`。
- `items[*].children[*].sourceSegmentKeys` 是 API read model 必返字段，用于后续 block 生成和引用校验；前端可忽略展示。
- 点击 child 目录项时，播放器跳转到 child `startSec`；播放时间落在 child `[startSec, endSec)` 时高亮对应 child，最后一个 child 允许命中 `endSec`。
- 同一个大标题下的 children 必须在视频时间线上连续归属，不能与其他大标题穿插；大标题 `startSec/endSec` 等于 children 的最小开始和最大结束。

### `GET /api/v1/courses/{courseId}/handouts/latest/blocks`

响应 `data.items[*]`：

```json
{
  "blockId": 4001,
  "handoutVersionId": 3001,
  "outlineKey": "outline-1",
  "title": "极限与连续",
  "summary": "先抓必考定义和题型",
  "status": "ready",
  "generationStatus": "ready",
  "contentMd": "### 极限与连续",
  "startSec": 120,
  "endSec": 360,
  "sourceSegmentKeys": ["mp4-c1", "mp4-c2"],
  "knowledgePoints": [],
  "generationMetadata": {
    "source": "model",
    "reason": "model_response"
  },
  "citations": [
    {
      "resourceId": 501,
      "refLabel": "PDF 第 2 页",
      "pageNo": 2
    }
  ]
}
```

`citations[]` 中同一结构也允许返回：

- `slideNo`：PPTX slide 引用
- `anchorKey`：DOCX heading / anchor 引用
- `items[*].generationMetadata` 是已生成 block 的必返元数据，`source` 取值为 `model` 或 `fallback`，`reason` 用于区分真实模型生成、模型异常 fallback、本地 fallback 等来源。
- `items[*].citations[]` 是 public citation，只暴露 `resourceId`、`refLabel` 与 locator 字段；`segmentId` / `segmentKey` 不出现在 public response 中。

未生成 block 可返回：

```json
{
  "blockId": 4002,
  "handoutVersionId": 3001,
  "outlineKey": "outline-2",
  "title": "集合的表示方法",
  "summary": "从列举法过渡到描述法",
  "status": "pending",
  "generationStatus": "pending",
  "contentMd": null,
  "startSec": 180,
  "endSec": 360,
  "sourceSegmentKeys": ["mp4-c3"],
  "knowledgePoints": [],
  "citations": []
}
```

### `POST /api/v1/handout-blocks/{blockId}/generate`

响应 `data`：

```json
{
  "taskId": 7102,
  "status": "queued",
  "nextAction": "poll",
  "entity": {
    "type": "handout_block",
    "id": 4002
  }
}
```

说明：

- 这是单个 child 目录项懒生成的接口方向；幂等、任务入队和 DTO 由后端 owner 落地。
- 必须支持 `Idempotency-Key`；相同用户、相同 `blockId`、相同 `Idempotency-Key` 的重复请求不得创建重复 block 或重复任务。
- 当 block 已处于 `generating` 时，重复请求返回当前任务，`entity.type = handout_block`，不得重复入队。
- 当 block 已处于 `ready` 时，重复请求返回当前 block 状态，不重新生成。
- 触发时只生成该 block 的 `contentMd`、block 级 `knowledgePoints` 和引用。

### `GET /api/v1/handout-blocks/{blockId}/status`

响应 `data`：

```json
{
  "blockId": 4002,
  "outlineKey": "outline-2",
  "status": "generating",
  "generationStatus": "generating",
  "startSec": 180,
  "endSec": 360
}
```

### `GET /api/v1/courses/{courseId}/handouts/current-block?currentSec=335`

响应 `data`：

```json
{
  "blockId": 4002,
  "outlineKey": "outline-2",
  "startSec": 180,
  "endSec": 360,
  "status": "pending",
  "generationStatus": "pending",
  "prefetchBlockId": 4003
}
```

说明：

- 播放时间命中规则为 `[startSec, endSec)`；最后一个 block 允许命中 `endSec`。
- 仅当距离当前 block 结束 30 秒以内，且紧邻的下一个 block 仍为 `pending` 时，返回 `prefetchBlockId`。
- 如果紧邻下一个 block 已经是 `generating`、`ready` 或 `failed`，不跳过它去建议更后面的 pending block。

### `GET /api/v1/handout-blocks/{blockId}/jump-target`

响应 `data`：

```json
{
  "blockId": 4002,
  "videoResourceId": 501,
  "startSec": 420,
  "endSec": 600,
  "docResourceId": 502,
  "slideNo": 6
}
```

## 7A. V2 知识图谱 contract 待冻结

V1 不冻结复杂知识图谱 API。V2 按 `docs/v2/phase-plan.md` 做复杂知识图谱时，必须先补充 graph read model contract，至少包含：

- 课程级图谱读取入口，例如 `GET /api/v1/courses/{courseId}/knowledge-graph`。
- 子图或路径读取入口，例如围绕知识点、讲义块、题目或复习任务查询局部图谱。
- 节点字段：稳定 `nodeId`、`nodeType`、`title`、`summary`、`mastery`、`confidence`、`sourceRefs`。
- 边字段：稳定 `edgeId`、`edgeType`、`sourceNodeId`、`targetNodeId`、`weight`、`evidenceRefs`、`reviewStatus`。
- 跳转字段：能回到讲义块、视频时间戳、PDF 页码、PPT 页码或 DOCX anchor。
- 审核字段：AI 生成边和人工确认边必须可区分。

在该 contract 冻结前，图谱生成、图谱查询包装、推荐增强和判卷证据链不得各自扩写不同字段。

## 8. 问答、测验、复习

### `POST /api/v1/qa/messages`

请求：

```json
{
  "courseId": 101,
  "handoutBlockId": 4001,
  "question": "这个定义和题型有什么联系？"
}
```

响应 `data`：

```json
{
  "sessionId": 6001,
  "messageId": 6002,
  "answerMd": "定义控制了题型的判断边界。",
  "answerType": "direct_answer",
  "generationMetadata": {
    "source": "model",
    "reason": "model_response"
  },
  "citations": [
    {
      "resourceId": 501,
      "refLabel": "PDF 第 2 页",
      "pageNo": 2
    }
  ]
}
```

说明：

- `answerType` 取值为 `direct_answer`、`clarification`、`insufficient_evidence`。
- Doubao / vivo QA 接入只影响服务端回答生成策略，不改变前端请求字段、接口路径或 citations 结构。
- `citations` 只能来自服务端当前候选证据反查；`insufficient_evidence` 时固定为空数组。
- `generationMetadata.source` 取值为 `model` 或 `fallback`；本地 fallback、模型异常 fallback 或证据不足拒答必须带明确 `reason`，调用方不得把 fallback 当成真实模型答案。

### `GET /api/v1/qa/sessions/{sessionId}/messages`

响应 `data`：

```json
{
  "items": [
    {
      "sessionId": 6001,
      "messageId": 6002,
      "answerMd": "定义控制了题型的判断边界。",
      "answerType": "direct_answer",
      "generationMetadata": {
        "source": "model",
        "reason": "model_response"
      },
      "citations": [
        {
          "resourceId": 501,
          "refLabel": "PDF 第 2 页",
          "pageNo": 2
        }
      ]
    }
  ]
}
```

### `POST /api/v1/courses/{courseId}/quizzes/generate`

请求可省略；省略时默认 `questionCountLevel = medium`：

```json
{
  "questionCountLevel": "medium"
}
```

说明：

- `questionCountLevel` 可取 `small`、`medium`、`large`。
- `small` 表示后端实时生成 1-3 题；`medium` 表示 3-5 题；`large` 表示 5-10 题。
- 前端只提交档位，不提交精确题数；响应仍以实际 `questionCount` 和 `questions` 为准。
- 测验题目由 DeepSeek 官方 API 实时生成，使用 `deepseek-v4-flash`、thinking enabled、`reasoning_effort=high`，并只允许基于当前课程的 active handout ready blocks 与当前 parse run segments 出题。
- DeepSeek 未配置、超时、坏 JSON、题数不在档位范围、引用未知 block / segment 或 schema 校验失败时，异步任务失败，不回退模板题。

响应结构与其他异步生成接口一致，`entity.type = quiz`。

### `GET /api/v1/quizzes/{quizId}`

响应 `data`：

```json
{
  "quizId": 8001,
  "courseId": 101,
  "status": "ready",
  "questionCount": 3,
  "questions": [
    {
      "questionId": 8101,
      "stemMd": "下列关于极限的说法哪项正确？",
      "options": [
        "A",
        "B",
        "C",
        "D"
      ]
    }
  ]
}
```

### `POST /api/v1/quizzes/{quizId}/attempts`

请求：

```json
{
  "answers": [
    {
      "questionId": 8101,
      "selectedOption": "A"
    }
  ]
}
```

`selectedOption` 的 contract 值是稳定选项 key：`A` / `B` / `C` / `D`。题目响应中的
`options` 数组按该顺序对应四个选项；后端会兼容精确匹配的完整选项文本并归一化为 key，
但前端不应依赖提交完整文本。

V2 主观题判卷说明：

- V1 `POST /api/v1/quizzes/{quizId}/attempts` 只冻结客观题提交，`selectedOption` 不得被复用为主观题答案。
- V2 主观题需要新增或扩展 contract 来表达 `questionType`、`textAnswer`、`rubric`、`gradingRunId`、判卷状态、分项分数、证据引用、置信度和 `needsHumanReview`。
- V2 判卷若走异步，必须继续使用 `async_tasks.id` 作为任务真相源，并明确 attempt 与 grading run 的对应关系。
- 在上述 contract 冻结前，后端、前端和 AI schema 不得各自扩写主观题字段。

响应 `data`：

```json
{
  "attemptId": 8201,
  "score": 100,
  "totalScore": 100,
  "accuracy": 1.0,
  "reviewTaskRunId": 8301,
  "masteryDelta": [
    {
      "knowledgePoint": "极限定义",
      "delta": 0.2,
      "status": "improved"
    }
  ],
  "recommendedReviewAction": {
    "type": "revisit_block",
    "targetBlockId": 4001,
    "reason": "建议先回看易错知识块，再进入下一轮练习。"
  }
}
```

### `GET /api/v1/courses/{courseId}/review-tasks`

响应 `data.items[*]`：

```json
{
  "reviewTaskId": 8401,
  "taskType": "revisit_block",
  "priorityScore": 95,
  "reasonText": "该块是考试高频点",
  "recommendedMinutes": 20,
  "recommendedSegment": {
    "blockId": 4001,
    "startSec": 120,
    "endSec": 240,
    "label": "建议优先回看片段"
  },
  "practiceEntry": {
    "type": "quiz",
    "targetId": 8001,
    "label": "再练 1 题"
  },
  "reviewOrder": 1,
  "intensity": "high"
}
```

### `POST /api/v1/courses/{courseId}/review-tasks/regenerate`

响应结构与其他异步生成接口一致，`entity.type = review_task_run`。

### `GET /api/v1/review-task-runs/{reviewTaskRunId}/status`

响应 `data`：

```json
{
  "reviewTaskRunId": 8301,
  "courseId": 101,
  "status": "ready",
  "generatedCount": 3
}
```

### `POST /api/v1/review-tasks/{reviewTaskId}/complete`

响应 `data`：

```json
{
  "reviewTaskId": 8401,
  "completed": true
}
```

## 9. 最近学习位置

### `GET /api/v1/courses/{courseId}/progress`

响应 `data`：

```json
{
  "courseId": 101,
  "handoutVersionId": 3001,
  "lastHandoutBlockId": 4001,
  "lastVideoResourceId": 501,
  "lastPositionSec": 180,
  "lastDocResourceId": 502,
  "lastPageNo": 3,
  "lastActivityAt": "2026-04-18T15:00:00+00:00"
}
```

### `POST /api/v1/courses/{courseId}/progress`

请求：

```json
{
  "handoutVersionId": 3001,
  "lastHandoutBlockId": 4001,
  "lastVideoResourceId": 501,
  "lastPositionSec": 180,
  "lastDocResourceId": 502,
  "lastPageNo": 3
}
```

说明：

- `courseId` 以 path 为准，请求体不重复传 `courseId`。
- `lastActivityAt` 可由服务端补写。
