# KnowLink V2 阶段一曹乐后端交接说明

日期：2026-05-19

## 0. 曹乐已完成

- V2 B站导入 API contract、错误码、状态机和 `async_tasks` 映射已冻结。
- B站扫码登录、服务端 cookie 保存、登录态查询、预览、任务创建、状态查询和取消接口已接入后端服务。
- 小型 B站下载器边界已实现：metadata、WBI 签名 playurl、HTTP 下载、取消 token、ffmpeg stream copy 合并和对象存储上传。
- B站导入 runner 已接通：`server.tasks.bilibili_import.BilibiliImportRunner` 负责从 `bilibili_import_run` 下载、合并、上传并创建课程资源。
- Dramatiq worker 已接线 `server.tasks.worker:bilibili_import`，真实队列模式会创建 SQL runtime repository/session 并关闭 session。
- 导入后的课程资源会标记 `sourceType=bilibili`、`originUrl` 和 `parsePolicyJson.importRunId`。
- SQL 运行时下 B站 cookie 使用加密 envelope 落库；建议通过 `KNOWLINK_BILIBILI_CREDENTIAL_SECRET` 配置独立凭据密钥。
- 课程库 V2 字段、推荐 `reasonMaterials` / `nextAction`、课程详情、当前课程和 `switch-current` 基础语义已接入。
- SQL 当前课程使用 `courses.is_current` 显式持久标记；未显式切换时回退最近更新课程。
- 单视频、多 P、合集和番剧的 URL 识别、预览、任务创建和 runner 导入路径已接入；合集和番剧的真实公网样例验收仍按阶段一第 2 周执行。

## 1. 曹乐可独立交付范围

- B站扫码登录、服务端凭据保存和登录态查询。
- B站单视频、多 P 的 URL 识别、元数据预览和导入任务创建。
- B站合集、番剧的 URL 识别、元数据预览和 contract 枚举；真实公网样例可用性在第 2 周验收。
- B站 playurl 获取、HTTP 下载、ffmpeg stream copy 合并、对象存储上传和课程资源入库。
- `bilibili_import_run` 状态机、`async_tasks` 映射、进度、失败原因、可恢复失败、通用 retry 和协作式取消副作用清理。
- B站 V2 contract、错误码、后端测试和验收样例。
- 课程库字段、推荐理由语义、多课程基础管理语义和复杂版面增强最低验收标准的后端口径。

## 2. 非曹乐独立范围

- Flutter 页面、Android 运行、扫码页、预览页、导入进度页、失败提示和取消入口由朱春雯负责。
- 页面视觉优化、真机截图/录屏和前端交互细节由朱春雯负责。
- 基础接口文档整理、测试数据整理、联调记录、任务列表展示字段整理等低风险辅助后端事项由杨彩艺负责。
- 用户测试调研、测试脚本、用户反馈记录和报告由杨彩艺负责。

## 3. 前端快速说明

- 登录页调用 `POST /api/v1/bilibili/auth/qr/sessions` 获取 `qrCodeUrl`，前端必须把它作为二维码内容本地编码渲染，不得作为图片/iframe/跳转 URL 直接请求；随后轮询 `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`。
- 导入前调用 `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview` 展示 `parts`；公共可访问视频不要求先扫码登录。
- 创建任务调用 `POST /api/v1/courses/{courseId}/resources/imports/bilibili`，随后轮询 `GET /api/v1/bilibili-import-runs/{importRunId}/status`。
- 取消按钮调用 `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`，响应为 async-task 形态。
- 前端只展示 `status`、`progressPct`、`stage`、`failureReason`、`nextAction` 和 `resourceIds`，不得读取或保存 B站 cookie。

## 3.1 给朱春雯

