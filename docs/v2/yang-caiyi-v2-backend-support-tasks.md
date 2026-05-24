# 杨彩艺 V2 后端辅助与联调任务清单

本文基于以下范围整理：`docs/contracts/api-contract.md`、`docs/contracts/week1-cao-le-freeze.md`、`docs/engineering/development-scaffold.md` 和 `server` 目录结构。

原则：杨彩艺只接边界清楚、低风险、可独立完成的后端辅助、DTO、查询接口、接口文档、测试数据和联调记录任务；不实现 B站下载、ffmpeg、AI、图谱生成、SSE 核心协议、主观题判卷策略等复杂逻辑。

## 任务清单

| 编号 | 任务 | 状态 | 产出 | 对应文件位置 | 备注 |
|---|---|---|---|---|---|
| 1 | 整理 V1 已冻结接口总表 | 已完成 | 接口路径、方法、请求/响应摘要表 | `docs/v2/yang-caiyi-v1-frozen-api-overview.md` | 只摘录已有 contract，不新增字段 |
| 2 | 整理核心状态枚举说明 | 已完成 | `lifecycleStatus`、`pipelineStage`、`pipelineStatus`、`async_tasks.status` 对照表 | `docs/v2/yang-caiyi-core-status-enums.md` | 可用于前端联调和验收记录 |
| 3 | 整理推荐接口 DTO 文档 | 已完成 | 推荐请求、推荐响应、推荐理由固定文案、排序规则 | `docs/v2/yang-caiyi-recommendation-dto.md` | 不修改推荐算法 |
| 4 | 整理课程创建和最近课程 DTO 文档 | 已完成 | `POST /courses`、`GET /courses/recent` 字段表 | `docs/v2/yang-caiyi-course-api-dto.md` | 不新增多课程增强字段 |
| 5 | 整理首页 dashboard DTO 文档 | 已完成 | 首页聚合返回字段说明 | `docs/v2/yang-caiyi-home-dashboard-dto.md` | 只描述已有字段 |
| 6 | 整理资源上传和资源列表 DTO 文档 | 已完成 | 上传初始化、上传完成、资源列表字段表 | `docs/v2/yang-caiyi-resource-api-dto.md` | 注意 MinIO public endpoint 说明 |
| 7 | 整理播放地址接口联调说明 | 已完成 | `playbackUrl`、`mimeType`、`expiresAt`、`durationSec` 说明和 Android 可达性注意事项 | `docs/v2/yang-caiyi-playback-url-integration.md` | 不改对象存储核心实现 |
| 8 | 整理 B站 V1 预留接口清单 | 已完成 | B站预留路径、当前 `501 bilibili.not_implemented` 行为说明 | `docs/v2/yang-caiyi-bilibili-import-dto.md` | 已升级吸收到 V2 B站导入 DTO |
| 9 | 整理 B站 V2 待冻结 contract 清单 | 已完成 | 曹乐冻结后整理为 V2 B站导入 DTO | `docs/v2/yang-caiyi-bilibili-import-dto.md` | 不实现扫码、预览、下载、取消副作用 |
| 10 | 整理 B站导入状态到 `async_tasks.status` 的已有映射 | 已完成 | 状态映射表和联调说明 | `docs/v2/yang-caiyi-bilibili-import-dto.md` | 只使用 contract 已给出的映射 |
| 11 | 编写 B站辅助查询接口联调记录模板 | 已完成 | 任务列表、状态查询、取消入口的记录模板 | `docs/v2/yang-caiyi-bilibili-import-integration-template.md` | 取消副作用不归杨彩艺 |
| 12 | 整理解析任务接口 DTO 文档 | 已完成 | `parse/start`、`parse-runs`、`pipeline-status`、`parse/summary` 字段表 | `docs/v2/yang-caiyi-parse-task-dto.md` | 不改解析策略 |
| 13 | 整理异步任务 retry 接口文档 | 已完成 | retry 适用状态、错误码、返回字段说明 | `docs/v2/yang-caiyi-async-task-retry-dto.md` | 不改 dispatcher / broker |
| 14 | 整理问询接口 DTO 文档 | 已完成 | 问题列表、答案提交字段表 | `docs/v2/yang-caiyi-inquiry-api-dto.md` | 不改问询生成逻辑 |
| 15 | 整理讲义查询接口 DTO 文档 | 已完成 | latest、outline、blocks、block status、current-block、jump-target 字段表 | `docs/v2/yang-caiyi-handout-api-dto.md` | 不改讲义生成逻辑 |
| 16 | 整理 QA 接口 DTO 文档 | 已完成 | QA 请求、消息查询、citation 字段说明 | `docs/v2/yang-caiyi-qa-api-dto.md` | 不改 AI 回答策略 |
| 17 | 整理测验接口 DTO 文档 | 已完成 | 客观题生成、查询、提交、得分返回字段 | `docs/v2/yang-caiyi-quiz-api-dto.md` | 不扩写主观题字段 |
| 18 | 整理复习接口 DTO 文档 | 已完成 | review tasks、regenerate、run status、complete 字段 | `docs/v2/yang-caiyi-review-api-dto.md` | 不改推荐复习算法 |
| 19 | 整理最近学习位置 DTO 文档 | 已完成 | progress 读取和保存字段表 | `docs/v2/yang-caiyi-progress-api-dto.md` | 只说明已有字段 |
| 20 | 整理课程 seed 测试数据说明 | 已完成 | 推荐演示课程、固定标题、默认资源清单说明 | `docs/v2/yang-caiyi-course-seed-data.md` | 不改推荐规则 |
| 21 | 整理固定联调资料 manifest 说明 | 已完成 | `1 mp4 + 1 pdf + 1 pptx + 1 docx` 资料说明 | `docs/v2/yang-caiyi-demo-assets-manifest.md` | 不提交二进制资料 |
| 22 | 整理 Android 联调后端地址说明 | 已完成 | 模拟器、真机、Wi-Fi、MinIO public endpoint 注意事项 | `docs/v2/yang-caiyi-android-backend-connectivity.md` | 可作为联调 checklist |
| 23 | 整理 server 分层入口说明 | 已完成 | router -> service -> repository 文件映射表 | `docs/v2/yang-caiyi-server-layer-map.md` | 不改架构 |
| 24 | 补充简单查询接口的字段对齐记录 | 已完成 | 字段对齐表、联调结论、待确认项 | `docs/v2/yang-caiyi-query-field-alignment.md` | 只有字段已冻结时才可进入实现 |
| 25 | 新增或修改 DTO | 需曹乐先冻结 | DTO 字段变更清单 | `server/schemas/common.py`、`server/schemas/requests.py`、`server/schemas/responses.py` | 必须先有 authoritative contract |
| 26 | 补简单查询包装接口 | 需曹乐先冻结 | 只读查询或状态透传接口 | `server/api/routers/`、`server/domain/services/`、`server/domain/repositories/interfaces.py`、`server/infra/repositories/sqlalchemy.py` | 不包含复杂状态机 |
| 27 | 补 contract freeze / API smoke 测试 | 需曹乐先冻结 | 字段和状态枚举测试 | `server/tests/test_contract_freeze.py`、`server/tests/test_api.py`、`server/tests/test_scaffold_consistency.py` | 只验证已冻结 contract |
| 28 | V2 知识图谱 contract 待办清单 | 需曹乐先冻结 | 待冻结项列表，不定义字段 | `docs/contracts/api-contract.md`、`server/ai/v2/graph.py` | 不扩写节点和边字段 |
| 29 | V2 SSE contract 待办清单 | 需曹乐先冻结 | 待冻结项列表，不定义事件协议 | `docs/contracts/api-contract.md`、`server/ai/v2/streaming.py`、`server/domain/services/async_tasks.py` | 不设计 SSE 核心协议 |
| 30 | V2 主观题判卷 contract 待办清单 | 需曹乐先冻结 | 待冻结项列表，不定义评分字段 | `docs/contracts/api-contract.md`、`server/ai/v2/grading.py`、`server/api/routers/quizzes.py` | 不扩写主观题判卷字段 |
| 31 | 实现 B站扫码登录、凭据保存、BiliClient | 不接 | 无 | `server/api/routers/bilibili.py`、`server/domain/services/bilibili.py` | 困难后端，需曹乐负责 |
| 32 | 实现 B站下载、ffmpeg 合并、上传链路 | 不接 | 无 | `server/domain/services/bilibili.py`、`server/tasks/`、`server/infra/storage/object_store.py` | 涉及下载合并和资源副作用 |
| 33 | 实现 B站取消状态机和失败恢复 | 不接 | 无 | `server/domain/services/bilibili.py`、`server/domain/services/async_tasks.py` | 涉及复杂任务状态机 |
| 34 | 实现知识图谱生成和图谱语义 | 不接 | 无 | `server/ai/v2/graph.py` | AI / 图谱核心 |
| 35 | 实现 SSE 核心事件协议和断线恢复 | 不接 | 无 | `server/ai/v2/streaming.py`、`server/domain/services/async_tasks.py` | 流式核心协议 |
| 36 | 实现主观题 AI 判卷策略 | 不接 | 无 | `server/ai/v2/grading.py`、`server/ai/pipelines/quiz.py` | 判卷策略、rubric、置信度、人审兜底 |

