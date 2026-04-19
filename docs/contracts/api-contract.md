# KnowLink API Contract

本文件冻结 MVP 阶段前后端共享的请求字段、响应字段、异步返回结构和 demo 鉴权策略。曹乐 owner 的 Week 1 冻结项与固定联调资料集基线见 [week1-cao-le-freeze.md](./week1-cao-le-freeze.md) 和 [../demo-assets-baseline.md](../demo-assets-baseline.md)。若与其他文档冲突，以本文件为准。

文档冲突优先级矩阵见 [ARCHITECTURE.md](../../ARCHITECTURE.md) 第 23 节。

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
- 以下写接口必须支持 `Idempotency-Key`：
  - `POST /api/v1/courses`
  - `POST /api/v1/recommendations/{catalogId}/confirm`
  - `POST /api/v1/courses/{courseId}/resources/upload-complete`
  - `POST /api/v1/courses/{courseId}/parse/start`
  - `POST /api/v1/courses/{courseId}/handouts/generate`
  - `POST /api/v1/courses/{courseId}/quizzes/generate`
  - `POST /api/v1/courses/{courseId}/review-tasks/regenerate`
- 带路径参数的课程接口一律以 path 中的 `courseId` 为准；请求体不再重复传同义 `courseId`，`POST /api/v1/qa/messages` 是唯一例外。

### 1.1 Week 1 冻结入口

- 曹乐负责的表语义、状态枚举、推荐理由文案和固定联调资料集基线，以 [week1-cao-le-freeze.md](./week1-cao-le-freeze.md) 为验收入口。
- 固定联调资料集只版本化清单与规范，不在仓库中提交 `mp4/pdf/pptx/docx` 二进制样例。
- demo 鉴权变量名固定为 `.env` / `.env.example` 中的 `KNOWLINK_DEMO_TOKEN`。

### 1.2 核心状态枚举

- `lifecycleStatus`: `draft` `resource_ready` `inquiry_ready` `learning_ready` `archived` `failed`
- `pipelineStage`: `idle` `upload` `parse` `inquiry` `handout`
- `pipelineStatus`: `idle` `queued` `running` `partial_success` `succeeded` `failed`
- `async_tasks.status`: `queued` `running` `succeeded` `failed` `retrying` `canceled` `skipped`

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
- `reasons[]` 在 Week 1 只允许使用以下冻结文案：
  - `难度与当前基础匹配`
  - `难度可控，适合作为过渡课程`
  - `时长可在当前预算内完成`
  - `需要拆分学习节奏，但仍可安排`
  - `目标关键词与课程主题高度一致`
  - `讲义风格与当前偏好一致`

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
  "uploadUrl": "https://minio.local/upload/demo",
  "objectKey": "raw/1/101/temp/chapter-1.pdf",
  "headers": {
    "x-amz-meta-course-id": "101"
  },
  "expiresAt": "2026-04-18T15:15:00+00:00"
}
```

### `POST /api/v1/courses/{courseId}/resources/upload-complete`

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

### `DELETE /api/v1/courses/{courseId}/resources/{resourceId}`

响应 `data`：

```json
{
  "deleted": true,
  "resourceId": 501
}
```

### B 站导入预留接口

以下接口参考 `bilidown` 的“单视频 + 登录态 + 任务状态”分层方式冻结 contract，但当前服务统一返回 `501 Not Implemented`，不创建真实任务、不触发 MinIO 写入，也不接通扫码登录。

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

- stub 阶段会保留上述 `requestBody` 结构，但暂不收紧为必填校验；鉴权通过后统一返回 `501`。

未来接通后的响应 `data`：

```json
{
  "taskId": 7201,
  "status": "queued",
  "nextAction": "poll",
  "entity": {
    "type": "bilibili_import_run",
    "id": 9101
  }
}
```

约束：

- 第一版只冻结单个公开视频链接，不覆盖番剧、合集、收藏夹和批量导入。
- 支持范围只包含标准视频页链接、`BV` 链接和 `b23.tv` 短链。
- 未来接通后，该异步导入实体类型固定为 `bilibili_import_run`。

### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`

