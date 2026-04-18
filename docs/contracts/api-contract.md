# KnowLink API Contract

本文件冻结 MVP 阶段前后端共享的请求字段、响应字段、异步返回结构和 demo 鉴权策略。若与其他文档冲突，以本文件为准。

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
- 以下写接口必须支持 `Idempotency-Key`：
  - `POST /api/v1/courses`
  - `POST /api/v1/recommendations/{catalogId}/confirm`
  - `POST /api/v1/courses/{courseId}/resources/upload-complete`
  - `POST /api/v1/courses/{courseId}/parse/start`
  - `POST /api/v1/courses/{courseId}/handouts/generate`
  - `POST /api/v1/courses/{courseId}/quizzes/generate`
  - `POST /api/v1/courses/{courseId}/review-tasks/regenerate`

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
        "匹配期末复习目标",
        "时长可在当前预算内完成"
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
  "title": "线性代数强化课",
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

请求体与 `GET` 返回结构一致，但 `lastActivityAt` 可由服务端补写。
