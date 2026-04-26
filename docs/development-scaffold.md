# KnowLink 组员开工骨架说明

本文件描述当前仓库已经稳定下来的边界，目的是让前端、后端、解析/AIGC 三条线可以直接开工，而不需要先重新讨论目录、字段和依赖方向。

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
| 领域 service + 仓储协议 + 内存态 demo | 已落地 | `server/domain/services/*.py`、`server/domain/repositories/interfaces.py`、`server/infra/repositories/memory.py`、`memory_runtime.py` |
| 推荐、创建课程、上传、解析、问询、讲义、QA、测验、复习接口 | scaffold 已覆盖 | `server/tests/test_api.py` 与 `server/tests/test_scaffold_consistency.py` 覆盖主链路 smoke、幂等和展示字段 |
| AI / parse contract 与引用约束 | 已落地 | `schemas/ai/*.schema.json`、`schemas/parse/normalized_document.schema.json`，并由 `server/tests/test_contract_freeze.py` 覆盖 |
| B 站预留接口 | 已实现 `501` stub | `server/api/routers/bilibili.py`、`server/domain/services/bilibili.py`，并由 `test_api.py`、`test_contract_freeze.py` 校验 |
| Flutter 路由、页面、provider 骨架 | scaffold 已覆盖 | `client_flutter/lib/app/`、`client_flutter/lib/features/`、`client_flutter/lib/shared/providers/` 已就位 |
| Flutter 自动化测试 | 已覆盖启动 smoke + course flow provider 语义 | `client_flutter/test/smoke_test.dart` 与 `client_flutter/test/shared/course_flow_providers_test.dart` |
| 基础四表 SQLAlchemy model 与 Alembic 初始化迁移 | 已接纳 | `courses`、`course_resources`、`parse_runs`、`async_tasks` 四表已在 `server/infra/db/models/` 与 `alembic/versions/1b319cfadeb3_init_tables.py` 覆盖 |
| `async_tasks` 任务骨架 | Week 1 scaffold 已完成 | 已有表模型、任务 payload、worker / scheduler 占位和内存态异步返回结构；真实状态流转进入 Week 2 |
| PostgreSQL / Redis / MinIO / Worker 真实运行时 | Week 1 scaffold 已完成，真实接入进入 Week 2 | 数据库 model 与初始迁移已接纳；完整 SQLAlchemy 持久化仓储、Redis、MinIO、Dramatiq Worker 仍未接通 |

## 5. 当前未接通的部分

- 以下内容不作为 Week 1 验收缺口，统一进入 Week 2 起的真实接入范围。
- 完整 SQLAlchemy 持久化仓储仍未接通，当前 service/repository 仍使用内存态 demo 适配器
- 基础四表之外的业务表尚未落库，包括解析产物、讲义、QA、测验、掌握度和复习任务相关表
- Redis / MinIO 真实读写
- Dramatiq broker 和真实 worker 消费
- `async_tasks` 真实状态流转与子任务消费
- OCR / ASR / LLM provider 接入
- Flutter 页面真实数据接线和交互打磨

## 6. Schema / Contract 变更流

1. 先判断变更属于哪一层：业务语义/状态枚举走 `ARCHITECTURE.md`，请求响应与错误码走 `docs/contracts/api-contract.md` / `docs/contracts/error-codes.md`，曹乐第 1 周冻结清单与 demo 基线参考 `docs/contracts/week1-cao-le-freeze.md`，代码结构与当前完成度走本文件。
2. 先改 authoritative 文档，再改代码或 schema：不要反过来让实现“倒逼” contract。
3. 涉及 `schemas/**` 或 `server/schemas/**` 时，同步更新对应的示例、枚举或字段约束，不只改单个文件。
4. 改完 contract 后，同步更新直接验证它的测试：优先检查 `server/tests/test_contract_freeze.py`、`server/tests/test_scaffold_consistency.py`、`server/tests/test_api.py`，必要时同步更新 Flutter smoke 或 provider 语义测试。
5. 只有在 owner、排期或文档入口本身发生变化时，才继续改 `TEAM_DIVISION.md`、`WEEKLY_PLAN.md`、`README.md`；不要把实现细节扩散到所有文档。

## 7. 开发约束

- 新增后端业务逻辑时，不要在 router 里直接访问仓储或 demo store。
- 新增字段时，先改 contract 和 DTO，再改前后端实现。
- 新增任务时，先在 `server/tasks/payloads.py` 冻结 payload 结构。
- 若需要替换内存仓储，优先复用 `server/domain/repositories/interfaces.py` 中的协议，不直接改 service 调用方式。

## 8. 文档优先级矩阵

| 主题 | 优先文档 | 说明 |
|---|---|---|
| 当前仓库是否真的已经落地 | 代码与测试，其次看本文件 | `server/**`、`client_flutter/**`、`server/tests/**`、`client_flutter/test/**` 是当前现实；本文件负责把这些现实总结成矩阵 |
| 模块边界、目录树、状态全集 | `ARCHITECTURE.md` | 负责定义系统边界与冻结的目标结构 |
| 请求/响应字段、示例 payload、错误码 | `docs/contracts/api-contract.md`、`docs/contracts/error-codes.md` | 这是接口 contract 的直接依据 |
| 曹乐负责冻结的业务语义、枚举和 AI / parse contract | `docs/contracts/week1-cao-le-freeze.md` | 只负责业务语义冻结，不代表 `router/service` 实现 owner |
| 第三方 AI 能力研究、vivo 比赛文档快照与实现注意事项 | `docs/vivo-ai-integration-research.md` | 这是第三方能力研究入口，不替代仓库自身 contract |
| 人员主负责人定义 | `TEAM_DIVISION.md` | `WEEKLY_PLAN.md` 只描述时间与交付节奏，不改 owner |
| 周次目标和演示节奏 | `WEEKLY_PLAN.md` | 它是排期文档，不是“当前已经实现”的证明 |
| 仓库入口与阅读顺序 | `README.md` | 负责把人导向上面这些文档，不重复定义细节 |