未来接通后的响应 `data`：

```json
{
  "items": [
    {
      "importRunId": 9101,
      "courseId": 101,
      "status": "queued",
      "videoUrl": "https://www.bilibili.com/video/BV1LLDCYJEU3/",
      "taskId": 7201,
      "resourceId": null
    }
  ]
}
```

### `GET /api/v1/bilibili-import-runs/{importRunId}/status`

未来接通后的响应 `data`：

```json
{
  "importRunId": 9101,
  "courseId": 101,
  "status": "queued",
  "videoUrl": "https://www.bilibili.com/video/BV1LLDCYJEU3/",
  "taskId": 7201,
  "resourceId": null,
  "nextAction": "poll",
  "errorCode": null
}
```

### `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

未来接通后的响应 `data`：

```json
{
  "taskId": 7201,
  "status": "canceled",
  "nextAction": "none",
  "entity": {
    "type": "bilibili_import_run",
    "id": 9101
  }
}
```

### `POST /api/v1/bilibili/auth/qr/sessions`

未来接通后的响应 `data`：

```json
{
  "sessionId": "bili_qr_session_001",
  "status": "pending_scan",
  "qrCodeUrl": "https://i0.hdslb.com/bfs/static/jinkela/long/qr-demo.png",
  "expiresAt": "2026-04-18T15:15:00+00:00"
}
```

### `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`

未来接通后的响应 `data`：

```json
{
  "sessionId": "bili_qr_session_001",
  "status": "pending_scan",
  "qrCodeUrl": "https://i0.hdslb.com/bfs/static/jinkela/long/qr-demo.png",
  "expiresAt": "2026-04-18T15:15:00+00:00"
}
```

### `GET /api/v1/bilibili/auth/session`

未来接通后的响应 `data`：

```json
{
  "loginStatus": "active",
  "userNickname": "KnowLink Demo",
  "expiresAt": "2026-04-18T17:15:00+00:00"
}
```

### `DELETE /api/v1/bilibili/auth/session`

未来接通后的响应 `data`：

```json
{
  "deleted": true
}
```

当前未实现阶段统一返回：

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
  "nextAction": "enter_inquiry",
  "sourceOverview": {
    "videoReady": true,
    "docTypes": ["pdf", "pptx", "docx"],
    "organizedSourceCount": 3
  },
  "knowledgeMap": {
    "status": "ready",
    "knowledgePointCount": 5,
    "segmentCount": 12
  },
  "highlightSummary": {
    "status": "ready",
    "items": [
      "重点公式与高频题型已抽取",
      "已生成下一步 AI 个性化问询入口"
    ]
  }
}
```

### `GET /api/v1/courses/{courseId}/parse/summary`

响应 `data`：

```json
{
  "courseId": 101,
  "activeParseRunId": 9001,
  "segmentCount": 12,
  "knowledgePointCount": 5
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
      "options": []
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
  "status": "ready",
  "totalBlocks": 3,
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
  "status": "ready"
}
```

### `GET /api/v1/courses/{courseId}/handouts/latest/blocks`

响应 `data.items[*]`：

```json
{
  "blockId": 4001,
  "title": "极限与连续",
  "summary": "先抓必考定义和题型",
  "contentMd": "### 极限与连续",
  "startSec": 120,
  "endSec": 360,
  "pageFrom": 2,
  "pageTo": 5,
  "citations": [
    {
      "resourceId": 501,
      "refLabel": "PDF 第 2 页",
      "pageNo": 2
    }
  ]
}
```

同一结构也允许返回：

- `slideNo`：PPTX slide 引用
- `anchorKey`：DOCX heading / anchor 引用

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
  "citations": [
    {
      "resourceId": 501,
      "refLabel": "PDF 第 2 页",
      "pageNo": 2
    }
  ]
}
```

### `GET /api/v1/qa/sessions/{sessionId}/messages`

响应 `data`：

```json
{
  "items": [
    {
      "sessionId": 6001,
      "messageId": 6002,
      "answerMd": "定义控制了题型的判断边界。",
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
