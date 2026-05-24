# 杨彩艺 V2 B站导入 DTO 文档

来源：

- `docs/contracts/v2-bilibili-import-contract.md`
- `docs/contracts/error-codes.md`
- `docs/v2/phase1-cao-le-handoff.md`
- `docs/contracts/api-contract.md`
- `docs/contracts/week1-cao-le-freeze.md`

用途：把原来的 B站 V1 stub 预留接口清单升级为 V2 B站导入 DTO 文档，供杨彩艺整理接口字段、任务列表样例、状态查询样例、错误码说明和联调记录。本文只整理曹乐已冻结的 contract，不实现扫码、凭据、下载、ffmpeg、对象存储上传、取消副作用、任务恢复或复杂状态机。

## 口径变化

| 项目 | 当前口径 |
|---|---|
| V1 `501` stub | 只作为历史预留口径保留 |
| V2 contract | 以 `docs/contracts/v2-bilibili-import-contract.md` 为准 |
| 错误码 | 以 `docs/contracts/error-codes.md` 的 Bilibili 段落为准 |
| 状态机 | 以 V2 B站 contract 第 5 节为准 |
| `async_tasks` 映射 | 以 V2 B站 contract 第 7 节为准 |
| 杨彩艺职责 | 整理字段说明、状态样例、任务列表样例、错误码说明、联调记录 |
| 杨彩艺不负责 | 凭据、下载、ffmpeg、上传、取消副作用、任务恢复、访问边界策略 |

## V2 接口清单

| 模块 | 方法 | 路径 | 用途 | 杨彩艺可做事项 |
|---|---|---|---|---|
| 扫码登录 | `POST` | `/api/v1/bilibili/auth/qr/sessions` | 创建 B站扫码登录会话 | 整理 QR session DTO 和状态记录 |
| 扫码登录 | `GET` | `/api/v1/bilibili/auth/qr/sessions/{sessionId}` | 查询扫码登录会话状态 | 整理轮询记录 |
| 登录态 | `GET` | `/api/v1/bilibili/auth/session` | 查询服务端当前 B站登录态 | 整理登录态展示字段和错误码 |
| 登录态 | `DELETE` | `/api/v1/bilibili/auth/session` | 清除服务端保存的 B站登录态 | 整理退出登录响应 |
| 预览 | `POST` | `/api/v1/courses/{courseId}/resources/imports/bilibili/preview` | 识别 B站链接并返回可选择导入项 | 整理 preview DTO、parts 字段和失败样例 |
| 创建导入任务 | `POST` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | 创建 B站导入任务并写入 `async_tasks` | 整理创建请求、异步响应和幂等记录 |
| 任务列表 | `GET` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | 列出当前课程 B站导入记录 | 整理任务列表字段和恢复页面样例 |
| 状态查询 | `GET` | `/api/v1/bilibili-import-runs/{importRunId}/status` | 查询导入任务状态 | 整理状态查询样例 |
| 取消入口 | `POST` | `/api/v1/bilibili-import-runs/{importRunId}/cancel` | 请求取消导入任务 | 整理取消响应；不处理取消副作用 |

## QR Session DTO

### 创建扫码会话

接口：`POST /api/v1/bilibili/auth/qr/sessions`

请求：空 body。

响应 `data`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `sessionId` | string | `bili_qr_session_001` | 扫码会话 ID |
| `status` | string | `pending_scan` | 扫码会话状态 |
| `qrCodeUrl` | string | `https://passport.bilibili.com/qrcode-demo` | 二维码 URL |
| `expiresAt` | string, datetime | `2026-05-18T12:15:00+00:00` | 二维码过期时间 |

`status` 取值：

| 取值 | 说明 |
|---|---|
| `pending_scan` | 等待扫码 |
| `scanned` | 已扫码 |
| `confirmed` | 已确认登录 |
| `expired` | 二维码已过期 |
| `failed` | 扫码会话失败 |

