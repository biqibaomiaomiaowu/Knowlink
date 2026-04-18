# KnowLink 组员开工骨架说明

本文件描述当前仓库已经稳定下来的边界，目的是让前端、后端、解析/AIGC 三条线可以直接开工，而不需要先重新讨论目录、字段和依赖方向。

## 1. 当前可依赖的边界

- 后端依赖方向固定为 `router -> service -> repository/pipeline protocol`。
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

## 4. 当前未接通的部分

- PostgreSQL / Redis / MinIO 真实读写
- SQLAlchemy model 与 Alembic 落表
- Dramatiq broker 和真实 worker 消费
- OCR / ASR / LLM provider 接入
- Flutter 页面真实数据接线和交互打磨

## 5. 开发约束

- 新增后端业务逻辑时，不要在 router 里直接访问仓储或 demo store。
- 新增字段时，先改 contract 和 DTO，再改前后端实现。
- 新增任务时，先在 `server/tasks/payloads.py` 冻结 payload 结构。
- 若需要替换内存仓储，优先复用 `server/domain/repositories/interfaces.py` 中的协议，不直接改 service 调用方式。
