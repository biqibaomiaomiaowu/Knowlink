# V2 Course And Resource Integration Record

测试人员：杨彩艺  
记录日期：2026-05-24  
关联文档：

- [yang-caiyi-course-api-dto.md](./yang-caiyi-course-api-dto.md)
- [yang-caiyi-home-dashboard-dto.md](./yang-caiyi-home-dashboard-dto.md)
- [yang-caiyi-resource-api-dto.md](./yang-caiyi-resource-api-dto.md)
- [yang-caiyi-playback-url-integration.md](./yang-caiyi-playback-url-integration.md)

本文整理课程、首页和资源接口的实际联调记录。原始记录中出现的 snake_case DTO 和 `status=active/archived` 属于旧口径；当前 V2/V1 contract 对外响应使用 camelCase，并使用 `lifecycleStatus`、`pipelineStage`、`pipelineStatus` 三个状态字段。

## Summary

| Area | Interface | Status | Conclusion |
|---|---|---|---|
| Course | `POST /api/v1/courses` | 已测 | 返回结构可用；实际课程摘要包含 `activeParseRunId`、`activeHandoutVersionId`，需以后端 contract 为准确认是否长期保留 |
| Course | `GET /api/v1/courses/recent` | 已测 | 返回 `items[]`，字段可用于最近课程列表 |
| Course | `GET /api/v1/courses/current` | 已测 | 返回 `data.course`，字段与课程详情结构一致 |
| Course | `GET /api/v1/courses/{courseId}` | 已测 | 原始记录误写为 `GET /courses/recent`，按返回结构修正为课程详情 |
| Course | `POST /api/v1/courses/{courseId}/switch-current` | 已测 | 返回 `currentCourseId` 和 `course` |
| Home | `GET /api/v1/home/dashboard` | 已测 | 首页聚合字段可用 |
| Resources | `POST /api/v1/courses/{courseId}/resources/upload-init` | 已测 | 返回 MinIO public endpoint 预签名 URL |
| Resources | `POST /api/v1/courses/{courseId}/resources/upload-complete` | 已测 | 返回资源详情字段 |
| Resources | `GET /api/v1/courses/{courseId}/resources` | 已测 | 返回资源列表 |
| Resources | `DELETE /api/v1/courses/{courseId}/resources/{resourceId}` | 已测 | 返回删除确认 |
| Playback | `GET /api/v1/course-resources/{resourceId}/playback` | 待测 | 需要先上传 mp4 视频资源 |

## 1. Course DTO Correction

原始记录中的 DTO：

```text
course_id: string
title: string
status: enum(active, archived)
updated_at: datetime
```

修正为当前 contract 口径：

| Field | Type | Meaning |
|---|---|---|
| `courseId` | integer | 课程 id |
| `title` | string | 课程标题 |
| `entryType` | string | `manual_import` or `recommendation` |
| `catalogId` | string or null | 推荐来源 |
| `goalText` | string or null | 学习目标 |
| `examAt` | datetime or null | 考试或截止时间 |
| `preferredStyle` | string or null | 偏好 |
| `lifecycleStatus` | string | 课程生命周期状态 |
| `pipelineStage` | string | 当前流程阶段 |
| `pipelineStatus` | string | 当前流程状态 |
| `updatedAt` | datetime | 更新时间 |

实际返回中还出现：

| Field | Actual | Handling |
|---|---|---|
| `activeParseRunId` | null / integer | 记录为实际返回字段，建议后续 contract 明确 |
| `activeHandoutVersionId` | null / integer | 记录为实际返回字段，建议后续 contract 明确 |

## 2. Create Course

接口：`POST /api/v1/courses`

请求：

```json
{
  "title": "高数期末冲刺课",
  "entryType": "recommendation",
  "goalText": "高等数学期末复习",
  "examAt": "2026-06-20T09:00:00+08:00",
  "preferredStyle": "exam"
}
```

结论：

