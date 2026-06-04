# 杨彩艺 V2 B站导入联调记录模板

来源：

- `docs/contracts/v2-bilibili-import-contract.md`
- `docs/contracts/error-codes.md`
- `docs/v2/phase1-cao-le-handoff.md`

用途：为 V2 B站扫码、预览、任务创建、任务列表、状态查询、取消、错误码和验收证据准备联调记录模板。本文只做记录模板，不实现扫码、下载、ffmpeg、对象存储上传、取消副作用、任务恢复或复杂状态机。

实际联调记录见 [test-bilibili.md](./test-bilibili.md)。截至 2026-05-24，已记录创建 QR session 和轮询 QR session 的返回；登录态、preview 和创建导入任务仍待有效扫码登录和固定 B站样例补充。

## 联调接口

| 场景 | 方法 | 路径 | 记录重点 |
|---|---|---|---|
| 创建扫码会话 | `POST` | `/api/v1/bilibili/auth/qr/sessions` | `sessionId`、QR `status`、`qrCodeUrl`、`expiresAt` |
| 查询扫码会话 | `GET` | `/api/v1/bilibili/auth/qr/sessions/{sessionId}` | QR `status` 流转 |
| 查询登录态 | `GET` | `/api/v1/bilibili/auth/session` | `loginStatus`、`userNickname`、`expiresAt`，确认不返回 cookie |
| 清除登录态 | `DELETE` | `/api/v1/bilibili/auth/session` | `deleted` |
| 创建预览 | `POST` | `/api/v1/courses/{courseId}/resources/imports/bilibili/preview` | `previewId`、`sourceType`、`parts`、`defaultSelectionMode` |
| 创建导入任务 | `POST` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | `taskId`、`entity.id`、幂等 key |
| 任务列表 | `GET` | `/api/v1/courses/{courseId}/resources/imports/bilibili` | `items[]`、恢复页面展示字段 |
| 状态查询 | `GET` | `/api/v1/bilibili-import-runs/{importRunId}/status` | `status`、`progressPct`、`stage`、`failureReason`、`nextAction` |
| 取消任务 | `POST` | `/api/v1/bilibili-import-runs/{importRunId}/cancel` | `status=canceled`、`nextAction=none` |
| 重试任务 | `POST` | `/api/v1/async-tasks/{taskId}/retry` | 仅记录 `recoverable` 后的 retry 入口和结果 |

## 通用记录

| 记录项 | 填写内容 |
|---|---|
| 测试时间 |  |
| 测试人员 | 杨彩艺 |
| 环境 | 本地 / 模拟器 / 真机 / Flutter Web |
| 后端地址 |  |
| MinIO public endpoint |  |
| demo token 是否配置 | 是 / 否；不要记录真实 token |
| B站登录态 | 未登录 / 已登录 / 已过期 |
| 课程 ID |  |
| B站样例类型 | 单视频 / 多 P / 合集 / 番剧 / 不可访问样例 |
| `sourceUrl` |  |
| 响应 JSON 保存位置 |  |
| 截图或录屏 |  |
| 结论 | 通过 / 不通过 / 待曹乐确认 |

## QR 登录记录

| 记录项 | 填写内容 |
|---|---|
| 创建 QR 接口状态码 |  |
| `sessionId` |  |
| 初始 QR `status` |  |
| `qrCodeUrl` 是否可展示 | 是 / 否 |
| `expiresAt` |  |
| 轮询次数 |  |
| 轮询状态序列 | 例如 `pending_scan -> scanned -> confirmed` |
| 最终 QR `status` |  |
| 登录态接口状态码 |  |
| `loginStatus` |  |
| `userNickname` |  |
| 是否返回 cookie 原文 | 应为否 |
| 错误码 |  |
| 证据 | 截图 / 响应 JSON |

## Preview 记录

