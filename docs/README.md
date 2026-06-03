# KnowLink 文档导航

本目录按“当前执行入口”和“历史冻结资料”分层。新成员或新 agent 开始工作时，先看本页，再进入对应版本文档。

## 当前优先级

| 场景 | 先看 | 说明 |
|---|---|---|
| 第二版规划、排期、负责人分工 | [v2/phase-plan.md](./v2/phase-plan.md) | V2 当前权威入口；阶段计划、每周任务、负责人和验收口径以此为准 |
| 第二版功能设计背景 | [v2/three-phase-design.md](./v2/three-phase-design.md) | Superpowers 产出的 V2 设计稿，作为计划的设计背景 |
| 第二版课程 / 节课工作台 | [contracts/v2-course-lesson-workbench-contract.md](./contracts/v2-course-lesson-workbench-contract.md) 与 [v2/phase2-course-lesson-workbench-handoff.md](./v2/phase2-course-lesson-workbench-handoff.md) | V2 Phase 2 课程库、Lesson domain、课程 / 节课资源 scope、工作台、节课详情、分层学习产物、首页继续学习、report / export placeholder 契约与交接 |
| 当前代码落地状态 | [engineering/development-scaffold.md](./engineering/development-scaffold.md) | 第一版已接通范围、V2 当前状态、工程边界、schema/contract 变更流 |
| API、DTO、错误码 | [contracts/api-contract.md](./contracts/api-contract.md) 与 [contracts/error-codes.md](./contracts/error-codes.md) | 当前主要是 V1/MVP contract；V2 新功能实施前需补 V2 contract |
| 第一版架构、分工、排期 | [v1/architecture.md](./v1/architecture.md)、[v1/team-division.md](./v1/team-division.md)、[v1/weekly-plan.md](./v1/weekly-plan.md) | V1 历史冻结资料；V2 owner 不直接沿用旧口径 |

## V2 文档

- [v2/phase-plan.md](./v2/phase-plan.md)：第二版阶段计划与负责人分工。
- [v2/three-phase-design.md](./v2/three-phase-design.md)：第二版三阶段功能设计与技术方案背景。
- [v2/phase1-cao-le-handoff.md](./v2/phase1-cao-le-handoff.md)：曹乐阶段一后端交接说明。
- [v2/phase2-course-lesson-workbench-handoff.md](./v2/phase2-course-lesson-workbench-handoff.md)：第二版阶段二课程 / 节课工作台交接说明。
- 当前 V2 Phase 2 客户端主入口为 `/courses`、`/courses/:courseId`、`/courses/:courseId/lessons/:lessonId`；graph / streaming / subjective grading / report / export 仍按 contract 保持 placeholder，不能当作正式生成能力。

## V1 历史冻结文档

- [v1/architecture.md](./v1/architecture.md)：第一版系统架构、领域语义和主链路设计。
- [v1/team-division.md](./v1/team-division.md)：第一版团队分工与 owner 边界。
- [v1/weekly-plan.md](./v1/weekly-plan.md)：第一版四周开发排期。
- [v1/week4-demo-runbook.md](./v1/week4-demo-runbook.md)：第一版 Week 4 演示脚本与验收清单。
- [v1/demo-assets-baseline.md](./v1/demo-assets-baseline.md)：固定联调资料集规范。
- [v1/demo-assets-first-edition.md](./v1/demo-assets-first-edition.md)：首版资料清单。

## Contract 文档

- [contracts/api-contract.md](./contracts/api-contract.md)：API path、请求/响应字段、异步返回结构和 V2 contract 过渡口径。
- [contracts/error-codes.md](./contracts/error-codes.md)：错误码与失败语义。
- [contracts/v2-bilibili-import-contract.md](./contracts/v2-bilibili-import-contract.md)：V2 阶段一 B站真实导入 API、状态机、错误码和取消语义。
- [contracts/v2-course-lesson-workbench-contract.md](./contracts/v2-course-lesson-workbench-contract.md)：V2 阶段二课程库、节课、工作台、分层资料和分层学习产物 API / DTO / 错误码契约。
- [contracts/week1-cao-le-freeze.md](./contracts/week1-cao-le-freeze.md)：曹乐 Week 1 业务语义冻结稿。
- [contracts/week2-cao-le-parse-inquiry-contract.md](./contracts/week2-cao-le-parse-inquiry-contract.md)：曹乐 Week 2 解析与问询契约。

## 工程与研究

- [engineering/development-scaffold.md](./engineering/development-scaffold.md)：工程状态、当前完成度、变更流和文档优先级。
- [research/vivo-ai-integration.md](./research/vivo-ai-integration.md)：vivo AI 接入研究与第三方能力快照。

## 根目录保留入口

- [../README.md](../README.md)：仓库总览和最短阅读路径。
- [../CONTRIBUTING.md](../CONTRIBUTING.md)：提交规范。
