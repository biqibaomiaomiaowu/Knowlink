# V2 Phase 2 Course-Lesson Workbench Handoff

日期：2026-06-02

本文件用于记录课程 / 节课工作台实现后的交接状态。当前已完成 Task 1 契约冻结、Task 2 后端 schema / repository 原语、Task 3 课程库 / 课程管理 / 删除影响 / 课程工作台后端 API、Task 4 lesson API、Task 5 资源 scope / 上传 placement / B站导入自动建 lesson，以及 Task 6 分层学习产物 / placeholder API；后续任务继续补充 Flutter 页面、首页推荐和最终验收证据。

## Implemented Scope

- Task 1：冻结 V2 Phase 2 课程 / 节课工作台契约、错误码和 handoff 骨架。
- Task 2：新增 lesson、user lesson progress、分层资源和分层 artifact 的后端模型、迁移、仓储协议、memory / SQL 仓储实现与测试。
- Task 3：新增完整课程库 `GET /api/v1/courses`、课程 PATCH、归档 / 恢复、删除影响、soft delete 阻塞判断，以及 `GET /api/v1/courses/{courseId}/workbench` 聚合 read model。
- Task 4：新增 lesson CRUD、reorder、primary video、merge、split，以及 lesson detail 聚合 read model。
- Task 5：新增资源上传 scope 校验、本地 MP4 自动建 lesson / 绑定既有 lesson、B站导入 per-video lesson mapping 与重试复用。
- Task 6：新增 course / lesson 讲义、QA、测验、复习、进度、图谱、报告和导出 placeholder API，并保留 V1 course-level 兼容入口。
- 契约入口：`docs/contracts/v2-course-lesson-workbench-contract.md`。

## Non-goals And Placeholders

- 不做单资料 QA。
- 复杂图谱、生产级流式输出、正式主观题判卷、真实报告和真实导出均为 placeholder。
- 不做多用户、团队课程、权限模型或共享课程。
- 删除课程、节课、资料时不做危险级联物理删除。

## Backend Contract Table

| Area | Contract | Implementation status | Tests |
|---|---|---|---|
| Course library / workbench | `GET /api/v1/courses`, `GET /api/v1/courses/{courseId}/workbench` | Done for Task 3 backend API | `server/tests/test_course_workbench_api.py` |
| Lessons | lesson CRUD, reorder, primary video, merge, split | Done for Task 4 backend API | `server/tests/test_lessons_api.py`, `server/tests/test_lesson_repository.py` |
| Resource scope | `scopeType`, `lessonId`, `usageRole`, `lessonPlacement` | Done for Task 5 upload API and B站 import binding | `server/tests/test_resource_scope_import.py` |
| Scoped artifacts | handout, QA, quiz, review, graph, report, export | Done for Task 6 placeholder API | `server/tests/test_scoped_learning_artifacts.py`, `server/tests/test_lesson_repository.py` |
| Home / progress | continue into lesson, lesson progress | Lesson progress API done; home continue-learning pending Task 8 | `server/tests/test_scoped_learning_artifacts.py`, `server/tests/test_lesson_repository.py` |

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
- `mastery_records` 使用 course-scope 与 lesson-scope 两个 partial unique indexes，避免 nullable `lesson_id` 破坏课程级唯一性。
- `user_lesson_progress.last_handout_block_id` 会校验 handout block 归属，不接受未知或跨课程引用。
- Downgrade 会删除旧 V1 schema 无法表达的 QA / quiz scoped placeholder 行，再恢复旧的非空 handout 外键。
- 不删除旧列，不破坏 V1 course-level 路由。
- B站 import run 的 `selection.partLessonMap` 记录 `sourcePartId -> {lessonId, resourceId}`，`bilibili_import_items.lesson_id` 同步保存 item 级 lesson 归属。若 part 上传中途失败，已创建的 lesson 会保留，retry 必须复用该 `lessonId`，不得重复创建 lesson。

## Fixed Demo Data And Acceptance Evidence

后续实现完成后补充：

- 固定课程和 lesson seed。
- MP4 自动创建 lesson 的接口记录。
- PDF / PPTX / DOCX / SRT course scope 与 lesson scope 样例。
- Course workbench 响应样例已由 `server/tests/test_course_workbench_api.py` 固定：course info、progress、lessons、courseResources、quickEntries、placeholderStates。
- Lesson detail 响应样例已由 `server/tests/test_lessons_api.py` 固定：lesson、primaryVideo、lessonResources、artifactSummaries、progress、placeholder 和 nextAction。
- Task 5 资源 / 导入证据：`.venv/bin/python -m pytest -q server/tests/test_resource_scope_import.py server/tests/test_bilibili_service.py server/tests/test_bilibili_import_runner.py` 通过。
- Task 5 upload smoke：`.venv/bin/python -m pytest -q server/tests/test_api.py -k "upload_complete or upload_contract or resource_playback or bilibili_import"` 通过。
- Course QA 与 lesson QA 独立入口测试证据：`server/tests/test_scoped_learning_artifacts.py::test_course_and_lesson_qa_sessions_are_separate_and_lesson_citations_are_scoped`。
- 无单资料 QA 入口检查证据：`server/tests/test_scoped_learning_artifacts.py::test_course_and_lesson_qa_sessions_are_separate_and_lesson_citations_are_scoped` 断言 `/courses/{courseId}/resources/{resourceId}/qa/messages` 返回 404。
- Task 6 分层产物 API 验证命令：`.venv/bin/python -m pytest -q server/tests/test_scoped_learning_artifacts.py server/tests/test_qa_policy.py server/tests/test_quiz_strategy.py server/tests/test_api.py server/tests/test_lesson_repository.py`。
- 后端 pytest 命令和结果：`server/tests/test_lesson_repository.py server/tests/test_contract_freeze.py server/tests/test_scaffold_consistency.py server/tests/test_resource_deletion_semantics.py server/tests/test_sql_runtime_contract.py` 通过。
- Task 3 后端 pytest 命令和结果：`.venv/bin/python -m pytest -q server/tests/test_course_workbench_api.py server/tests/test_api.py` 通过。
- Task 3 repository / migration 回归：`.venv/bin/python -m pytest -q server/tests/test_lesson_repository.py server/tests/test_lesson_migration.py server/tests/test_scaffold_consistency.py server/tests/test_sql_runtime_contract.py` 通过。
- Alembic 临时 SQLite 升降级：`upgrade head -> downgrade c8d9e0f1a2b3 -> upgrade head` 通过。
- Flutter test 命令和结果。

## Known Risks

- V1 数据是 course-centric，多表增加 scope 需要保守迁移和兼容默认值。
- 课程 / 节课删除会影响引用链，第一轮必须优先 blocker 预览和软删除。
- B站导入重试需要幂等记录 `sourcePartId`、`lessonId` 与 item `resourceId`，否则可能重复创建 lesson 或丢失部分 `partLessonMap`。
- Flutter 与后端并行时必须以冻结 DTO 为准，避免页面层拼接低级接口。
- 当前本地 Flutter 验证依赖 Windows SDK；若 WSL wrapper 或 Windows Dart compiler 崩溃，需要在最终交接中记录环境证据。
