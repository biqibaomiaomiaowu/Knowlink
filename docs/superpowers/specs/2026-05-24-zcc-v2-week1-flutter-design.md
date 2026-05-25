# 朱春雯 V2 第一周 Flutter 前端设计

日期：2026-05-24

## 1. 背景与目标

V2 第一周目标是让阶段一基础闭环有可验收入口。朱春雯 owner 范围是 Flutter 页面、Android 运行、页面设计优化、前端交互和前端联调。后端 B站导入 contract、状态机、课程库字段和当前课程语义已经由 V2 文档冻结，Flutter 侧只消费已冻结字段，不重新定义后端状态或业务语义。

本设计采用第一周最小闭环：在 Flutter 导入页补齐 B站扫码登录、登录态展示、资源预览、分 P 选择、创建导入任务、导入状态展示、失败提示和取消入口；保留现有手动创建课程、文件上传、资源列表、解析进度和讲义入口。课程详情和课程切换只补前端消费所需的最小 API 与状态展示，不新增复杂独立页面。

## 2. Owner 边界

本轮允许修改：

- `client_flutter/lib/**`
- `client_flutter/test/**`
- Superpowers spec/plan 文档

本轮不修改：

- `server/**`
- `schemas/**`
- `alembic/**`
- `docs/contracts/v2-bilibili-import-contract.md`
- B站下载、WBI、playurl、HTTP 下载、ffmpeg、对象存储上传、任务恢复、取消副作用清理等后端核心链路

Flutter 不读取、不缓存、不打印、不展示 `SESSDATA`、`bili_jct`、`DedeUserID` 或完整 cookie。登录态只通过 `GET /api/v1/bilibili/auth/session` 的 `loginStatus` 等安全字段展示。

## 3. 用户体验范围

### 3.1 导入页结构

`CourseImportPage` 继续作为阶段一导入入口。页面保留现有课程创建和本地文件上传区块，并新增 B站导入区块。

B站导入区块在没有 `courseId` 时展示禁用状态，提示先创建课程或从推荐页进入已有课程；有 `courseId` 后开放登录态、扫码、预览和导入任务操作。

### 3.2 B站登录

页面进入后可查询服务端 B站登录态：

- 已登录：展示 `loginStatus`、昵称和过期时间。
- 未登录或过期：展示扫码登录入口。
- 查询失败：展示可重试错误。

点击扫码登录后，Flutter 调用创建二维码会话接口，展示 `qrCodeUrl` 和过期时间，并轮询二维码状态。`confirmed` 后刷新服务端登录态；`expired` 或 `failed` 后停止轮询并允许重新创建二维码。

### 3.3 资源预览与选择

用户输入 B站链接后点击预览。Flutter 调用 preview 接口，展示：

- 标题、封面、来源类型、总分 P 数。
- `parts[]` 列表，每项展示标题、页码、时长。
- 默认选中 `selectedByDefault=true` 的 part。

选择模式规则：

- 如果全选所有 part，则请求 `selectionMode=all_parts`。
- 如果选择集合完全等于 `selectedByDefault=true` 的默认集合，则请求 `selectionMode=current_part`。
- 如果用户手动选择了非默认集合且不是全选，则请求 `selectionMode=selected_parts` 和 `selectedPartIds`。

`qualityPreference` 第一周固定为 `android_safe`，页面不提供其他枚举。

### 3.4 创建导入与状态展示

创建导入任务时，Flutter 发送 `previewId`、`sourceUrl`、`selectionMode`、`selectedPartIds` 和 `qualityPreference=android_safe`，并携带稳定的 `Idempotency-Key`。创建成功后保存 `taskId` 和 `importRunId`，开始刷新状态。

状态展示读取 `GET /api/v1/bilibili-import-runs/{importRunId}/status`，展示：

- `status`
- `stage`
- `progressPct`
- `failureReason`
- `nextAction`
- `resourceIds`
- preview 标题和 parts 摘要

终态处理：

- `imported`：停止轮询，刷新课程资源列表，展示进入解析进度按钮。
- `failed` / `recoverable`：停止轮询，展示 `failureReason` 和错误码；`nextAction=retry` 时只展示“可重试”提示，不在第一周新增未确认的重试 UI。
- `canceled`：停止轮询，展示已取消。

取消按钮调用 `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`。Flutter 只展示取消结果，不实现下载中断或临时文件清理。

## 4. Flutter 组件与状态设计

### 4.1 Models

新增 `client_flutter/lib/shared/models/bilibili_import_models.dart`，负责 V2 B站导入 DTO：

- `BilibiliQrSessionModel`
- `BilibiliAuthSessionModel`
- `BilibiliPreviewModel`
- `BilibiliPreviewPartModel`
- `BilibiliImportCreateRequestModel`
- `BilibiliImportTaskModel`
- `BilibiliImportRunModel`
- `BilibiliImportRunListModel`