| 记录项 | 填写内容 |
|---|---|
| Preview 接口状态码 |  |
| `courseId` |  |
| `sourceUrl` |  |
| `previewId` |  |
| `sourceType` | `single_video` / `multi_p` / `collection` / `bangumi` |
| `title` |  |
| `coverUrl` |  |
| `totalParts` |  |
| `defaultSelectionMode` | `current_part` / `all_parts` / `selected_parts` |
| `parts[].partId` |  |
| `parts[].title` |  |
| `parts[].durationSec` |  |
| `parts[].cid` |  |
| `parts[].pageNo` |  |
| `parts[].selectedByDefault` |  |
| 失败错误码 |  |
| 失败原因 |  |
| 证据 | 响应 JSON、截图 |

## 创建导入任务记录

| 记录项 | 填写内容 |
|---|---|
| 创建任务接口状态码 |  |
| `Idempotency-Key` | 记录是否使用，不记录敏感信息 |
| `courseId` |  |
| `previewId` |  |
| `sourceUrl` |  |
| `selectionMode` | `current_part` / `all_parts` / `selected_parts` |
| `selectedPartIds` |  |
| `qualityPreference` | 应为 `android_safe` |
| `taskId` |  |
| `status` |  |
| `nextAction` |  |
| `entity.type` | 应为 `bilibili_import_run` |
| `entity.id` / `importRunId` |  |
| 幂等重复提交结果 |  |
| 幂等 body mismatch 结果 |  |
| 错误码 |  |
| 证据 | 响应 JSON |

## 任务列表记录

接口：`GET /api/v1/courses/{courseId}/resources/imports/bilibili`

| 记录项 | 填写内容 |
|---|---|
| 列表接口状态码 |  |
| `items.length` |  |
| `importRunId` |  |
| `courseId` |  |
| `sourceUrl` |  |
| `sourceType` |  |
| `status` |  |
| `progressPct` |  |
| `stage` |  |
| `taskId` |  |
| `resourceIds` |  |
| `preview.title` |  |
| `preview.parts[]` 摘要 |  |
| `errorCode` |  |
| `failureReason` |  |
| `recoverable` |  |
| `nextAction` |  |
| 前端恢复页面是否够用 | 是 / 否；备注 |
| 证据 | 响应 JSON、截图 |

## 状态查询记录

接口：`GET /api/v1/bilibili-import-runs/{importRunId}/status`

| 记录项 | 填写内容 |
|---|---|
| 状态接口状态码 |  |
| `importRunId` |  |
| `courseId` |  |
| `taskId` |  |
| `sourceType` |  |
| `status` |  |
| 映射到 `async_tasks.status` |  |
| `progressPct` |  |
| `stage` |  |
| `resourceIds` |  |
| `errorCode` |  |
| `failureReason` |  |
| `recoverable` |  |
| `nextAction` |  |
| 是否进入终态 | 是 / 否 |
| 证据 | 响应 JSON、截图或录屏 |

状态序列记录：

| 时间点 | `status` | `stage` | `progressPct` | `resourceIds` | `errorCode` | 备注 |
|---|---|---|---|---|---|---|
| T1 |  |  |  |  |  |  |
| T2 |  |  |  |  |  |  |
| T3 |  |  |  |  |  |  |

## 取消记录

