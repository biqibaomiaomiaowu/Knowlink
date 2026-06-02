# V2 Phase 2 Course-Lesson Workbench Handoff

日期：2026-06-02

本文件用于记录课程 / 节课工作台实现后的交接状态。当前为 Task 1 skeleton；后续任务完成后必须补充实际 API、迁移、测试和验收证据。

## Implemented Scope

- 待 Task 2-9 补充。
- 契约入口：`docs/contracts/v2-course-lesson-workbench-contract.md`。

## Non-goals And Placeholders

- 不做单资料 QA。
- 复杂图谱、生产级流式输出、正式主观题判卷、真实报告和真实导出均为 placeholder。
- 不做多用户、团队课程、权限模型或共享课程。
- 删除课程、节课、资料时不做危险级联物理删除。

## Backend Contract Table

| Area | Contract | Implementation status | Tests |
|---|---|---|---|
| Course library / workbench | `GET /api/v1/courses`, `GET /api/v1/courses/{courseId}/workbench` | Pending | Pending |
| Lessons | lesson CRUD, reorder, primary video, merge, split | Pending | Pending |
| Resource scope | `scopeType`, `lessonId`, `usageRole` | Pending | Pending |
| Scoped artifacts | handout, QA, quiz, review, graph, report, export | Pending | Pending |
| Home / progress | continue into lesson, lesson progress | Pending | Pending |

## Flutter Contract Table

| Area | Route | Implementation status | Tests |
|---|---|---|---|
| Course library | `/courses` | Pending | Pending |
| Course workbench | `/courses/:courseId` | Pending | Pending |
| Lesson detail | `/courses/:courseId/lessons/:lessonId` | Pending | Pending |
| Course QA | `/courses/:courseId/qa` | Pending | Pending |
| Lesson QA | `/courses/:courseId/lessons/:lessonId/qa` | Pending | Pending |
| Placeholder pages | graph / review / exports / handout | Pending | Pending |

## Migration And Rollback Notes

- 新表和新增 nullable scope 字段应可独立回滚。
- 旧 course-centric rows 迁移为 `scopeType=course`、`lessonId=null`。
- 不删除旧列，不破坏 V1 course-level 路由。
- 若 B站 auto lesson binding 不稳定，可先保留资源 course scope，并通过修复脚本或 service 方法后补 lesson 绑定。

## Fixed Demo Data And Acceptance Evidence

后续实现完成后补充：

- 固定课程和 lesson seed。
- MP4 自动创建 lesson 的接口记录。
- PDF / PPTX / DOCX / SRT course scope 与 lesson scope 样例。
- Course workbench 响应样例。
- Lesson detail 响应样例。
- Course QA 与 lesson QA 独立入口截图或测试证据。
- 无单资料 QA 入口的检查证据。
- 后端 pytest 命令和结果。
- Flutter test 命令和结果。

## Known Risks

- V1 数据是 course-centric，多表增加 scope 需要保守迁移和兼容默认值。
- 课程 / 节课删除会影响引用链，第一轮必须优先 blocker 预览和软删除。
- B站导入重试需要幂等记录 `sourcePartId` 与 `lessonId`，否则可能重复创建 lesson。
- Flutter 与后端并行时必须以冻结 DTO 为准，避免页面层拼接低级接口。
- 当前本地 Flutter 验证依赖 Windows SDK；若 WSL wrapper 或 Windows Dart compiler 崩溃，需要在最终交接中记录环境证据。