- 页面只需要展示 `qrCodeUrl`、`loginStatus`、`preview.parts`、`status`、`progressPct`、`stage`、`failureReason`、`nextAction` 和 `resourceIds`；`qrCodeUrl` 是二维码内容，不是图片地址。
- 前端不读取、不缓存、不打印 cookie；登录态只通过 `GET /api/v1/bilibili/auth/session` 展示。
- `GET /api/v1/bilibili/auth/session` 未登录返回 `loginStatus=inactive`，过期返回 `loginStatus=expired`，不作为预览和导入按钮的硬前置。
- 扫码、资源预览、导入进度、失败提示和取消入口按 contract 字段渲染即可。
- Android 真机录屏、页面截图、扫码页和进度页交互由朱春雯补充验收证据。
- 推荐页可读取 `reasonMaterials` 和 `nextAction.type=confirm_course`；课程详情调用 `GET /api/v1/courses/{courseId}`，当前课程调用 `GET /api/v1/courses/current`，切换课程调用 `POST /api/v1/courses/{courseId}/switch-current`。

## 3.2 给杨彩艺

- 可以整理状态查询样例、任务列表样例、错误码说明、基础 DTO 字段说明和联调记录。
- 可以整理课程库 seed、课程详情、当前课程、课程切换和推荐结果样例。
- 不要实现下载、ffmpeg 合并、对象存储上传、取消副作用、任务恢复和复杂状态机。
- 不要新增未冻结错误码；若遇到缺字段，先回到 `docs/contracts/` 和本文件确认口径。

## 4. 辅助后端边界

杨彩艺可以独立处理：

- 按 contract 整理接口字段说明和联调记录。
- 整理 B站导入状态查询、任务列表展示和取消入口的请求/响应样例。
- 整理 Android 联调所需后端地址、URL 可达性记录和测试数据。
- 补充基础错误返回说明，但不得新增未冻结错误码。

杨彩艺不负责：

- B站凭据处理、下载、ffmpeg 合并、对象存储上传链路。
- 复杂状态机、任务恢复、取消副作用清理。
- 会员、付费、地区限制等访问边界判断策略。

## 5. Contract 指针

- V2 B站导入 contract：[../contracts/v2-bilibili-import-contract.md](../contracts/v2-bilibili-import-contract.md)。
- V2 阶段计划与 owner 边界：[phase-plan.md](./phase-plan.md)。
- V1 B站 `501 bilibili.not_implemented` 只作为历史 stub 口径保留。

## 6. 状态与错误码指针

- 状态机以 `docs/contracts/v2-bilibili-import-contract.md` 第 5 节为准。
- `bilibili_import_run.status` 到 `async_tasks.status` 的映射以 contract 第 7 节「`async_tasks` 映射」为准。
- 错误码以 [../contracts/error-codes.md](../contracts/error-codes.md) 的 Bilibili 段落为准。
- 状态拼写统一使用 `canceled`。
- 访问受限统一使用 `bilibili.access_denied`；ffmpeg 合并失败统一使用 `bilibili.merge_failed`。
- `recoverable` 的前端动作统一为 `nextAction=retry`；重试通过 `POST /api/v1/async-tasks/{taskId}/retry` 重新入队同一个 `bilibili_import` task。
- 取消为协作式取消：API 先把 run/task 标为 `canceled`，worker 的下载和 ffmpeg cancel token 观察该状态后停止 HTTP 请求或子进程，并清理临时目录。

## 7. 曹乐独立验收证据

曹乐独立验收至少需要：

- 一个固定 B站单视频或多 P 样例。
- 一个固定合集或番剧样例；若公网内容不可访问，需要记录 `bilibili.access_denied` 或具体失败码。
- 导入状态接口返回样例。
- 导入后课程资源记录，资源需能标识来源为 B站。
- 失败或不可访问样例的错误码和 `failureReason`。
- 取消任务后的状态接口返回和临时文件清理记录。
- 后端测试命令和本地运行命令。

## 8. 小组联调依赖

- Android 截图或录屏由朱春雯在前端和真机联调中提供。
- 页面扫码、预览、进度、失败和取消展示由朱春雯按 contract 字段对齐。
- 状态样例、任务列表字段说明、测试数据整理和联调记录由杨彩艺按曹乐冻结字段补齐。