说明：二维码失效后前端重新创建会话，不复用旧 `sessionId`。

### 查询扫码会话

接口：`GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`

响应 `data` 与创建扫码会话一致。

## 登录态 DTO

### 查询登录态

接口：`GET /api/v1/bilibili/auth/session`

响应 `data`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `loginStatus` | string | `active` | 服务端登录态 |
| `userNickname` | string | `KnowLink Demo` | B站用户昵称 |
| `expiresAt` | string, datetime | `2026-05-18T14:00:00+00:00` | 登录态过期时间 |

安全边界：

| 禁止返回 |
|---|
| `SESSDATA` |
| `bili_jct` |
| `DedeUserID` |
| 完整 cookie |

失败语义：

| 场景 | HTTP / 错误码 |
|---|---|
| 未登录 | `401 bilibili.auth_required` |
| cookie 已失效 | `401 bilibili.auth_expired` |

### 清除登录态

接口：`DELETE /api/v1/bilibili/auth/session`

响应 `data`：

| 字段 | 类型 | 示例 |
|---|---|---|
| `deleted` | boolean | `true` |

## Preview DTO

接口：`POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview`

请求：

| 字段 | 位置 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|---|
| `courseId` | path | number | 是 | `101` | 课程 ID |
| `sourceUrl` | body | string | 是 | `https://www.bilibili.com/video/BV1xx411c7mD?p=2` | B站单视频、多 P、合集或番剧入口链接 |

响应 `data`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `previewId` | string | `bili_preview_9101` | 预览快照 ID，创建导入任务时复用 |
| `sourceUrl` | string | `https://www.bilibili.com/video/BV1xx411c7mD?p=2` | 原始链接 |
| `sourceType` | string | `multi_p` | 来源类型 |
| `title` | string | `课程样例` | 标题 |
| `coverUrl` | string/null | `https://i0.hdslb.com/bfs/archive/demo.jpg` | 封面 URL |
| `totalParts` | number | `2` | 可导入条目总数 |
| `parts` | array | 见下表 | 分 P、合集或番剧条目 |
| `defaultSelectionMode` | string | `current_part` | 默认选择模式 |

`parts[]`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `partId` | string | `cid-1001` | 稳定选择 ID |
| `title` | string | `P1 导论` | 条目标题 |
| `durationSec` | number | `600` | 时长，单位秒 |
| `cid` | number | `1001` | B站 cid |
| `pageNo` | number | `1` | 分 P 或条目序号 |
| `selectedByDefault` | boolean | `true` | 是否默认选中 |

## 创建导入任务 DTO

接口：`POST /api/v1/courses/{courseId}/resources/imports/bilibili`

请求：

| 字段 | 位置 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|---|
| `courseId` | path | number | 是 | `101` | 以 path 为准，请求体不重复传 |
| `previewId` | body | string | 是 | `bili_preview_9101` | 复用预览快照 |
| `sourceUrl` | body | string | 是 | `https://www.bilibili.com/video/BV1xx411c7mD?p=2` | 用于幂等回放、快照校验和审计 |
| `selectionMode` | body | string | 是 | `selected_parts` | 选择模式 |
| `selectedPartIds` | body | array[string] | 条件必填 | `["cid-1001"]` | 仅 `selected_parts` 时必填 |
| `qualityPreference` | body | string | 是 | `android_safe` | phase 1 唯一允许值 |

响应 `data`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `taskId` | number | `7201` | 异步任务 ID |
| `status` | string | `queued` | 异步任务状态 |
| `nextAction` | string | `poll` | 下一步动作 |
| `entity.type` | string | `bilibili_import_run` | 固定实体类型 |
| `entity.id` | number | `9101` | 导入 run ID |

幂等说明：

