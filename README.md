# KnowLink

KnowLink 是一个面向移动端的 AI 学习闭环产品：用户导入课程与资料，系统完成预解析、个性化问询、互动讲义、块级问答、测验和复习推荐。

当前仓库同时维护：

- 工程规格文档
- 可分工开发的后端骨架（FastAPI，router -> service -> repository）
- 可分工开发的 Flutter 客户端骨架（页面、路由、course-flow 状态）
- 接口 contract、AI schema 和开发环境脚手架

研发开工以 [ARCHITECTURE.md](./ARCHITECTURE.md) 为准，接口与 DTO 冻结以 [docs/contracts/api-contract.md](./docs/contracts/api-contract.md) 为准。

## 文档

- [系统架构设计（Flutter MVP）](./ARCHITECTURE.md)
- [团队分工与协作方案](./TEAM_DIVISION.md)
- [MVP 4 周开发任务清单](./WEEKLY_PLAN.md)
- [曹乐 Week 1 冻结稿](./docs/contracts/week1-cao-le-freeze.md)
- [API Contract 冻结稿](./docs/contracts/api-contract.md)
- [固定联调资料集规范](./docs/demo-assets-baseline.md)
- [首版资料清单](./docs/demo-assets-first-edition.md)
- [vivo AI 接入研究（第三方能力研究与快照入口）](./docs/vivo-ai-integration-research.md)
- [错误码与失败语义](./docs/contracts/error-codes.md)
- [组员开工骨架说明（含完成度矩阵、变更流、文档优先级）](./docs/development-scaffold.md)
- [提交规范](./CONTRIBUTING.md)

## 文档优先级矩阵

| 文档 | 优先级 | 负责回答的问题 |
|---|---|---|
| [docs/contracts/api-contract.md](./docs/contracts/api-contract.md) | P0 | 接口路径、请求字段、响应字段、DTO 和错误码 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | P0 | 领域语义、状态模型、目录边界、主链路设计 |
| [TEAM_DIVISION.md](./TEAM_DIVISION.md) | P1 | owner、协作边界与单 owner 口径 |
| [docs/contracts/week1-cao-le-freeze.md](./docs/contracts/week1-cao-le-freeze.md) | P1 | 曹乐冻结的业务语义、状态语义、推荐规则与 demo 基线 |
| [docs/development-scaffold.md](./docs/development-scaffold.md) | P1 | 当前骨架完成度、schema/contract 变更流、文档优先级 |
| [docs/vivo-ai-integration-research.md](./docs/vivo-ai-integration-research.md) | P2 | vivo 比赛 AI 文档的第三方接入研究、快照索引与实现注意事项 |
| [WEEKLY_PLAN.md](./WEEKLY_PLAN.md) | P2 | 周排期、阶段目标和每周交付物 |

## 工程骨架

- `server/`: FastAPI 骨架、服务层、仓储协议、内存 demo 适配器、任务 payload 和解析/AI 占位模块
- `client_flutter/`: Flutter 页面与路由骨架、course-flow 状态、独立 QA 页面入口
- `schemas/`: AI 输出 schema 和解析输出 schema
- `server/seeds/`: 固定课程目录、demo 数据和资料清单 manifest
- `.github/workflows/`: 最小 CI

## 当前状态

- 资料类型承诺已统一为 `MP4 + PDF + PPTX + DOCX`，`SRT` 作为可选辅助输入。
- 当前首版联调资料的本地副本约定放在 `local_assets/`，仓库只跟踪文档与 manifest，不跟踪二进制文件。
- 当前仓库已完成 Week 2 上传、解析和问询入口链路的本地真实联调；讲义、QA、测验和复习仍按后续周计划继续接入。
- 已就位：接口 DTO、路由、服务层、仓储协议、SQLAlchemy 运行时仓储、Flutter 路由、页面和 Week 2 Provider 链路。
- Week 1 推荐页本地联调已跑通：基于 demo token、内存态 demo 仓储和 `server/seeds/course_catalog.json`，可完成“获取推荐 -> 确认入课 -> 前往自主导入页”。
- Week 2 固定资料集本地真实联调已跑通：`1 MP4 + 1 PDF + 1 PPTX + 1 DOCX` 可完成创建课程、上传、MinIO 真实写入、解析任务、`pipeline-status` 轮询并进入问询入口。
- 2026-05-03 验收记录：`course_resources` 已写入 4 条 `ready / passed / succeeded` 记录；MinIO bucket `knowlink` 下 4 个对象的 size 与 checksum metadata 匹配；`parse_runs` 为 `succeeded`、`progress_pct=100`；`async_tasks` 中 `parse_pipeline`、资源校验、字幕提取、文档解析、目录抽取和向量化均为 `succeeded`；`course_segments=178`，`vector_documents=178`。
- 当前本地运行时已接通 PostgreSQL、Redis、MinIO、Dramatiq worker 和 scheduler；Flutter Web 本地验收仍使用独立 Chrome 绕过尚未正式配置的 CORS。
- 当前仓库按 Flutter APP 交付组织；策划书中的“快应用”不在本仓实现范围。