## 本周阶段一重点任务完成情况

| 优先级 | 任务 | 完成情况 | 对应文件位置 |
|---|---|---|---|
| 1 | 基础课程列表、课程详情、课程切换 DTO 文档 | 已完成 | `docs/v2/yang-caiyi-course-api-dto.md` |
| 2 | 课程库 seed、测试课程数据和基础查询样例 | 已完成 | `docs/v2/yang-caiyi-course-seed-data.md` |
| 3 | B站导入状态查询、任务列表、取消入口字段整理 | 已完成 | `docs/v2/yang-caiyi-bilibili-import-dto.md` |
| 4 | B站导入联调记录模板 | 已完成 | `docs/v2/yang-caiyi-bilibili-import-integration-template.md` |
| 5 | Android 联调后端地址、URL 可达性和测试数据说明 | 已完成 | `docs/v2/yang-caiyi-android-backend-connectivity.md` |

## 仍依赖联调现场补充的验收证据

| 验收证据 | 负责人边界 | 当前状态 |
|---|---|---|
| Android 截图或录屏 | 朱春雯负责提供；杨彩艺可整理记录 | 待前端真机或模拟器联调产出 |
| 固定 B站单视频或多 P 样例 | 曹乐负责样例与核心链路；杨彩艺可记录接口返回 | 待真实样例联调产出 |
| 导入状态接口返回 | 曹乐提供真实接口能力；杨彩艺负责记录样例 | 模板已完成，待真实返回填入 |
| 课程资源展示截图 | 朱春雯负责页面截图；杨彩艺可整理验收材料 | 待前端页面联调产出 |