| 场景 | 口径 |
|---|---|
| 相同 scope + key + 相同请求体 | 不创建重复 run，不重复入队；返回第一次创建的 async-task 响应 |
| 相同 scope + key + 不同请求体 | 返回 `409 idempotency.body_mismatch` |
| run 已创建但派发失败 | 同 key 重放看到同一个 run 的失败或可重试状态，不创建重复 run |

## 任务列表 / 状态查询 DTO

适用接口：

- `GET /api/v1/courses/{courseId}/resources/imports/bilibili`
- `GET /api/v1/bilibili-import-runs/{importRunId}/status`

响应字段：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `importRunId` | number | `9001` | 导入 run ID |
| `courseId` | number | `101` | 课程 ID |
| `sourceUrl` | string | `https://www.bilibili.com/video/BV1xx411c7mD?p=2` | 原始链接 |
| `sourceType` | string | `multi_p` | 来源类型 |
| `status` | string | `downloading` | 导入 run 状态 |
| `progressPct` | number | `42` | 进度百分比 |
| `stage` | string | `download` | 展示阶段 |
| `taskId` | number | `7001` | 关联 async task ID |
| `resourceIds` | array[number] | `[]` | 已创建课程资源 ID |
| `preview` | object | `{ "title": "...", "parts": [...] }` | 预览摘要 |
| `errorCode` | string/null | `null` | 失败错误码 |
| `failureReason` | string/null | `null` | 失败原因 |
| `recoverable` | boolean | `false` | 是否可恢复 |
| `nextAction` | string | `poll` | 下一步动作 |

`preview.parts[]` 摘要字段：

| 字段 | 类型 | 示例 |
|---|---|---|
| `partId` | string | `cid-1001` |
| `title` | string | `P1 行列式` |
| `durationSec` | number | `1800` |

## 取消 DTO