| Check | Result |
|---|---|
| `courseId` | returned |
| `title` | returned |
| `lifecycleStatus` | returned as `draft` in later query records |
| `pipelineStage` | returned as `idle` in later query records |
| `pipelineStatus` | returned as `idle` in later query records |
| `updatedAt` | returned |

说明：原始记录中的“`status` 返回 running”不应写入课程 DTO。课程状态应拆成 `lifecycleStatus`、`pipelineStage`、`pipelineStatus`；`running` 属于 pipeline / async task 语义，不是课程 `status` 字段。

## 3. Recent Courses

接口：`GET /api/v1/courses/recent`

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "courseId": 5,
        "title": "高数期末冲刺课",
        "entryType": "recommendation",
        "catalogId": null,
        "goalText": "高等数学期末复习",
        "examAt": "2026-06-20T01:00:00+00:00",
        "preferredStyle": "exam",
        "lifecycleStatus": "draft",
        "pipelineStage": "idle",
        "pipelineStatus": "idle",
        "activeParseRunId": null,
        "activeHandoutVersionId": null,
        "updatedAt": "2026-05-24T12:40:21.315580+00:00"
      }
    ]
  },
  "requestId": "req_d33811d0f1ac490c92271c2f0392e43a",
  "timestamp": "2026-05-24T13:03:49.029724+00:00"
}
```

结论：列表结构为 `data.items[]`，可用于最近课程展示。实际测试中返回多条课程，本文只保留第一条作为示例。

## 4. Current Course

接口：`GET /api/v1/courses/current`

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "course": {
      "courseId": 5,
      "title": "高数期末冲刺课",
      "entryType": "recommendation",
      "catalogId": null,
      "goalText": "高等数学期末复习",
      "examAt": "2026-06-20T01:00:00+00:00",
      "preferredStyle": "exam",
      "lifecycleStatus": "draft",
      "pipelineStage": "idle",
      "pipelineStatus": "idle",
      "activeParseRunId": null,
      "activeHandoutVersionId": null,
      "updatedAt": "2026-05-24T12:40:21.315580+00:00"
    }
  },
  "requestId": "req_4b35f5a6ba634ded8147165414b0e9b2",
  "timestamp": "2026-05-24T13:34:50.721380+00:00"
}
```

结论：当前课程返回 `data.course`，字段与课程详情一致。

## 5. Course Detail

接口：`GET /api/v1/courses/{courseId}`

原始记录标题误写为 `GET /courses/recent`，但实际返回是 `data.course`，应归入课程详情接口。

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "course": {
      "courseId": 5,
      "title": "高数期末冲刺课",
      "entryType": "recommendation",
      "catalogId": null,
      "goalText": "高等数学期末复习",
      "examAt": "2026-06-20T01:00:00+00:00",
      "preferredStyle": "exam",
      "lifecycleStatus": "draft",
      "pipelineStage": "idle",
      "pipelineStatus": "idle",
      "activeParseRunId": null,
      "activeHandoutVersionId": null,
      "updatedAt": "2026-05-24T12:40:21.315580+00:00"
    }
  },
  "requestId": "req_cb782609ad5d4470991e214aa4ab7d6c",
  "timestamp": "2026-05-24T13:36:23.220851+00:00"
}
```

## 6. Switch Current Course

接口：`POST /api/v1/courses/{courseId}/switch-current`

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "currentCourseId": 5,
    "course": {
      "courseId": 5,
      "title": "高数期末冲刺课",
      "entryType": "recommendation",
      "catalogId": null,
      "goalText": "高等数学期末复习",
      "examAt": "2026-06-20T01:00:00+00:00",
      "preferredStyle": "exam",
      "lifecycleStatus": "draft",
      "pipelineStage": "idle",
      "pipelineStatus": "idle",
      "activeParseRunId": null,
      "activeHandoutVersionId": null,
      "updatedAt": "2026-05-24T13:38:42.228515+00:00"
    }
  },
  "requestId": "req_b817393537514b459ea72a170f56d776",
  "timestamp": "2026-05-24T13:38:42.233576+00:00"
}
```