模型只保留 contract 字段，不保存 cookie 或后端内部字段。

新增 `client_flutter/lib/shared/models/bilibili_import_state.dart`，负责 Provider UI 状态：

- 当前登录态
- 当前二维码会话
- 输入 URL
- preview 结果和选择集合
- 当前创建任务结果
- 当前 run 状态
- 正在加载、预览、创建、取消的状态

### 4.2 ApiClient

在 `ApiClient` 中新增方法：

- `createBilibiliQrSession()`
- `fetchBilibiliQrSession(String sessionId)`
- `fetchBilibiliAuthSession()`
- `deleteBilibiliAuthSession()`
- `previewBilibiliImport({required String courseId, required String sourceUrl})`
- `createBilibiliImport({required String courseId, required BilibiliImportCreateRequestModel request, required String idempotencyKey})`
- `fetchBilibiliImportRuns(String courseId)`
- `fetchBilibiliImportRunStatus(int importRunId)`
- `cancelBilibiliImportRun(int importRunId)`

课程基础 API 增补：

- `fetchRecentCourses()`
- `fetchCourse(String courseId)`
- `fetchCurrentCourse()`
- `switchCurrentCourse(String courseId)`

课程基础 API 只用于第一周课程切换和详情最小消费，不新增复杂导航结构。

### 4.3 Provider

新增 `client_flutter/lib/shared/providers/bilibili_import_provider.dart`。Provider 负责：

- 查询登录态。
- 创建二维码会话和轮询二维码状态。
- 维护 URL 输入、preview 和 part 选择。
- 创建导入任务和稳定幂等 key。
- 查询导入 run 列表并恢复最近任务。
- 刷新当前 run 状态。
- 取消当前 run。
- 完成导入后触发现有资源列表刷新，由页面调用 `courseImportProvider.fetchResources(courseId)`。

Provider 不直接执行无限后台轮询。页面层用显式刷新按钮和有限轮询触发，避免 widget 测试与 Android 前台生命周期复杂化。

### 4.4 页面

`CourseImportPage` 新增 B站导入区块，复用现有卡片、按钮、加载和错误组件。页面不创建新的顶级路由，降低第一周范围风险。

页面交互顺序：

1. 有效 `courseId` 后查询 B站登录态和导入 run 列表。
2. 未登录时展示扫码登录。
3. 已登录后输入链接并预览。
4. preview 后选择 parts 并创建导入任务。
5. 创建后展示状态、刷新和取消。
6. 完成后刷新资源列表并引导进入解析进度。

## 5. 错误处理

所有网络错误以现有 `AppErrorView` 或区块内错误文本展示。接口错误不改写后端 `errorCode`，只做用户可读文案包装。

重点错误展示：

- `bilibili.auth_required` / `bilibili.auth_expired`：提示重新扫码。
- `bilibili.unsupported_url`：提示链接不在第一周支持范围。
- `bilibili.access_denied`：提示内容不可访问，不提供绕过建议。
- `bilibili.selection_invalid`：提示重新选择分 P。
- `bilibili.preview_not_found`：提示重新预览。
- `bilibili.cancel_failed`：提示当前状态不可取消。

## 6. 测试策略

必须按 TDD 分层补测试：

1. 模型测试：验证 V2 B站 DTO JSON 解析和请求序列化。
2. ApiClient 测试：验证路径、HTTP method、请求体、`Idempotency-Key` 和响应解析。
3. Provider 测试：验证登录、扫码、preview、选择、创建、状态刷新、取消和完成后状态。
4. Widget 测试：验证导入页在无课程时禁用 B站导入，有课程时展示登录态、扫码、preview parts、导入状态、失败原因和取消按钮。
5. 回归测试：保留现有手动创建、文件上传、资源列表、推荐确认、解析进度和讲义测试全部通过。

最终验证命令：

```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

## 7. 非目标

- 不做 Android 真机录屏；CLI 环境只能保证 Flutter 代码和测试支持，录屏需用户在本地设备执行。
- 不实现 B站合集和番剧完整前端体验收口；第一周只按 contract 支持展示，真实完整验收属于第二周。
- 不新增未冻结 API 或错误码。
- 不把 B站导入状态混入解析 `pipeline-status` 的后端 contract。
- 不调整 QA、测验、复习页面，除非现有测试暴露出与导入入口直接相关的问题。

## 8. 验收口径

本轮完成后，Flutter 应满足：

- Android 或 Flutter Web 可进入导入页并看到 B站导入入口。
- 已有课程下可以查看 B站登录态、发起扫码登录、输入 B站链接、预览资源、选择 parts。
- 可以创建 B站导入任务，并看到进度、失败、取消和完成状态。
- 导入完成后可以刷新课程资源并进入解析进度。
- 首页、推荐、手动导入、解析进度和讲义主链路现有测试不退化。