接口：`POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

| 记录项 | 填写内容 |
|---|---|
| 点击取消时 run `status` |  |
| 点击取消时 `stage` |  |
| 取消接口状态码 |  |
| 响应 `taskId` |  |
| 响应 `status` | 应为 `canceled` 或错误 |
| 响应 `nextAction` |  |
| 响应 `entity.type` |  |
| 响应 `entity.id` |  |
| 取消后再次查询 `status` |  |
| 取消后是否产生课程资源 | 只记录观察结果 |
| 临时文件清理记录 | 如曹乐提供则附上；杨彩艺不判断实现 |
| 错误码 |  |
| 证据 | 响应 JSON、截图或录屏 |

## 失败 / 可恢复记录

| 记录项 | 填写内容 |
|---|---|
| 失败样例类型 | 不支持 URL / 未登录 / 登录过期 / 访问受限 / 元数据失败 / 下载失败 / 合并失败 / 上传失败 / 导入失败 |
| `sourceUrl` |  |
| HTTP 状态码 |  |
| `errorCode` |  |
| `failureReason` |  |
| `recoverable` |  |
| `nextAction` |  |
| 是否需要重新扫码 | 是 / 否 |
| 是否需要 retry | 是 / 否 |
| retry 接口结果 |  |
| 证据 | 响应 JSON、截图 |

## 错误码核对表

| 错误码 | 是否出现 | 证据位置 | 备注 |
|---|---|---|---|
| `bilibili.auth_required` |  |  |  |
| `bilibili.auth_expired` |  |  |  |
| `bilibili.unsupported_url` |  |  |  |
| `bilibili.access_denied` |  |  |  |
| `bilibili.metadata_failed` |  |  |  |
| `bilibili.playurl_failed` |  |  |  |
| `bilibili.download_failed` |  |  |  |
| `bilibili.merge_failed` |  |  |  |
| `bilibili.upload_failed` |  |  |  |
| `bilibili.import_failed` |  |  |  |
| `bilibili.cancel_failed` |  |  |  |
| `bilibili.run_not_found` |  |  |  |
| `bilibili.selection_invalid` |  |  |  |
| `bilibili.preview_not_found` |  |  |  |
| `async_task.enqueue_failed` |  |  |  |
| `idempotency.body_mismatch` |  |  |  |

## 验收证据清单

| 证据 | 负责人 | 杨彩艺记录事项 |
|---|---|---|
| 固定 B站单视频或多 P 样例 | 曹乐提供后端样例，朱春雯补前端展示 | 记录 URL、preview、任务状态、资源结果 |
| 合集或番剧样例 | 曹乐提供可访问样例或失败原因 | 记录 `sourceType`、错误码、`failureReason` |
| 导入状态接口返回样例 | 杨彩艺整理 | 保存 JSON 和状态序列 |
| 导入后课程资源记录 | 杨彩艺整理 | 记录 `resourceIds`、课程资源列表截图或响应 |
| 失败或不可访问样例 | 杨彩艺整理，曹乐判断 | 记录错误码和 `failureReason` |
| 取消任务状态样例 | 杨彩艺整理，曹乐判断副作用 | 记录取消响应和取消后状态 |
| Android 录屏 / 页面截图 | 朱春雯 | 杨彩艺可引用保存位置 |

## 问题归类模板

| 问题类型 | 示例 | 归属 |
|---|---|---|
| 字段不一致 | 前端需要字段和 contract 不一致 | 先记录，需曹乐确认 |
| 状态不一致 | run `status` 与 `async_tasks.status` 映射不一致 | 曹乐 |
| 错误码不在冻结表 | 返回了未冻结 `bilibili.*` | 曹乐 |
| Android 地址不可达 | FastAPI 或 MinIO URL 不可达 | 杨彩艺记录，交对应负责人处理 |
| 取消副作用异常 | 取消后仍下载、仍合并、资源残留 | 曹乐 |
| 下载 / 合并 / 上传失败 | `download_failed`、`merge_failed`、`upload_failed` | 曹乐 |
| 页面展示问题 | 状态、进度、失败提示、取消按钮体验问题 | 朱春雯 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 原样记录响应 JSON、状态、错误码、截图 | 实现扫码登录 |
| 整理 preview、任务列表、状态查询、取消记录 | 处理 cookie / 凭据 |
| 整理 `failureReason`、`recoverable`、`nextAction` | 实现下载、ffmpeg、上传 |
| 汇总待曹乐判断项 | 处理取消副作用和临时文件清理 |
| 整理验收材料 | 判断会员、付费、DRM、地区限制绕过策略 |