接口：`POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

请求：空 body。

响应 `data`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `taskId` | number | `7201` | 异步任务 ID |
| `status` | string | `canceled` | 取消后状态 |
| `nextAction` | string | `none` | 下一步动作 |
| `entity.type` | string | `bilibili_import_run` | 固定实体类型 |
| `entity.id` | number | `9101` | 导入 run ID |

边界说明：杨彩艺只记录取消请求和响应，不处理停止 HTTP、终止 ffmpeg、临时文件清理或对象存储清理。

## 字段枚举

### `sourceType`

| 取值 | 含义 |
|---|---|
| `single_video` | 单视频入口或单 P 视频 |
| `multi_p` | 多 P 视频入口 |
| `collection` | 合集入口 |
| `bangumi` | 番剧入口 |

### `qualityPreference`

| 取值 | 含义 |
|---|---|
| `android_safe` | phase 1 唯一允许值；优先 H.264/AVC 视频和 AAC 音频 |

### `selectionMode` / `defaultSelectionMode`

| 取值 | 含义 |
|---|---|
| `current_part` | 只选择当前链接指向的分 P 或当前条目 |
| `all_parts` | 选择预览中的全部可导入条目 |
| `selected_parts` | 选择指定条目 |

### `bilibili_import_run.status`

| 状态 | 含义 | 是否终态 |
|---|---|---|
| `pending` | run 已创建，等待 worker 或调度器处理 | 否 |
| `fetching_metadata` | 正在解析 URL、元数据、分 P、合集或番剧条目 | 否 |
| `waiting_download` | 元数据已确认，等待下载槽位 | 否 |
| `downloading` | 正在下载音视频流 | 否 |
| `merging` | 正在用 ffmpeg stream copy 合并 | 否 |
| `uploading` | 正在上传对象存储并准备课程资源入库 | 否 |
| `imported` | 已创建课程资源并可进入学习链路 | 是 |
| `failed` | 不可恢复失败 | 是 |
| `recoverable` | 可恢复失败；`nextAction=retry` 时调用 async task retry | 是 |
| `canceled` | 用户或系统取消，副作用已尽力清理 | 是 |

### `stage`

| 取值 | 含义 |
|---|---|
| `queued` | 已入队或等待 worker 领取 |
| `metadata` | 正在获取或复用预览元数据 |
| `download` | 正在下载音视频流 |
| `ffmpeg` | 正在用 ffmpeg 合并 |
| `object_storage` | 正在上传对象存储 |
| `resource_import` | 正在创建课程资源记录 |
| `done` | 已完成并可进入学习链路 |
| `error` | 失败或可恢复失败的展示阶段 |
| `canceling` | 正在处理取消和副作用清理 |
| `canceled` | 已取消 |

## `async_tasks` 映射

| `bilibili_import_run.status` | `async_tasks.status` | 说明 |
|---|---|---|
| `pending`、`waiting_download` | `queued` | 等待元数据、排队或等待下载槽位 |
| `fetching_metadata`、`downloading`、`merging`、`uploading` | `running` | worker 正在执行 |
| `imported` | `succeeded` | 课程资源已创建 |
| `failed` | `failed` | 不可恢复失败 |
| `recoverable` | `failed` | 可恢复失败仍在任务层标记失败，run 响应承载恢复语义 |
| `canceled` | `canceled` | 已取消 |

`async_tasks.entity.type` 固定为 `bilibili_import_run`，`async_tasks.entity.id` 固定为 `importRunId`。

## Bilibili 错误码

| 错误码 | 说明 |
|---|---|
| `bilibili.not_implemented` | V1 B站导入与扫码登录接口已预留，但当前服务尚未接通 |
| `bilibili.auth_required` | V2 B站导入需要扫码登录后才能继续 |
| `bilibili.auth_expired` | V2 B站登录态过期或服务端凭据失效 |
| `bilibili.unsupported_url` | V2 B站链接不属于单视频、多 P、合集或番剧支持范围 |
| `bilibili.access_denied` | B站内容不可访问，包含付费、会员、DRM、地区限制或账号无权限 |
| `bilibili.metadata_failed` | B站元数据、分 P、合集或番剧条目获取失败 |
| `bilibili.playurl_failed` | B站播放地址获取失败或没有可用音视频流 |
| `bilibili.download_failed` | B站音视频流下载失败 |
| `bilibili.merge_failed` | ffmpeg 合并音视频失败 |
| `bilibili.upload_failed` | 合并产物上传对象存储失败 |
| `bilibili.import_failed` | 上传后创建课程资源失败 |
| `bilibili.cancel_failed` | 取消导入任务或清理副作用失败 |
| `bilibili.run_not_found` | B站导入 run 不存在或不属于当前用户 |
| `bilibili.selection_invalid` | B站导入选择模式或分 P 选择项不合法 |
| `bilibili.preview_not_found` | B站导入预览结果不存在或已失效 |

共享错误码：

| 错误码 | 场景 |
|---|---|
| `async_task.enqueue_failed` | 任务记录创建后派发到 dispatcher / broker 失败 |
| `idempotency.body_mismatch` | 同一幂等 scope 和 key 被不同请求体复用 |
| `common.idempotency_replay` | 已开始但尚未完成的同一幂等请求回放 |

## V1 历史 Stub 说明

| 项目 | 说明 |
|---|---|
| V1 历史错误码 | `bilibili.not_implemented` |
| V1 历史行为 | 鉴权通过后统一返回 `501`，不创建任务、不触发 MinIO、不接通扫码 |
| 现在用途 | 只作为历史说明；V2 真实导入不受 V1 stub 约束 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理 QR、登录态、preview、创建任务、列表、状态、取消 DTO | 实现扫码登录 |
| 整理 B站状态、stage、错误码和 async task 映射 | 处理 cookie / 凭据加密 |
| 整理任务列表样例和状态查询样例 | 实现下载、ffmpeg 合并、对象存储上传 |
| 整理失败原因和可恢复状态记录 | 处理取消副作用和临时文件清理 |
| 汇总待曹乐判断的问题 | 判断会员、付费、DRM、地区限制绕过策略 |
