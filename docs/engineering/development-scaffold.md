# KnowLink 组员开工骨架说明

本文件描述第一版仓库已经稳定下来的工程边界，目的是让前端、后端、解析/AIGC 三条线可以直接开工，而不需要先重新讨论目录、字段和依赖方向。第二版功能规划、负责人分工、每周任务和验收口径以根目录 [docs/v2/phase-plan.md](../v2/phase-plan.md) 为准。

## 1. 当前可依赖的边界

- 后端依赖方向固定为 `router -> service -> repository`。
- 当前 `server/infra/repositories/memory.py` 只是 demo 适配器，后续可以替换成数据库实现，但 router 不应再直接引用它。
- DTO 固定在 `server/schemas/common.py`、`server/schemas/requests.py`、`server/schemas/responses.py`。
- 客户端路由固定为 `/`、`/import`、`/recommend`、`/courses/:courseId/progress`、`/courses/:courseId/inquiry`、`/courses/:courseId/handout`、`/courses/:courseId/qa/:sessionId`、`/quizzes/:quizId`、`/courses/:courseId/review`。
- 当前仓库按 Flutter APP 交付组织，不承接快应用工程。

## 2. 各条线入口

- 移动端：
  入口在 `client_flutter/lib/features/`，共享状态在 `client_flutter/lib/shared/providers/course_flow_providers.dart`。
- 后端：
  入口在 `server/api/routers/` 和 `server/domain/services/`，需要新增能力时先补 service，再决定是否加 repository protocol。
- 解析/AIGC：
  占位入口在 `server/parsers/`、`server/ai/pipelines/`、`server/tasks/payloads.py`。

## 3. 当前冻结的输入与引用语义

- 资料类型：`mp4`、`pdf`、`pptx`、`docx` 为 MVP 范围，`srt` 为可选辅助输入。
- 引用字段：
  - `pdf` 使用 `pageNo`
  - `pptx` 使用 `slideNo`
  - `docx` 使用 `anchorKey`
  - 视频定位使用 `startSec/endSec`
- 不为 `docx` 伪造页码，不把引用语义混写到单一字符串里。

## 4. 当前完成度矩阵

| 范围 | 当前仓库状态 | 依据 |
|---|---|---|
| FastAPI app / router 骨架 | 已落地 | `server/app.py`、`server/api/app_factory.py`、`server/api/router.py` 与 `server/api/routers/*.py` 已存在 |
| 领域 service + 仓储协议 + 运行时仓储 | 已落地 | `server/domain/services/*.py`、`server/domain/repositories/interfaces.py`、`server/infra/repositories/sqlalchemy.py`；内存态 demo 适配器仍保留为 scaffold / 测试路径 |
| 推荐、创建课程、上传、解析、问询、讲义、QA、测验、复习接口 | 第一版主链路已覆盖 | `server/tests/test_api.py`、`server/tests/test_scaffold_consistency.py` 与 runtime wiring 测试覆盖主链路 smoke、幂等和展示字段 |
| AI / parse contract 与引用约束 | 已落地 | `schemas/ai/*.schema.json`、`schemas/parse/normalized_document.schema.json`，并由 `server/tests/test_contract_freeze.py` 覆盖 |
| B 站预留接口 | 第一版已实现 `501` stub；第二版将按 `docs/v2/phase-plan.md` 接通真实登录、下载、导入 | `server/api/routers/bilibili.py`、`server/domain/services/bilibili.py`，并由 `test_api.py`、`test_contract_freeze.py` 校验 |
| Flutter 路由、页面、provider | 第一版主链路已承接 | `client_flutter/lib/app/`、`client_flutter/lib/features/`、`client_flutter/lib/shared/providers/` 已就位 |
| Flutter 自动化测试 | 已覆盖启动 smoke、course flow provider 和 Week 4 页面 / provider 语义 | `client_flutter/test/` 下 smoke、provider、quiz、review、home 等测试 |
| SQLAlchemy model 与 Alembic 迁移 | 第一版业务表已覆盖 | 课程、资源、解析、讲义、QA、测验、掌握度、复习和学习进度相关 model / migration 已进入运行时 |
| `async_tasks` 与 worker | 第一版异步运行时已接通 | parse、handout、quiz、review 等任务通过 task payload、Dramatiq worker 和 dispatcher 接线 |
| PostgreSQL / Redis / MinIO / Worker 真实运行时 | 第一版已接通 | 本地运行时已覆盖 SQLAlchemy 持久化仓储、MinIO 上传 / 读取、Redis / Dramatiq worker、scheduler 与聚合 read model |