结论：接口可用于单用户当前课程切换。

## 7. Home Dashboard

接口：`GET /api/v1/home/dashboard`

实际返回摘要：

| Field | Actual |
|---|---|
| `recentCourses` | 3 items |
| `topReviewTasks` | `[]` |
| `recommendationEntryEnabled` | `true` |
| `dailyRecommendedKnowledgePoints` | `[]` |
| `learningStats.streakDays` | `0` |
| `learningStats.completedCourses` | `0` |
| `learningStats.reviewTasksCompleted` | `0` |
| `learningStats.totalLearningMinutes` | `0` |

结论：首页聚合字段与文档一致；空数组和 0 值需要前端兼容。

## 8. Upload Init

接口：`POST /api/v1/courses/{courseId}/resources/upload-init`

原始记录中 `{coursesId}` 修正为 `{courseId}`。

实际返回摘要：

| Field | Actual |
|---|---|
| `uploadUrl` | `http://127.0.0.1:9000/...` |
| `objectKey` | `raw/1/5/temp/pdf/knowlink-demo-handout.pdf` |
| `headers.x-amz-meta-course-id` | `5` |
| `headers.x-amz-meta-checksum` | `sha256:demo` |
| `expiresAt` | `2026-05-24T15:01:14.612073+00:00` |

结论：`uploadUrl` 使用本地可访问的 `127.0.0.1:9000`，符合 MinIO public endpoint 联调要求。

## 9. Upload Complete

接口：`POST /api/v1/courses/{courseId}/resources/upload-complete`

实际返回摘要：

| Field | Actual |
|---|---|
| `resourceId` | `1` |
| `courseId` | `5` |
| `resourceType` | `pdf` |
| `sourceType` | `upload` |
| `objectKey` | `raw/1/5/temp/pdf/knowlink-demo-handout.pdf` |
| `ingestStatus` | `ready` |
| `validationStatus` | `passed` |
| `processingStatus` | `pending` |

结论：上传完成后资源成功登记，解析仍需通过 `POST /api/v1/courses/{courseId}/parse/start` 触发。

## 10. List Resources

接口：`GET /api/v1/courses/{courseId}/resources`

实际返回摘要：

| Field | Actual |
|---|---|
| `items.length` | `1` |
| `items[0].resourceId` | `1` |
| `items[0].resourceType` | `pdf` |
| `items[0].sourceType` | `upload` |
| `items[0].processingStatus` | `pending` |

结论：资源列表可展示上传资源；本次只有 PDF。

## 11. Delete Resource

接口：`DELETE /api/v1/courses/{courseId}/resources/{resourceId}`

输入：

| Field | Value |
|---|---|
| `courseId` | `5` |
| `resourceId` | `1` |

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "deleted": true,
    "resourceId": 1
  },
  "requestId": "req_c1fb034b1f40477fafd62aa93563a016",
  "timestamp": "2026-05-24T15:14:23.721396+00:00"
}
```

结论：删除接口返回符合 contract。若资源已有下游依赖，需另测 `resource.has_dependents`。

## 12. Playback

接口：`GET /api/v1/course-resources/{resourceId}/playback`

当前状态：待测。  
原因：本次只上传了 PDF，没有上传 mp4 视频资源。播放地址需要 mp4 资源后再测。

后续记录位置：[yang-caiyi-playback-url-integration.md](./yang-caiyi-playback-url-integration.md)。

## Pending Items

| Item | Owner boundary | Note |
|---|---|---|
| `activeParseRunId` / `activeHandoutVersionId` 是否进入正式课程 DTO | 需后端 contract 确认 | 实际接口已返回，文档先作为差异记录 |
| mp4 playback 测试 | 杨彩艺可记录，需先有 mp4 资源 | 当前未测 |
| 删除有依赖资源的错误场景 | 杨彩艺可记录 | 当前只测了成功删除 |
