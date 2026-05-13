# KnowLink

KnowLink 是一个面向移动端的 AI 学习闭环产品：用户导入课程与资料，系统完成预解析、个性化问询、互动讲义、块级问答、测验和复习推荐。

当前仓库同时维护：

- 工程规格文档
- 可分工开发的后端骨架（FastAPI，router -> service -> repository）
- 可分工开发的 Flutter 客户端骨架（页面、路由、course-flow 状态）
- 接口 contract、AI schema 和开发环境脚手架

第二版功能规划、负责人分工、每周任务和验收口径以 [docs/v2/phase-plan.md](./docs/v2/phase-plan.md) 为准。完整文档地图见 [docs/README.md](./docs/README.md)。

## 最短阅读路径

- [文档导航](./docs/README.md)：所有文档的分层入口。
- [第二版阶段计划与负责人分工](./docs/v2/phase-plan.md)：当前 V2 执行入口。
- [工程骨架与当前完成度](./docs/engineering/development-scaffold.md)：当前代码和运行时状态。
- [API Contract 冻结稿](./docs/contracts/api-contract.md)：接口、DTO、异步返回结构和 V2 contract 过渡口径。
- [第一版系统架构](./docs/v1/architecture.md)：V1 历史架构与主链路设计。
- [第一版团队分工](./docs/v1/team-division.md)：V1 owner 边界；V2 以阶段计划为准。
- [提交规范](./CONTRIBUTING.md)：提交 message 与 scope 规则。

## 文档优先级矩阵

| 文档 | 优先级 | 负责回答的问题 |
|---|---|---|
| [docs/v2/phase-plan.md](./docs/v2/phase-plan.md) | P0 | 第二版阶段计划、每周任务、负责人分工和验收口径 |
| [docs/contracts/api-contract.md](./docs/contracts/api-contract.md) | P0 | 接口路径、请求字段、响应字段、DTO 和错误码 |
| [docs/v1/architecture.md](./docs/v1/architecture.md) | P0 | 第一版领域语义、状态模型、目录边界、主链路设计 |
| [docs/v1/team-division.md](./docs/v1/team-division.md) | P1 | 第一版 owner、协作边界与单 owner 口径；V2 以 `docs/v2/phase-plan.md` 为准 |
| [docs/contracts/week1-cao-le-freeze.md](./docs/contracts/week1-cao-le-freeze.md) | P1 | 曹乐冻结的业务语义、状态语义、推荐规则与 demo 基线 |
| [docs/engineering/development-scaffold.md](./docs/engineering/development-scaffold.md) | P1 | 当前骨架完成度、schema/contract 变更流、文档优先级 |
| [docs/research/vivo-ai-integration.md](./docs/research/vivo-ai-integration.md) | P2 | vivo 比赛 AI 文档的第三方接入研究、快照索引与实现注意事项 |
| [docs/v1/weekly-plan.md](./docs/v1/weekly-plan.md) | P2 | 第一版周排期、阶段目标和每周交付物 |

## 工程骨架

- `server/`: FastAPI 骨架、服务层、仓储协议、内存 demo 适配器、任务 payload 和解析/AI 占位模块
- `client_flutter/`: Flutter 页面与路由骨架、course-flow 状态、独立 QA 页面入口
- `schemas/`: AI 输出 schema 和解析输出 schema
- `server/seeds/`: 固定课程目录、demo 数据和资料清单 manifest
- `.github/workflows/`: 最小 CI

## 当前状态

- 资料类型承诺已统一为 `MP4 + PDF + PPTX + DOCX`，`SRT` 作为可选辅助输入。
- 当前首版联调资料的本地副本约定放在 `local_assets/`，仓库只跟踪文档与 manifest，不跟踪二进制文件。
- 截至 2026-05-12，KnowLink 第一版 MVP 已完成，固定主链路已跑通：`上传 -> 解析 -> 问询 -> 讲义 -> QA -> 测验 -> 复习`。
- 已就位：接口 DTO、路由、服务层、仓储协议、SQLAlchemy 运行时仓储、异步任务、Flutter 路由、页面和主链路 Provider。
- Week 1 推荐页本地联调已跑通：基于 demo token、内存态 demo 仓储和 `server/seeds/course_catalog.json`，可完成“获取推荐 -> 确认入课 -> 前往自主导入页”。
- Week 2 固定资料集本地真实联调已跑通：`1 MP4 + 1 PDF + 1 PPTX + 1 DOCX` 可完成创建课程、上传、MinIO 真实写入、解析任务、`pipeline-status` 轮询并进入问询入口。
- 2026-05-03 验收记录：`course_resources` 已写入 4 条 `ready / passed / succeeded` 记录；MinIO bucket `knowlink` 下 4 个对象的 size 与 checksum metadata 匹配；`parse_runs` 为 `succeeded`、`progress_pct=100`；`async_tasks` 中 `parse_pipeline`、资源校验、字幕提取、文档解析、目录抽取和向量化均为 `succeeded`；`course_segments=178`，`vector_documents=178`。
- Week 3 讲义与 QA 链路已完成：问询后可生成讲义目录，讲义块可按需生成，引用可跳转到视频时间戳或文档位置，当前块 QA 可返回结构化 citations。
- Week 4 测验、掌握度、复习与首页聚合链路已完成：测验可生成、作答、判分并更新掌握度，复习页可展示 Top3 任务，首页可展示最近学习与复习任务。
- 进度说明：第 2、3、4 周中 `docs/v1/team-division.md` 归杨彩艺 owner 的后端运行时、接口、DB、worker 与联调类任务，首版收口阶段均由曹乐代为完成；该说明只记录第一版实际执行过程，不改变 V1 owner 边界。V2 后端分工以 `docs/v2/phase-plan.md` 为准。
- 当前本地运行时已接通 PostgreSQL、Redis、MinIO、Dramatiq worker 和 scheduler；FastAPI 默认允许本地 Flutter Web origin，MinIO 本地默认使用全局 `MINIO_API_CORS_ALLOW_ORIGIN=*`，生产环境可通过 `KNOWLINK_CORS_ALLOW_ORIGINS` 和 `KNOWLINK_MINIO_CORS_ALLOW_ORIGIN` 收紧。
- 当前仓库按 Flutter APP 交付组织；策划书中的“快应用”不在本仓实现范围。
