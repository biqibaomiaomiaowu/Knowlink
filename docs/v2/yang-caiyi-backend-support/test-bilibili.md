# V2 Bilibili Import Integration Record

测试人员：杨彩艺  
记录日期：2026-05-24  
关联文档：

- [yang-caiyi-bilibili-import-dto.md](./yang-caiyi-bilibili-import-dto.md)
- [yang-caiyi-bilibili-import-integration-template.md](./yang-caiyi-bilibili-import-integration-template.md)
- [../contracts/v2-bilibili-import-contract.md](../contracts/v2-bilibili-import-contract.md)

本文记录 B站导入相关接口的实际联调返回。只记录接口现象，不实现扫码登录、下载、ffmpeg、对象存储上传、取消副作用或任务恢复。

## Summary

| Interface | Status | Conclusion |
|---|---|---|
| `POST /api/v1/bilibili/auth/qr/sessions` | 已测 | 返回字段与 V2 contract 一致 |
| `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}` | 已测 | 可查询 QR session；本次记录到 `expired` |
| `GET /api/v1/bilibili/auth/session` | 待测 | 需要扫码确认后补登录态返回 |
| `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview` | 待测 | 需要有效登录态和 B站样例 |
| `POST /api/v1/courses/{courseId}/resources/imports/bilibili` | 待测 | 需要 preview 成功后创建导入任务 |

## 1. Create QR Session

接口：`POST /api/v1/bilibili/auth/qr/sessions`

结论：无字段出入。`data` 中返回 `sessionId`、`status`、`qrCodeUrl`、`expiresAt`，符合 V2 B站导入 contract。

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "e7109601a9b3cf796e75a4eba47cd249",
    "status": "pending_scan",
    "qrCodeUrl": "https://account.bilibili.com/h5/account-h5/auth/scan-web?navhide=1&callback=close&qrcode_key=e7109601a9b3cf796e75a4eba47cd249&from=",
    "expiresAt": "2026-05-24T15:48:34.663210+00:00"
  },
  "requestId": "req_df2b042f01a14e61b9c05201994b4db9",
  "timestamp": "2026-05-24T15:45:34.679336+00:00"
}
```

字段核对：

| Field | Actual | Contract result |
|---|---|---|
| `sessionId` | `e7109601a9b3cf796e75a4eba47cd249` | match |
| `status` | `pending_scan` | match |
| `qrCodeUrl` | B站扫码 URL | match |
| `expiresAt` | ISO 8601 datetime | match |

## 2. Poll QR Session

接口：`GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`

原始记录中方法写成 `POST`，按 contract 修正为 `GET`。

实际返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": "e7109601a9b3cf796e75a4eba47cd249",
    "status": "expired",
    "qrCodeUrl": "https://account.bilibili.com/h5/account-h5/auth/scan-web?navhide=1&callback=close&qrcode_key=e7109601a9b3cf796e75a4eba47cd249&from=",
    "expiresAt": "2026-05-24T16:08:52.976298+00:00"
  },
  "requestId": "req_a34512f3994841bfb22da2d817d50275",
  "timestamp": "2026-05-24T16:05:52.995290+00:00"
}
```

字段核对：

| Field | Actual | Contract result |
|---|---|---|
| `sessionId` | same as created session | match |
| `status` | `expired` | match, allowed enum |
| `qrCodeUrl` | B站扫码 URL | match |
| `expiresAt` | ISO 8601 datetime | match |

待确认项：

| Item | Note |
|---|---|
| QR 状态流转 | 本次只记录到 `pending_scan -> expired`；还需要扫码成功样例补 `scanned` / `confirmed` |
| 登录态接口 | 需要成功扫码后调用 `GET /api/v1/bilibili/auth/session` |

## 3. Auth Session

接口：`GET /api/v1/bilibili/auth/session`

当前状态：待测。  
补充条件：需要先完成扫码登录确认。

待记录字段：

| Field | Expected |
|---|---|
| `loginStatus` | `active` or error |
| `userNickname` | nullable display name |
| `expiresAt` | nullable datetime |
| cookie 原文 | 不得返回 |

## 4. Preview Import

接口：`POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview`

当前状态：待测。  
补充条件：需要有效 B站登录态、有效 `courseId` 和固定 B站样例。

待记录字段：

| Field | Expected |
|---|---|
| `previewId` | preview snapshot id |
| `sourceType` | `single_video` / `multi_p` / `collection` / `bangumi` |
| `parts[]` | part list |
| `defaultSelectionMode` | selection mode |

## 5. Create Import Task

接口：`POST /api/v1/courses/{courseId}/resources/imports/bilibili`

当前状态：待测。  
补充条件：需要 preview 成功返回 `previewId`。

待记录字段：

| Field | Expected |
|---|---|
| `taskId` | async task id |
| `status` | `queued` or error |
| `nextAction` | `poll` |
| `entity.type` | `bilibili_import_run` |
| `entity.id` | import run id |

## Boundary

| Yang Caiyi can record | Not in Yang Caiyi scope |
|---|---|
| QR response JSON and status sequence | 扫码登录实现 |
| Auth session display fields | cookie / credential handling |
| Preview and import task response | B站下载、ffmpeg、上传 |
| Error code and failure reason | 取消副作用、任务恢复、复杂状态机 |