FastAPI 当前默认允许本地 Flutter Web origin；MinIO 本地默认使用全局 `MINIO_API_CORS_ALLOW_ORIGIN=*`，生产环境可通过 `KNOWLINK_CORS_ALLOW_ORIGINS` 和 `KNOWLINK_MINIO_CORS_ALLOW_ORIGIN` 显式收紧。

## 5. 首版完成说明

- 截至 2026-05-12，KnowLink 第一版 MVP 已完成，固定主链路为 `上传 -> 解析 -> 问询 -> 讲义 -> QA -> 测验 -> 复习`。
- 第 2、3、4 周中 `docs/v1/team-division.md` 归杨彩艺 owner 的后端运行时、接口、DB、worker 与联调类任务，首版收口阶段由曹乐代为完成；该说明只记录第一版实际执行过程，不改变 V1 owner 边界。V2 后端分工以 `docs/v2/phase-plan.md` 为准。
- 内存态 demo 适配器仍保留，用于 scaffold、轻量测试和无外部依赖演示；真实联调与首版完成口径以 SQLAlchemy 运行时仓储、MinIO、Redis / Dramatiq 和聚合 read model 为准。
- 首版之后的工作不再是补齐主链路，而是围绕稳定性、真机展示、失败恢复、数据质量和非 MVP 功能继续增强。

## 6. Schema / Contract 变更流

1. 先判断变更属于 V1 还是 V2。V1 业务语义/状态枚举走 `docs/v1/architecture.md`，请求响应与错误码走 `docs/contracts/api-contract.md` / `docs/contracts/error-codes.md`，曹乐第 1 周冻结清单与 demo 基线参考 `docs/contracts/week1-cao-le-freeze.md`，代码结构与当前完成度走本文件。V2 功能范围、负责人分工和验收口径先走 `docs/v2/phase-plan.md`，再同步补充对应 contract/schema。
2. 先改 authoritative 文档，再改代码或 schema：不要反过来让实现“倒逼” contract。
3. 涉及 `schemas/**` 或 `server/schemas/**` 时，同步更新对应的示例、枚举或字段约束，不只改单个文件。
4. 改完 contract 后，同步更新直接验证它的测试：优先检查 `server/tests/test_contract_freeze.py`、`server/tests/test_scaffold_consistency.py`、`server/tests/test_api.py`，必要时同步更新 Flutter smoke 或 provider 语义测试。
5. 只有在 owner、排期或文档入口本身发生变化时，才继续改 `docs/v1/team-division.md`、`docs/v1/weekly-plan.md`、`README.md`；不要把实现细节扩散到所有文档。

## 7. 开发约束

- 新增后端业务逻辑时，不要在 router 里直接访问仓储或 demo store。
- 新增字段时，先改 contract 和 DTO，再改前后端实现。
- 新增任务时，先在 `server/tasks/payloads.py` 冻结 payload 结构。
- 若需要替换内存仓储，优先复用 `server/domain/repositories/interfaces.py` 中的协议，不直接改 service 调用方式。

## 8. 文档优先级矩阵

| 主题 | 优先文档 | 说明 |
|---|---|---|
| 第二版阶段计划、负责人分工和验收口径 | `docs/v2/phase-plan.md` | V2 中若与 V1 owner 或旧 MVP contract 口径冲突，先以该文件收敛范围，再更新对应 contract |
| 当前仓库是否真的已经落地 | 代码与测试，其次看本文件 | `server/**`、`client_flutter/**`、`server/tests/**`、`client_flutter/test/**` 是当前现实；本文件负责把这些现实总结成矩阵 |
| 第一版模块边界、目录树、状态全集 | `docs/v1/architecture.md` | 负责定义 V1 系统边界与冻结的目标结构 |
| 第一版请求/响应字段、示例 payload、错误码 | `docs/contracts/api-contract.md`、`docs/contracts/error-codes.md` | 这是 V1/MVP 接口 contract 的直接依据；V2 新增能力需补充 V2 contract |
| 曹乐负责冻结的第一版业务语义、枚举和 AI / parse contract | `docs/contracts/week1-cao-le-freeze.md` | 只负责 V1 业务语义冻结，不代表 `router/service` 实现 owner |
| 第三方 AI 能力研究、vivo 比赛文档快照与实现注意事项 | `docs/research/vivo-ai-integration.md` | 这是第三方能力研究入口，不替代仓库自身 contract |
| 第一版人员主负责人定义 | `docs/v1/team-division.md` | `docs/v1/weekly-plan.md` 只描述 V1 时间与交付节奏，不改 V1 owner；V2 owner 以 `docs/v2/phase-plan.md` 为准 |
| 第一版周次目标和演示节奏 | `docs/v1/weekly-plan.md` | 它是 V1 排期文档，不是“当前已经实现”的证明 |
| 仓库入口与阅读顺序 | `README.md` | 负责把人导向上面这些文档，不重复定义细节 |
