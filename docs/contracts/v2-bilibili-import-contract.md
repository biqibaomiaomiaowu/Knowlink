# KnowLink V2 B站导入 Contract

日期：2026-05-18

## 1. 适用范围

本文冻结 KnowLink V2 phase 1 B站真实导入的 API、DTO、状态机、错误码和验收口径，供后端实现、前端联调和辅助后端文档整理使用。V1 `501 bilibili.not_implemented` 是历史预留口径，只说明第一版 stub 状态，不再约束 V2 真实导入实现。

本文覆盖单用户下的单视频、多 P、合集和番剧导入；不覆盖收藏夹、热门列表、大规模批量下载、付费/会员/DRM/地区限制内容绕过。

真相源：KnowLink V2 B站导入以 `bilibili_import_run` 和 `async_tasks` 为任务真相源，不引入第三方下载器的数据库或任务模型。

## 2. 通用约定

- 所有接口仍使用 `/api/v1` 前缀。
- 除健康检查外，接口继续要求 `Authorization: Bearer <token>`。
- 服务端保存 B站 cookie 必要字段，不向前端返回 cookie 原文。
- `sourceUrl` 支持 B站单视频、多 P、合集和番剧入口链接。
- `qualityPreference` 默认 `android_safe`，优先选择 H.264/AVC 视频和 AAC 音频，便于 Android 播放和后续解析。
- 所有创建导入任务的写接口必须支持 `Idempotency-Key`。

## 3. API

### `POST /api/v1/bilibili/auth/qr/sessions`

创建 B站扫码登录会话。

请求：空 body。

响应 `data`：

```json
{
  "sessionId": "bili_qr_20260518_001",
  "qrCodeUrl": "https://passport.bilibili.com/qr/demo",
  "loginStatus": "pending",
  "expiresAt": "2026-05-18T12:05:00+08:00"
}
```

说明：

- `loginStatus` 可取 `pending`、`confirmed`、`expired`、`failed`。
- 二维码失效后前端重新创建会话，不复用旧 `sessionId`。

### `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`

查询扫码登录会话状态。

响应 `data`：

```json
{
  "sessionId": "bili_qr_20260518_001",
  "loginStatus": "confirmed",
  "expiresAt": "2026-05-18T12:05:00+08:00",
  "nextAction": "preview"
}
```

### `GET /api/v1/bilibili/auth/session`

查询服务端当前 B站登录态。

响应 `data`：

```json
{
  "authenticated": true,
  "expiresAt": "2026-06-18T12:00:00+08:00",
  "displayName": "bili-user",
  "nextAction": "preview"
}
```

失败语义：

- 未登录返回 `401 bilibili.auth_required`。
- cookie 已失效返回 `401 bilibili.auth_expired`。

### `DELETE /api/v1/bilibili/auth/session`

清除服务端保存的 B站登录态。

响应 `data`：

```json
{
  "deleted": true
}
```

### `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview`

识别 B站链接并返回可选择的导入项，不创建课程资源。

请求：

```json
{
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "qualityPreference": "android_safe"
}
```

响应 `data`：

```json
{
  "courseId": 101,
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "sourceType": "bilibili",
  "preview": {
    "title": "线性代数复习",
    "coverUrl": "https://i0.hdslb.com/demo.jpg",
    "kind": "video",
    "parts": [
      {
        "partId": "cid-1001",
        "title": "P1 行列式",
        "durationSec": 1800,
        "defaultSelected": true
      }
    ]
  },
  "nextAction": "import"
}
```

失败语义：

- URL 不属于支持范围返回 `422 bilibili.unsupported_url`。
- 未登录或登录态失效返回 `401 bilibili.auth_required` / `401 bilibili.auth_expired`。
- 元数据不可访问返回 `403 bilibili.access_denied` 或 `502 bilibili.metadata_failed`。

### `POST /api/v1/courses/{courseId}/resources/imports/bilibili`

创建 B站导入任务并写入 `async_tasks`。

请求：

```json
{
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "selectionMode": "selected_parts",
  "selectedPartIds": ["cid-1001"],
  "qualityPreference": "android_safe"
}
```

字段：

- `selectionMode` 可取 `current_part`、`all_parts`、`selected_parts`。
- `selectedPartIds` 仅在 `selected_parts` 时必填。
- `courseId` 以 path 为准，请求体不重复传同义字段。

响应 `data`：

```json
{
  "importRunId": 9001,
  "courseId": 101,
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "sourceType": "bilibili",
  "status": "pending",
  "progressPct": 0,
  "stage": "queued",
  "taskId": 7001,
  "resourceIds": [],
  "preview": null,
  "errorCode": null,
  "failureReason": null,
  "recoverable": false,
  "nextAction": "poll_status"
}
```

失败语义：

- 选择项不合法返回 `422 bilibili.selection_invalid`。
- 任务创建或派发失败返回 `503 async_task.enqueue_failed`，响应仍应包含可追踪的任务或失败原因。

### `GET /api/v1/courses/{courseId}/resources/imports/bilibili`

列出当前课程的 B站导入记录，用于前端恢复页面和辅助后端联调记录。

响应 `data`：

```json
{
  "items": [
    {
      "importRunId": 9001,
      "courseId": 101,
      "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
      "status": "downloading",
      "progressPct": 42,
      "taskId": 7001,
      "resourceIds": [],
      "errorCode": null,
      "failureReason": null,
      "recoverable": false,
      "nextAction": "poll_status"
    }
  ]
}
```

### `GET /api/v1/bilibili-import-runs/{importRunId}/status`

查询导入任务状态。

响应 `data`：

