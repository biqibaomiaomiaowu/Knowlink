# KnowLink V2 阶段一曹乐后端交接说明

日期：2026-05-18

## 1. 曹乐可独立交付范围

- B站扫码登录、服务端凭据保存和登录态查询。
- B站单视频、多 P、合集、番剧的 URL 识别、元数据预览和导入任务创建。
- B站 playurl 获取、HTTP 下载、ffmpeg stream copy 合并、对象存储上传和课程资源入库。
- `bilibili_import_run` 状态机、`async_tasks` 映射、进度、失败原因、可恢复失败和取消副作用清理。
- B站 V2 contract、错误码、后端测试和验收样例。
- 课程库字段、推荐理由语义、多课程基础管理语义和复杂版面增强最低验收标准的后端口径。

## 2. 非曹乐独立范围

- Flutter 页面、Android 运行、扫码页、预览页、导入进度页、失败提示和取消入口由朱春雯负责。
- 页面视觉优化、真机截图/录屏和前端交互细节由朱春雯负责。
- 基础接口文档整理、测试数据整理、联调记录、任务列表展示字段整理等低风险辅助后端事项由杨彩艺负责。
- 用户测试调研、测试脚本、用户反馈记录和报告由杨彩艺负责。

## 3. 前端快速说明

- 登录页调用 `POST /api/v1/bilibili/auth/qr/sessions` 获取 `qrCodeUrl`，轮询 `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`。
- 导入前调用 `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview` 展示 `preview.parts`。
- 创建任务调用 `POST /api/v1/courses/{courseId}/resources/imports/bilibili`，随后轮询 `GET /api/v1/bilibili-import-runs/{importRunId}/status`。
- 取消按钮调用 `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`。
- 前端只展示 `status`、`progressPct`、`stage`、`failureReason`、`nextAction` 和 `resourceIds`，不得读取或保存 B站 cookie。

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
- `bilibili_import_run.status` 到 `async_tasks.status` 的映射以 contract 第 6 节为准。
- 错误码以 [../contracts/error-codes.md](../contracts/error-codes.md) 的 Bilibili 段落为准。
- 状态拼写统一使用 `canceled`。

## 7. 验收证据

阶段一验收至少需要：

- Android 截图或录屏。
- 一个固定 B站单视频或多 P 样例。
- 导入状态接口返回样例。
- 导入后课程资源记录，资源需带 `sourceType=bilibili`。
- 失败或不可访问样例的错误码和 `failureReason`。
- 取消任务后的状态接口返回和临时文件清理记录。

## 8. 本地命令

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py server/tests/test_contract_freeze.py::test_bilibili_reserved_contract_is_aligned_across_docs -q
```

后续生产代码接入时，需追加服务、路由、仓储、worker 和 SQL runtime 的对应测试命令。

## 9. 风险

- B站登录态可能过期或触发风控，必须返回明确认证错误，不把 cookie 暴露给前端。
- 会员、付费、DRM、地区限制或账号无权限内容只返回访问受限，不做绕过。
- 下载与 ffmpeg 合并链路需要严格响应取消，避免临时文件和半成品对象残留。
- `bilibili_import_run` 与 `async_tasks` 状态需要保持一致，否则前端进度和后端恢复会分叉。
- Android 端播放稳定性依赖编码选择，默认优先 H.264/AVC 和 AAC。
