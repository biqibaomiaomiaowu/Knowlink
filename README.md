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
- [API Contract 冻结稿](./docs/contracts/api-contract.md)
- [错误码与失败语义](./docs/contracts/error-codes.md)
- [组员开工骨架说明](./docs/development-scaffold.md)

## 工程骨架

- `server/`: FastAPI 骨架、服务层、仓储协议、内存 demo 适配器、任务 payload 和解析/AI 占位模块
- `client_flutter/`: Flutter 页面与路由骨架、course-flow 状态、独立 QA 页面入口
- `schemas/`: AI 输出 schema 和解析输出 schema
- `server/seeds/`: 固定课程目录和 demo 数据
- `.github/workflows/`: 最小 CI

## 当前状态

- 资料类型承诺已统一为 `MP4 + PDF + PPTX + DOCX`，`SRT` 作为可选辅助输入。
- 当前仓库是“可开工骨架版”，不是“基础设施已接通版”。
- 已就位：接口 DTO、路由、服务层、仓储协议、内存态 demo、Flutter 路由和主页面骨架。
- 未接通：真实 Postgres/Redis/MinIO、SQLAlchemy 持久化、Dramatiq broker、真实 OCR/解析/AIGC pipeline。
- 当前仓库按 Flutter APP 交付组织；策划书中的“快应用”不在本仓实现范围。
