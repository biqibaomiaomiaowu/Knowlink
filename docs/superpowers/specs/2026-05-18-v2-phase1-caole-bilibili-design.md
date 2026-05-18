# V2 Phase 1 Cao Le Bilibili Import Design

日期：2026-05-18

## 1. Goal

完成 KnowLink V2 阶段一中曹乐可独立交付的后端、AI/解析语义和交接文档部分：B站真实导入核心后端、课程库与推荐语义、多课程基础管理语义、复杂版面增强验收标准。

本设计采用“模仿 Bilidown 关键做法，写 KnowLink 专用小型 B站下载器”的方案。KnowLink 不直接把 Bilidown 作为黑盒任务系统接入；Bilidown 只作为实现参考。下载器必须服从 KnowLink 的 `async_tasks`、课程资源、错误码、取消、副作用清理和交接文档口径。

## 2. Scope

### 2.1 In Scope

- B站二维码登录、登录态查询、退出登录和服务端凭据保存。
- 单视频、多 P、合集、番剧的 URL 识别、元数据预览和导入任务创建。
- B站播放地址解析，默认选择 Android 与后续解析更稳的 H.264/AVC 视频和 AAC 音频。
- HTTP 下载、ffmpeg stream copy 合并、对象存储上传、课程资源入库。
- 导入任务状态机、进度、失败原因、错误码、可恢复失败和取消语义。
- 下载和 ffmpeg 子进程取消，临时文件和半成品资源清理。
- 课程库字段、推荐规则、推荐理由、多课程基础管理语义。
- 阶段一复杂版面增强的最低验收标准。
- V2 B站导入 contract、错误码、交接文档和后端测试。

### 2.2 Out Of Scope

- 收藏夹、热门列表、大规模批量下载。
- 付费、会员、DRM、地区限制内容绕过。
- 前端 Flutter 页面、Android 运行、截图录屏和页面视觉优化。
- 杨彩艺负责的辅助接口文档整理、测试样例整理和联调记录。
- 阶段二知识图谱、流式输出、主观题判卷。

## 3. Design Principles

- Contract first：先冻结 V2 API、DTO、状态和错误码，再实现。
- KnowLink owns the state：导入状态以 KnowLink `bilibili_import_run` 和 `async_tasks` 为真相源，不引入 Bilidown 的数据库或任务模型。
- Small downloader：只实现阶段一需要的 B站能力，避免复制完整 Bilidown 产品。
- Adapter boundary：B站 API、下载器、ffmpeg、对象存储分别有清晰端口，便于测试和后续替换。
- Cancellation is explicit：取消必须写入状态，停止下载和 ffmpeg，并清理临时文件。
- Handoff friendly：文档必须让朱春雯、杨彩艺能按字段和状态并行联调。

## 4. Architecture

新增后端结构：

```text
server/domain/services/bilibili.py
server/domain/repositories/interfaces.py
server/infra/repositories/memory_runtime.py
server/infra/repositories/sqlalchemy.py
server/infra/db/models/bilibili.py
server/infra/bilibili/
  __init__.py
  client.py
  downloader.py
  ffmpeg.py
  models.py
  url.py
server/tasks/bilibili_import.py
server/tasks/dispatcher.py
server/tasks/worker.py
server/schemas/requests.py
server/schemas/responses.py
docs/contracts/v2-bilibili-import-contract.md
docs/v2/phase1-cao-le-handoff.md
```

职责：

- `BilibiliService`：API-facing service，负责鉴权状态、预览、创建任务、查询任务、取消任务和错误映射。
- `BiliClient`：模仿 Bilidown 的 B站 API 访问层，负责 QR 登录、cookie 校验、视频/合集/番剧元数据、playurl。
- `BiliDownloader`：负责按 playurl 下载视频流和音频流，报告进度，响应取消 token。
- `FfmpegMerger`：负责调用 ffmpeg 做 stream copy 合并，响应取消并清理输出。
- `BilibiliImportRunner`：worker 入口，串起 metadata、download、merge、upload、resource create。
- `BilibiliImportRepository`：保存导入 run、QR session、凭据摘要和状态。
- `TaskDispatcher`：新增 `enqueue_bilibili_import`，沿用现有 `async_tasks` 机制。