```json
{
  "importRunId": 9001,
  "courseId": 101,
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "sourceType": "bilibili",
  "status": "merging",
  "progressPct": 70,
  "stage": "ffmpeg",
  "taskId": 7001,
  "resourceIds": [],
  "preview": {
    "title": "线性代数复习",
    "parts": [
      {
        "partId": "cid-1001",
        "title": "P1 行列式",
        "durationSec": 1800
      }
    ]
  },
  "errorCode": null,
  "failureReason": null,
  "recoverable": false,
  "nextAction": "poll_status"
}
```

失败语义：

- run 不存在或不属于当前用户返回 `404 bilibili.run_not_found`。

### `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

请求取消导入任务。取消是显式状态变更，必须尽力停止下载、ffmpeg 和上传副作用。

请求：空 body。

响应 `data`：

```json
{
  "importRunId": 9001,
  "status": "canceled",
  "taskId": 7001,
  "resourceIds": [],
  "errorCode": null,
  "failureReason": null,
  "recoverable": false,
  "nextAction": "none"
}
```

失败语义：

- run 不存在返回 `404 bilibili.run_not_found`。
- 终态 `imported` 不可取消，返回当前结果或 `409 bilibili.cancel_failed`。
- 停止下载、ffmpeg 或清理临时文件失败时，返回 `409 bilibili.cancel_failed`，并在 `failureReason` 中说明可人工处理的残留。

## 4. DTO 字段冻结

导入 run 响应必须至少包含：

- `importRunId`
- `courseId`
- `sourceUrl`
- `sourceType`
- `status`
- `progressPct`
- `stage`
- `taskId`
- `resourceIds`
- `preview`
- `errorCode`
- `failureReason`
- `recoverable`
- `nextAction`

Preview item 必须至少包含：

- `partId`
- `title`
- `durationSec`
- `defaultSelected`

## 5. 状态机

`bilibili_import_run.status` 只允许以下值：

- `pending`
- `fetching_metadata`
- `waiting_download`
- `downloading`
- `merging`
- `uploading`
- `imported`
- `failed`
- `recoverable`
- `canceled`

终态：

- `imported`
- `failed`
- `recoverable`
- `canceled`

状态含义：

| 状态 | 含义 | 下一步 |
|---|---|---|
| `pending` | run 已创建，等待 worker 或调度器处理 | `fetching_metadata` 或 `waiting_download` |
| `fetching_metadata` | 正在解析 URL、元数据、分 P、合集或番剧条目 | `waiting_download`、`failed`、`recoverable`、`canceled` |
| `waiting_download` | 元数据已确认，等待下载槽位 | `downloading`、`canceled` |
| `downloading` | 正在下载音视频流 | `merging`、`failed`、`recoverable`、`canceled` |
| `merging` | 正在用 ffmpeg stream copy 合并 | `uploading`、`failed`、`recoverable`、`canceled` |
| `uploading` | 正在上传对象存储并准备课程资源入库 | `imported`、`failed`、`recoverable`、`canceled` |
| `imported` | 已创建课程资源并可进入学习链路 | 终态 |
| `failed` | 不可恢复失败 | 终态 |
| `recoverable` | 可恢复失败，前端可提示重试或重新登录 | 终态 |
| `canceled` | 用户或系统取消，副作用已尽力清理 | 终态 |

## 6. `async_tasks` 映射

| `bilibili_import_run.status` | `async_tasks.status` | 说明 |
|---|---|---|
| `pending`、`waiting_download` | `queued` | 等待元数据、排队或等待下载槽位 |
| `fetching_metadata`、`downloading`、`merging`、`uploading` | `running` | worker 正在执行 |
| `imported` | `succeeded` | 课程资源已创建 |
| `failed` | `failed` | 不可恢复失败 |
| `recoverable` | `failed` | 可恢复失败仍在任务层标记失败，run 响应承载恢复语义 |
| `canceled` | `canceled` | 已取消 |

`async_tasks.entity.type` 固定为 `bilibili_import_run`，`async_tasks.entity.id` 固定为 `importRunId`。

## 7. 错误码

V2 B站导入错误码冻结在 [error-codes.md](./error-codes.md) 的 Bilibili 段落。接口实现只能返回该段落中的 B站错误码，新增错误码必须先更新本文和错误码 contract。

会员、付费、DRM、地区限制或账号无权限统一归入 `bilibili.access_denied`，`failureReason` 说明具体原因，不做绕过。

## 8. 取消与清理

- `pending`、`waiting_download`：直接写入 `canceled`，不产生课程资源。
- `fetching_metadata`：写入 `canceled`，不保留预览副作用。
- `downloading`：停止 HTTP 请求，删除临时视频和音频片段。
- `merging`：终止 ffmpeg 子进程，删除临时输出。
- `uploading`：尽力中断上传；若对象已存在但课程资源未入库，记录清理提示并避免前端展示半成品。
- `imported`：不可取消，不删除已创建课程资源。

临时目录格式：

```text
runtime/bilibili/{import_run_id}/
```

对象 key 格式：

```text
raw/1/{course_id}/bilibili/{import_run_id}/{safe_title}.mp4
```

## 9. 验收口径

- 固定样例至少覆盖一个可访问的单视频或多 P 链路。
- 合集和番剧以至少一个可访问样例为准；会员、付费、地区限制或不可观看内容只要求返回明确失败原因。
- 导入后必须能在课程资源列表看到 `sourceType=bilibili` 的资源。
- 状态接口必须能展示下载、合并、上传、失败、可恢复失败和取消语义。
- Android 前端只读取 `qrCodeUrl`、`loginStatus`、`preview.parts`、`status`、`progressPct`、`stage`、`failureReason`、`nextAction` 等展示字段，不读取 cookie。