## 9. 复杂布局最低验收标准

- 表格：保留行列结构；无法保留原结构时转换为可读 Markdown 表格。
- 公式：不能出现明显乱码；无法结构化时保留原文或 OCR 文本，并记录 issue。
- 图片：保留 caption、位置和来源引用。
- 复杂布局：不丢页、不让引用断裂、不混同不同页或 slide 的 citation。

交接时建议每个复杂资料样例至少记录：

- 文件类型、文件名和页码 / slide 范围。
- 解析后的 `segmentType`、定位字段和 citation。
- 表格、公式、图片 caption 是否满足上述最低标准。
- 若依赖 OCR / vision / ASR，记录对应 enable flag 和 issue code。

## 10. 本地命令

```bash
KNOWLINK_RUNTIME_REPOSITORY_BACKEND=memory KNOWLINK_STORAGE_BACKEND=demo KNOWLINK_QA_PROVIDER=vivo KNOWLINK_ENABLE_VIVO_QA=false .venv/bin/python -m pytest -s \
  server/tests/test_bilibili_contract.py \
  server/tests/test_bilibili_url.py \
  server/tests/test_bilibili_service.py \
  server/tests/test_bilibili_import_runner.py \
  server/tests/test_bilibili_sql_runtime.py \
  server/tests/test_async_task_reliability.py::test_retry_async_task_reenqueues_supported_task_types \
  server/tests/test_api.py::test_course_detail_and_current_course_switch \
  server/tests/test_scaffold_consistency.py::test_v2_course_catalog_fields_are_present \
  server/tests/test_sql_runtime_contract.py::test_sql_repository_current_course_uses_recent_then_explicit_switch \
  -q
```

如果只验证文档 contract，可运行：

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py server/tests/test_contract_freeze.py -q
```

如果验证复杂版面和 V2 解析 contract，可运行：

```bash
KNOWLINK_ENABLE_VIVO_VISION=false KNOWLINK_ENABLE_VIVO_ASR=false KNOWLINK_ENABLE_VIVO_OCR=false .venv/bin/python -m pytest -s \
  server/tests/test_ai_v2_contracts.py \
  server/tests/test_parsers.py \
  -q
```

本地 `.env` 如果启用了 SQL、MinIO 或真实 QA，测试时建议显式覆盖：

- `KNOWLINK_RUNTIME_REPOSITORY_BACKEND=memory`
- `KNOWLINK_STORAGE_BACKEND=demo`
- `KNOWLINK_QA_PROVIDER=vivo`
- `KNOWLINK_ENABLE_VIVO_QA=false`

## 11. 风险

- B站登录态可能过期或触发风控，必须返回明确认证错误，不把 cookie 暴露给前端。
- 会员、付费、DRM、地区限制或账号无权限内容只返回访问受限，不做绕过。
- 下载与 ffmpeg 合并链路需要严格响应取消，避免临时文件和半成品对象残留。
- `bilibili_import_run` 与 `async_tasks` 状态需要保持一致，否则前端进度和后端恢复会分叉。
- Android 端播放稳定性依赖编码选择，默认优先 H.264/AVC 和 AAC。

## 12. 2026-05-28 平板端联调记录

- 平板端联调基本通过；当前已验证的核心功能入口、网络访问、资源上传和阶段一主流程未发现功能性阻塞。
- 平板 USB 联调需要同时映射 FastAPI 与 MinIO：`adb reverse tcp:8000 tcp:8000`、`adb reverse tcp:9000 tcp:9000`。只映射 `8000` 时，上传初始化可以成功，但文件 PUT 到 `127.0.0.1:9000` 的 MinIO 预签名 URL 会失败。
- 当前唯一必须立即修复的问题是讲义页平板端布局：页面在平板上变成上下结构，而不是预期的左 / 中 / 右三栏结构。该问题属于 Flutter 平板 UI 适配与讲义页交互体验，应作为进入完整阶段一平板验收前的高优先级问题关闭。
