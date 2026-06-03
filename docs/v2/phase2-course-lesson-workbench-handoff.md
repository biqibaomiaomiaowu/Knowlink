# V2 Phase 2 Course-Lesson Workbench Handoff

日期：2026-06-02

本文件用于记录课程 / 节课工作台实现后的交接状态。当前已完成 Task 1 契约冻结、Task 2 后端 schema / repository 原语、Task 3 课程库 / 课程管理 / 删除影响 / 课程工作台后端 API、Task 4 lesson API、Task 5 资源 scope / 上传 placement / B站导入自动建 lesson、Task 6 分层学习产物 / placeholder API、Task 7 Flutter 课程 / 节课 IA 页面、Task 8 首页继续学习 / 课程内推荐 / 报告导出占位，以及 Task 9 文档 / scaffold consistency / focused final verification。

## Implemented Scope

- Task 1：冻结 V2 Phase 2 课程 / 节课工作台契约、错误码和 handoff 骨架。
- Task 2：新增 lesson、user lesson progress、分层资源和分层 artifact 的后端模型、迁移、仓储协议、memory / SQL 仓储实现与测试。
- Task 3：新增完整课程库 `GET /api/v1/courses`、课程 PATCH、归档 / 恢复、删除影响、soft delete 阻塞判断，以及 `GET /api/v1/courses/{courseId}/workbench` 聚合 read model。
- Task 4：新增 lesson CRUD、reorder、primary video、merge、split，以及 lesson detail 聚合 read model。
- Task 5：新增资源上传 scope 校验、本地 MP4 自动建 lesson / 绑定既有 lesson、B站导入 per-video lesson mapping 与重试复用。
- Task 6：新增 course / lesson 讲义、QA、测验、复习、进度、图谱、报告和导出 placeholder API，并保留 V1 course-level 兼容入口。
- Task 7：新增 Flutter 课程库、课程工作台、节课详情、全课程 / 节课 QA、graph / report / export / handout placeholder 页面、课程导入 scope 控件和继续学习跳转；默认 `/courses/:courseId/review` 保留既有真实复习任务页，report / 综合测验 / 主观题判卷通过 query 进入占位状态；前端模型对齐冻结 DTO 的 `artifactSummaries` list、`nextAction.type/route`、lesson progress 和 lesson 操作门面。
- Task 8：新增首页 `continueLearning` 具体节课定位、current course / current lesson / next step / today review tasks / course quick entries；新增 course / lesson `recommendations/next-actions` 确定性规则推荐；报告和导出 placeholder 响应补齐 `courseId` / `lessonId` scope 字段。
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
| Home / progress | continue into lesson, lesson progress | Done for Task 8 home continue-learning and lesson-scoped next actions | `server/tests/test_home_lesson_continuation.py`, `server/tests/test_scoped_learning_artifacts.py`, `server/tests/test_lesson_repository.py` |
| In-course recommendations | course / lesson next-actions placeholder rules | Done for Task 8 deterministic rule-based recommendations; graph-driven reasons remain placeholder | `server/tests/test_home_lesson_continuation.py` |

## Flutter Contract Table

| Area | Route | Implementation status | Tests |
|---|---|---|---|
| Course library | `/courses` | Done for Task 7 Flutter page / provider / model | `client_flutter/test/widgets/course_library_page_test.dart` |
| Course workbench | `/courses/:courseId` | Done for Task 7 Flutter page / provider / route | `client_flutter/test/widgets/course_workbench_page_test.dart` |
| Lesson detail | `/courses/:courseId/lessons/:lessonId` | Done for Task 7 Flutter page / provider / route | `client_flutter/test/widgets/lesson_detail_page_test.dart` |
| Course QA | `/courses/:courseId/qa` | Done for Task 7 scoped QA placeholder UI | `client_flutter/test/app_router_test.dart` |
| Lesson QA | `/courses/:courseId/lessons/:lessonId/qa` | Done for Task 7 scoped QA placeholder UI | `client_flutter/test/app_router_test.dart` |
| Lesson operations | lesson CRUD / reorder / primary video / merge / split / progress | Done for Task 7 API facade coverage | `client_flutter/test/shared/course_lesson_api_test.dart` |
| Placeholder pages | graph / exports / handout / report / comprehensive quiz / subjective grading | Done for Task 7 placeholder pages and routes; default course review route keeps existing `ReviewPage` | `client_flutter/test/app_router_test.dart` |

## Migration And Rollback Notes

- 新表和新增 nullable scope 字段应可独立回滚。
- 旧 course-centric rows 迁移为 `scopeType=course`、`lessonId=null`。
- `mastery_records` 使用 course-scope 与 lesson-scope 两个 partial unique indexes，避免 nullable `lesson_id` 破坏课程级唯一性。
- `user_lesson_progress.last_handout_block_id` 会校验 handout block 归属，不接受未知或跨课程引用。
- Downgrade 会删除旧 V1 schema 无法表达的 QA / quiz scoped placeholder 行，再恢复旧的非空 handout 外键。
- 不删除旧列，不破坏 V1 course-level 路由。
- B站 import run 的 `selection.partLessonMap` 记录 `sourcePartId -> {lessonId, resourceId}`，`bilibili_import_items.lesson_id` 同步保存 item 级 lesson 归属。若 part 上传中途失败，已创建的 lesson 会保留，retry 必须复用该 `lessonId`，不得重复创建 lesson。