## 5. API Contract

V2 需要新增独立 contract 文档：`docs/contracts/v2-bilibili-import-contract.md`，并在 `docs/contracts/api-contract.md`、`docs/contracts/error-codes.md`、`docs/README.md` 中建立入口。

API 保留现有路径，并补充预览接口：

- `POST /api/v1/bilibili/auth/qr/sessions`
- `GET /api/v1/bilibili/auth/qr/sessions/{sessionId}`
- `GET /api/v1/bilibili/auth/session`
- `DELETE /api/v1/bilibili/auth/session`
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview`
- `POST /api/v1/courses/{courseId}/resources/imports/bilibili`
- `GET /api/v1/courses/{courseId}/resources/imports/bilibili`
- `GET /api/v1/bilibili-import-runs/{importRunId}/status`
- `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`

请求字段：

- `sourceUrl`：B站链接，支持单视频、多 P、合集、番剧。
- `selectionMode`：`current_part`、`all_parts`、`selected_parts`。
- `selectedPartIds`：选择部分 P 或条目时使用。
- `qualityPreference`：默认 `android_safe`，优先 H.264/AVC + AAC。

响应字段必须至少包含：

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

## 6. State Machine

V2 状态统一使用：

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

映射到 `async_tasks.status`：

- `pending`、`waiting_download` -> `queued`
- `fetching_metadata`、`downloading`、`merging`、`uploading` -> `running`
- `imported` -> `succeeded`
- `failed`、`recoverable` -> `failed`
- `canceled` -> `canceled`

终态：

- `imported`
- `failed`
- `recoverable`
- `canceled`

取消规则：

- `pending`、`waiting_download`：直接标记 `canceled`，不产生资源。
- `fetching_metadata`：标记 `canceled`，不保留预览副作用。
- `downloading`：取消 HTTP 请求，删除临时视频/音频片段。
- `merging`：终止 ffmpeg 子进程，删除临时输出。
- `uploading`：尽力中断上传；若对象已存在但资源未入库，记录清理提示。
- `imported`：不可取消，返回当前结果。

## 7. Error Codes

新增或冻结以下错误码：

- `bilibili.auth_required`
- `bilibili.auth_expired`
- `bilibili.unsupported_url`
- `bilibili.access_denied`
- `bilibili.metadata_failed`
- `bilibili.playurl_failed`
- `bilibili.download_failed`
- `bilibili.merge_failed`
- `bilibili.upload_failed`
- `bilibili.import_failed`
- `bilibili.cancel_failed`
- `bilibili.run_not_found`
- `bilibili.preview_not_found`
- `bilibili.selection_invalid`

会员、付费、DRM、地区限制、账号无权限统一归入 `bilibili.access_denied`，`failureReason` 说明具体原因，不做绕过。

## 8. Persistence

SQL 运行时新增表或等价模型：

- `bilibili_auth_sessions`
- `bilibili_qr_sessions`
- `bilibili_import_runs`
- `bilibili_import_items`

内存运行时同步支持同等读写能力，保证本地测试和 scaffold 一致。

`bilibili_import_runs` 关键字段：

- `id`
- `course_id`
- `task_id`
- `source_url`
- `source_type`
- `status`
- `progress_pct`
- `stage`
- `preview_json`
- `selection_json`
- `resource_ids_json`
- `temp_dir`
- `error_code`
- `failure_reason`
- `recoverable`
- `created_at`
- `updated_at`
- `finished_at`

凭据保存：

- 第一阶段只做单用户环境。
- 服务端保存 cookie 必要字段，不暴露给前端。
- 文档必须标明生产环境需要加密存储；本地开发可以使用明文 DB 字段但不得提交真实凭据。

## 9. Downloader Design

小型下载器模仿 Bilidown 的分层，而不是复用 Bilidown 进程：

1. URL 解析：识别 `BV`、`b23.tv`、多 P、合集、番剧。
2. Metadata：调用 B站 API 获取标题、封面、分 P、时长、cid、aid、番剧条目。
3. Playurl：用登录 cookie 获取 DASH video/audio URL。
4. Stream choice：默认选择 H.264/AVC 视频和 AAC 音频；若不可用，记录降级原因。
5. Download：分别下载视频和音频到 run 专属临时目录。
6. Merge：调用 ffmpeg `-c copy` 合并。
7. Upload：写入对象存储。
8. Resource import：创建 `course_resources`，`sourceType=bilibili`。

临时目录格式：

```text
runtime/bilibili/{import_run_id}/
```

对象 key 格式：

```text
raw/1/{course_id}/bilibili/{import_run_id}/{safe_title}.mp4
```

## 10. Course And Recommendation Semantics

阶段一后端独立交付范围：

- 课程库 seed 扩展字段：学科、课程代码、目标人群、难度、先修要求、知识点标签、课程大纲、资源导入提示、推荐理由素材、封面、亮点。
- 推荐规则纳入目标匹配、基础水平、时间预算、考试紧迫度、标签匹配、资源可解析性。
- 推荐结果保留可解释 `reasons[]`，补充 `nextAction` 或等价下一步建议。
- 多课程基础语义冻结：课程创建、最近课程、课程详情、当前课程/切换课程、课程隔离。

第一阶段不做归档、删除、复杂搜索和个性化模型。

## 11. Complex Layout Acceptance

阶段一只冻结最低可用门槛：

- 表格：保留行列结构或转换为可读 Markdown 表格。
- 公式：不能出现明显乱码；无法结构化时保留原文或 OCR 文本并打 issue。
- 图片：至少保留 caption、位置和来源引用。
- 复杂布局：不能丢页、不能引用断裂、不能把不同页/slide 的 citation 混在同一条引用中。
- 验收材料必须包含至少一个真实资料样例和解析结果片段。

## 12. Testing Strategy

测试必须按 TDD 执行。重点测试：

- V2 contract 文档入口和错误码冻结。
- QR session 状态映射。
- auth session 不向前端泄露 cookie。
- URL 类型识别。
- preview 响应覆盖单视频、多 P、合集、番剧。
- import run 状态流转。
- `canceled` 拼写和取消副作用。
- playurl/download/merge/upload/resource create 各阶段错误映射。
- 导入完成后 `course_resources` 可查询。
- 课程库字段完整性和推荐理由可解释。
- 多课程详情/当前课程语义。

真实 B站和 ffmpeg 集成测试需要可选开关，默认单元测试使用 fake Bili API 和 fake downloader，避免 CI 被账号、网络、地区和大文件影响。

## 13. Handoff Documents

新增 `docs/v2/phase1-cao-le-handoff.md`，结构：

1. 曹乐已完成范围。
2. 曹乐未承诺范围。
3. 给朱春雯的前端字段和状态说明。
4. 给杨彩艺的辅助后端/文档/联调材料边界。
5. B站导入接口清单。
6. 状态机和错误码速查。
7. 固定验收样例与证据清单。
8. 本地运行和测试命令。
9. 已知风险和后续真实联调步骤。

## 14. Acceptance

曹乐独立完成的验收标准：

- V2 B站导入 contract、错误码和交接文档完成。
- 后端可创建 QR session、查询登录态、预览资源、创建导入任务、查询任务、取消任务。
- 小型下载器具备真实 B站 API/下载/ffmpeg 的实现边界，并用 fake 依赖覆盖单元测试。
- 导入 runner 能在测试环境完成 `imported` 并创建课程资源。
- 单视频、多 P、合集、番剧至少在 contract 和 fake preview 中有样例覆盖。
- 课程库/推荐/多课程语义完成文档冻结和最小接口增强。
- 复杂版面增强验收标准写入交接文档。

小组联调依赖，不作为曹乐独立完成阻塞：

- Flutter 扫码、预览、进度、失败、取消页面。
- Android 模拟器/真机录屏。
- 杨彩艺整理辅助接口文档、状态返回样例和联调记录。
- 真实用户路径的视频播放、页面体验和截图材料。

## 15. Risks

- B站接口、风控、登录态和播放地址规则可能变化。
- 真实账号权限、地区、会员状态会影响样例可访问性。
- ffmpeg 环境缺失会阻塞真实合并。
- 大文件下载和对象存储上传会让端到端测试慢且不稳定。
- 凭据加密存储需要生产前单独收口；阶段一先明确不得提交真实 cookie。

这些风险通过 adapter 边界、fake 测试、可选集成测试和交接文档缓解。