## Demo Routes And Manual Acceptance Checklist

Demo route list:

- `/courses`
- `/courses/:courseId`
- `/courses/:courseId/qa`
- `/courses/:courseId/graph`
- `/courses/:courseId/review`
- `/courses/:courseId/review?kind=report`
- `/courses/:courseId/review?kind=comprehensive_quiz`
- `/courses/:courseId/review?kind=subjective_grading`
- `/courses/:courseId/exports`
- `/courses/:courseId/lessons/:lessonId`
- `/courses/:courseId/lessons/:lessonId/qa`
- `/courses/:courseId/lessons/:lessonId/handout`
- `/courses/:courseId/lessons/:lessonId/review`
- `/courses/:courseId/lessons/:lessonId/graph`

Manual acceptance checklist:

- Create course.
- Upload MP4 and verify lesson auto-created.
- Upload PDF to course scope.
- Upload PPTX / PDF to lesson scope.
- Open course workbench.
- Open lesson detail.
- Use course QA entry and lesson QA entry as distinct pages.
- Verify no resource QA entry exists.
- Archive and restore course.
- Confirm home continues into lesson.

## Fixed Demo Data And Acceptance Evidence

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
- Task 7 Flutter 验证命令（规格修复后复跑）：`flutter test test/app_router_test.dart test/widgets/course_library_page_test.dart test/widgets/course_workbench_page_test.dart test/widgets/lesson_detail_page_test.dart test/shared/course_lesson_api_test.dart` 通过；`flutter analyze` 通过。当前 WSL Flutter shell wrapper 有 CRLF 问题，实际验证在 D 盘临时副本通过 Windows Flutter SDK 执行。
- Task 8 首页 / 推荐 / 报告导出占位验证命令：`.venv/bin/python -m pytest -q server/tests/test_home_lesson_continuation.py server/tests/test_course_workbench_api.py` 通过。
- Task 8 scoped artifact 回归验证命令：`.venv/bin/python -m pytest -q server/tests/test_scoped_learning_artifacts.py` 通过。
- Task 9 focused backend suite：`.venv/bin/python -m pytest -q server/tests/test_course_lesson_contract.py server/tests/test_lesson_repository.py server/tests/test_lessons_api.py server/tests/test_course_workbench_api.py server/tests/test_resource_scope_import.py server/tests/test_scoped_learning_artifacts.py server/tests/test_home_lesson_continuation.py server/tests/test_api.py server/tests/test_contract_freeze.py server/tests/test_scaffold_consistency.py` 通过。
- Task 9 Flutter suite：`flutter test` 通过；`flutter analyze` 通过。当前 WSL Flutter shell wrapper 有 CRLF 问题，实际验证在 D 盘临时副本通过 Windows Flutter SDK 执行。
- Final review remediation：merge 会将非 target lesson 的 lesson-scoped resources 迁移到 target lesson；split 后两段 lesson 共享同一个 `primaryVideoResourceId`，必要时把原 lesson-scoped video 提升为 course scope；`CreateLessonRequest` 主视频必须带完整 start/end range。
- Final verification：后端 845 个 pytest 用按文件顺序分段全覆盖命令通过；本机单进程全量 pytest 在 pytest / C extension 长进程里出现非确定性 SIGSEGV，失败用例单跑和文件级均通过。Windows Flutter SDK 临时副本 `flutter test` 通过、`flutter analyze` 通过。
- 后端 pytest 命令和结果：`server/tests/test_lesson_repository.py server/tests/test_contract_freeze.py server/tests/test_scaffold_consistency.py server/tests/test_resource_deletion_semantics.py server/tests/test_sql_runtime_contract.py` 通过。
- Task 3 后端 pytest 命令和结果：`.venv/bin/python -m pytest -q server/tests/test_course_workbench_api.py server/tests/test_api.py` 通过。
- Task 3 repository / migration 回归：`.venv/bin/python -m pytest -q server/tests/test_lesson_repository.py server/tests/test_lesson_migration.py server/tests/test_scaffold_consistency.py server/tests/test_sql_runtime_contract.py` 通过。
- Alembic 临时 SQLite 升降级：`upgrade head -> downgrade c8d9e0f1a2b3 -> upgrade head` 通过。

## Known Risks

- V1 数据是 course-centric，多表增加 scope 需要保守迁移和兼容默认值。
- 课程 / 节课删除会影响引用链，第一轮必须优先 blocker 预览和软删除。
- B站导入重试需要幂等记录 `sourcePartId`、`lessonId` 与 item `resourceId`，否则可能重复创建 lesson 或丢失部分 `partLessonMap`。
- Flutter 与后端并行时必须以冻结 DTO 为准，避免页面层拼接低级接口。
- 当前本地 Flutter 验证依赖 Windows SDK；若 WSL wrapper 或 Windows Dart compiler 崩溃，需要在最终交接中记录环境证据。
