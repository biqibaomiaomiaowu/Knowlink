# PLAN.md

## Phase 0：Baseline audit and contract lock

### Goal name

Baseline audit and contract lock

### Scope

先锁定真实 contract、测试基线和改动边界，避免 Codex 在 goal mode 中误改后端主干或重做 UI。

### Files likely to modify

- `docs/contracts/v2-course-lesson-workbench-contract.md`
- `docs/contracts/api-contract.md`
- 可新增：`docs/contracts/frontend-backend-finalization-contract.md`
- 可新增：`docs/v2/*handoff*.md`

Phase 0 不应修改生产代码，除非只修正文档与已实现 API 的明显不一致。

### Implementation steps

1. 对比 `main...codex/rerecreate`，记录前后端实际差异。
2. 审核以下 contract 是否与代码一致：
   - courses list/delete-impact/archive/restore。
   - resources upload/list/delete/playback。
   - lessons CRUD/reorder/merge/split/primary-video。
   - lesson progress。
   - B 站 import。
   - QA session/history。
   - quiz generate/submit/detail。
   - review run/review read model/complete。
3. 标记 contract gap：
   - `CreateLessonRequest.metaJson`。
   - resource generic download。
   - resource PATCH/rebind/visibleToCourseQa。
   - quiz history list。
   - QA history message 是否包含 question。
4. 记录前端真实 noop/static/local-only 状态。
5. 跑基线测试并记录失败项。
6. 更新 contract 文档中的本轮范围、Non-goals、风险和测试策略。

### Tests to add/update

- 本 phase 不强制新增测试。
- 可新增轻量 contract consistency test，确保 docs 中新增 route token 与 router/API wrapper 一致。

### Verification commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

### Done criteria

- 已明确列出 existing reusable / extend / new API。
- 已记录测试基线。
- Contract docs 写明 Non-goals。
- 没有生产行为改动。

### Rollback/safety notes

- 若只改 docs，可直接 revert docs commit。
- 不得在 Phase 0 引入 UI 或后端实现变更。
- 不得删除/跳过现有测试。

### Dependencies on earlier phases

无。

---

## Phase 1：P0 core integration

### Goal name

P0 core integration

### Scope

补主流程可信度：

1. 课程工作台上传课程/课时资料。
2. 课时进度持久化。
3. 新建课时字段落库。
4. 新建课时 B 站导入。
5. quiz submit → reviewTaskRunId → review polling → review read model 闭环。

### Files likely to modify

#### Flutter

- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/resource_upload_models.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/models/bilibili_import_models.dart`
- `client_flutter/lib/shared/models/bilibili_import_state.dart`
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/course_import_provider.dart`
- `client_flutter/lib/shared/providers/bilibili_import_provider.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/shared/providers/quiz_provider.dart`
- `client_flutter/lib/shared/providers/review_provider.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- `client_flutter/lib/features/review/review_page.dart`
- `client_flutter/test/**`

#### Backend

- `server/schemas/requests.py`
- `server/domain/services/lessons.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/api/routers/bilibili.py` only if request/response mismatch is discovered。
- `server/domain/services/bilibili*.py` only if bind-existing behavior is incomplete。
- `server/tests/**`
- `docs/contracts/*.md`

### Implementation steps

1. **Shared upload path**
   - Extract or add reusable upload controller for workbench.
   - Wire course resource card button to file picker/upload queue.
   - Use existing upload-init/object PUT/upload-complete.
   - Refresh workbench after success.
   - Keep existing CourseImportPage upload tests passing.

2. **Lesson progress**
   - Add progress save controller logic.
   - Wire video position updates to local state.
   - Debounce/throttle backend PUT.
   - Flush on pause and dispose.
   - Save block changes when outline/current block changes.

3. **Create lesson metadata**
   - Extend backend `CreateLessonRequest` with optional `meta_json/metaJson`.
   - Pass `meta_json` through `LessonService` to repository.
   - Ensure SQL/memory repos persist and return it.
   - Extend Flutter request construction and model parsing.
   - Update contract docs.

4. **B 站 import in new lesson**
   - Extend frontend Bilibili import request model to include `lessonMode`, `targetLessonId`, `partLessonMap`, `createLessonIfMissing`.
   - Add preview/auth/import state to new lesson dialog.
   - On submit with B 站 URL: preview or use existing preview, create lesson once, create bind-existing import, poll run, refresh workbench/lesson.
   - Add failure/cancel/retry UI states.

5. **Review closure**
   - Add ReviewProvider action for polling an existing run id.
   - Update ReviewPage to consume route query/CourseFlow run id.
   - Remove production `20ms` polling interval.
   - Ensure quiz submit CTA navigates to review with run id where available.

6. Update docs/contracts for all changed request/response fields and frontend flow guarantees.

### Tests to add/update

- Flutter provider tests：upload sequence/retry, lesson progress debounce/flush, create lesson metadata request, B 站 bind-existing import, review existing run polling。
- Flutter widget tests：workbench upload, new lesson metadata/B 站 states, lesson study progress hooks, review existing run loading。
- Backend tests：create lesson `metaJson`, B 站 bind-existing target lesson validation, lesson progress upsert, review run status compatibility。

### Verification commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Targeted examples:

```bash
python -m pytest server/tests/test_lessons.py server/tests/test_bilibili_sql_runtime.py server/tests/test_progress.py
cd client_flutter && flutter test test/features/course_workbench test/features/lesson_study test/features/review
```

### Done criteria

- 工作台课程级上传真实可用。
- 新建课时 metadata 持久化并向后兼容。
- B 站链接能完成 preview → bind-existing import → poll → refresh。
- 课时学习进度会保存并恢复。
- quiz submit 后 ReviewPage 会 poll existing `reviewTaskRunId` 并刷新 review。
- 旧课程导入、讲义生成、quiz submit、review regenerate 测试通过。

### Rollback/safety notes

- Upload 改动必须可独立 revert，不影响 CourseImportPage。
- Metadata 后端字段必须 optional。
- Progress save 失败不得阻断播放。
- B 站导入失败不得重复创建 lesson。
- Review polling 不得自动 regenerate。

### Dependencies on earlier phases

依赖 Phase 0。

---

## Phase 2：P1 interaction completion

### Goal name

P1 interaction completion

### Scope

补齐已露出 UI 的真实交互：

1. 课程库搜索、筛选、排序。
2. QA 会话历史。
3. 课时学习页 AI 问答 question+answer pair。
4. 本节资料弹窗操作。
5. 课时管理入口。

### Files likely to modify

#### Flutter

- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/models/handout_models.dart`
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/course_library_provider.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- 新增或修改 QA providers under `client_flutter/lib/shared/providers/*`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/lib/features/course_qa/course_qa_page.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`

#### Backend

- `server/api/routers/resources.py`
- `server/domain/services/resources.py`
- `server/schemas/requests.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/domain/services/qa.py`
- `server/infra/repositories/*` only if QA messages lack question。
- `server/tests/**`
- `docs/contracts/*.md`

### Implementation steps

1. **Course library filters**
   - Add query state and parameterized provider.
   - Replace static filter card with real controls.
   - Add loading/error/empty/refresh handling.
   - Preserve selection semantics.

2. **QA history**
   - Add `QaSessionModel` and richer `QaMessageModel` if needed.
   - Add providers for session list and messages.
   - Refactor `CourseQaPage` from local-only session state to provider-backed active session.
   - Send with active session id.
   - Refresh sessions after successful send.

3. **Lesson embedded QA pair**
   - Add local exchange model with pending/success/error.
   - Show user question and answer.
   - Add retry for failed exchange.
   - Keep existing lesson QA backend call.

4. **Materials dialog**
   - Add item-level actions: refresh, delete, mp4 preview.
   - Add generic download endpoint if implementing non-video download.
   - Add resource PATCH endpoint if implementing rebind/visibleToCourseQa.
   - Refresh lesson detail after mutations.

5. **Lesson management**
   - Add management menu to lesson cards.
   - Implement rename/delete/reorder first.
   - Add merge/split/set primary video as separate, tested operations.
   - Display stale artifact notice from merge/split response.

### Tests to add/update

- Course library provider/widget tests for query params and empty/error。
- QA provider/widget tests for session list/history/continue。
- Lesson study widget/provider tests for QA pairs/retry。
- Materials dialog tests for delete/download/toggle/rebind states。
- Lesson management widget/provider tests for each mutation。
- Backend resource update/download tests if endpoints added。
- Backend QA history question tests if response extended。

### Verification commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Targeted examples:

```bash
python -m pytest server/tests/test_resources.py server/tests/test_qa.py server/tests/test_lessons.py
cd client_flutter && flutter test test/features/course_library test/features/course_qa test/features/lesson_study test/features/course_workbench
```

### Done criteria

- 课程库筛选真实驱动后端 query。
- QA 页面能打开历史 session 并继续提问。
- 课时学习页嵌入 QA 展示 question+answer，失败可重试。
- 本节资料弹窗至少支持删除、刷新和视频预览；增强项有测试。
- 课时卡片有管理入口，且不破坏继续学习。
- P0 链路全部仍通过。

### Rollback/safety notes

- QA history refactor 不得删除现有发送 QA 功能。
- Materials PATCH/download 若风险过高，可保留最小闭环并在 docs 标记增强项未实现。
- Lesson management 操作必须 item-level loading，避免误操作多个课时。
- Reorder/merge/split 要信任后端 409，不在前端强行修复数据。

### Dependencies on earlier phases

依赖 Phase 0。部分 materials 操作依赖 Phase 1 upload/resource state。

---

## Phase 3：P2 management polish

### Goal name

P2 management polish

### Scope

补齐课程测试历史、重新生成测试语义、删除影响确认、归档/恢复。

### Files likely to modify

#### Flutter

- `client_flutter/lib/app/router/app_router.dart`
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/quiz_models.dart`
- 新增 `client_flutter/lib/shared/models/course_management_models.dart` 或合适模型文件
- `client_flutter/lib/shared/providers/course_library_provider.dart`
- `client_flutter/lib/shared/providers/quiz_provider.dart`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- 新增 `client_flutter/lib/features/quiz/quiz_history_page.dart`
- `client_flutter/test/**`

#### Backend

- `server/api/routers/quizzes.py`
- `server/domain/services/quizzes.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/api/routers/courses.py` only if response shape adjustment needed。
- `server/tests/**`
- `docs/contracts/*.md`

### Implementation steps

1. **Quiz history**
   - Add backend list endpoint.
   - Add repository/service method for quiz history with latest attempt summary.
   - Add Flutter models/provider/page.
   - Add route and wire workbench history button.

2. **Regenerate semantics**
   - Add query or constructor flag for `QuizPage(autoRegenerate)`.
   - Workbench regenerate button routes with `?regenerate=1`.
   - Guard against repeated generate on rebuild.
   - Keep start quiz route unchanged.

3. **Delete impact**
   - Add frontend wrappers/models.
   - Fetch impact before delete dialog.
   - Display counts and blockers.
   - Implement partial success/failure summary.

4. **Archive/restore**
   - Add frontend wrappers.
   - Add UI actions and archived filter.
   - Update query provider to use `archived`.
   - Handle active course archived/restored state.

5. Update docs/contracts.

### Tests to add/update

- Backend quiz history API/service/repository tests。
- Flutter quiz history provider/widget tests。
- Quiz regenerate once-only provider/widget tests。
- Course delete impact dialog tests。
- Archive/restore provider/widget tests。
- Existing quiz generation/detail/submit tests must remain green。

### Verification commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Targeted examples:

```bash
python -m pytest server/tests/test_quizzes.py server/tests/test_courses.py
cd client_flutter && flutter test test/features/quiz test/features/course_library test/features/course_workbench
```

### Done criteria

- 历史课程测试进入独立 history 页面并可打开 detail。
- 重新生成课程测试会真实调用 generate。
- 删除确认展示真实 impact，支持 partial failure。
- 课程可归档、查看归档、恢复。
- P0/P1 核心路径仍通过。

### Rollback/safety notes

- Quiz history endpoint 新增不应影响 existing quiz detail/submit。
- Auto regenerate 必须只在明确 query 下触发。
- Archive/restore 默认不改变 delete 行为。
- Delete impact 失败时不得直接继续删除。

### Dependencies on earlier phases

依赖 Phase 0。课程库 archived filter 与 Phase 2 query state 共用；若 Phase 2 未完成，Phase 3 需先落 query provider。

---

## Phase 4：Regression, docs, and handoff

### Goal name

Regression, docs, and handoff

### Scope

统一测试、contract 文档、手工验收说明和回归证明。

### Files likely to modify

- `docs/contracts/*.md`
- `docs/v2/*`
- `client_flutter/test/**`
- `server/tests/**`
- 不应新增功能代码，除非修复回归测试暴露的小缺陷。

### Implementation steps

1. 跑完整后端测试。
2. 跑完整 Flutter analyze/test。
3. 跑重点手工路径。
4. 更新 contract 文档：所有新增字段/API、Non-goals、已知限制、手工验收路径。
5. 写 handoff 记录：已完成 goal、验证命令、失败/跳过项、风险和后续建议。
6. 确认没有实现 Non-goals。

### Tests to add/update

- 不新增大测试，除非覆盖缺口明显。
- 补齐 regression test 名称与手工路径文档。

### Verification commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Optional targeted rerun:

```bash
python -m pytest server/tests/test_scaffold_consistency.py
cd client_flutter && flutter test test/features
```

### Done criteria

- 所有新增/修改 API 在 docs/contracts 中有记录。
- 测试命令结果清晰。
- 手工验收路径覆盖课程导入、资料、讲义、测试、复习链路。
- 没有新增大框架、没有 UI 风格替换、没有 Non-goal 实现。
- Handoff 文档能指导 reviewer 验证。

### Rollback/safety notes

- 文档和测试改动可独立 revert。
- 回归修复应小步提交，避免 Phase 4 引入新 feature。
- 若完整测试环境缺依赖，应记录缺失原因和已跑的替代命令。

### Dependencies on earlier phases

依赖 Phase 1–3 的实现完成。

---

# Codex Goal Pack

## Goal 1: Baseline audit and contract lock

Objective:
- 锁定 `codex/rerecreate` 当前真实状态、API contract 和测试基线，生成可执行的 contract delta。

Constraints:
- 不实现功能。
- 不改 UI。
- 不删除测试。
- 不处理 Non-goals。
- 不重写后端架构。

Allowed files:
- `docs/contracts/*.md`
- 可新增 `docs/contracts/frontend-backend-finalization-contract.md`
- 可新增审查记录文档 under `docs/v2/`

Disallowed files:
- `client_flutter/lib/**`
- `server/api/**`
- `server/domain/**`
- `server/infra/**`
- `server/tasks/**`

Steps:
1. Inspect key frontend/backend files listed in SPEC.
2. Record existing vs missing contract: `metaJson`, resource download/PATCH, quiz history, QA message question field, archive/restore/delete-impact wrappers.
3. Run baseline tests.
4. Update docs with contract delta and Non-goals.

Verification:
```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Acceptance:
- 文档明确列出 existing reusable / extend / new API。
- 测试基线记录完整。
- 没有生产代码 diff。

---

## Goal 2: Workbench course and lesson resource upload

Objective:
- 让课程工作台“上传资料”从 noop 变为真实 upload-init → object PUT → upload-complete → refresh 流程，并支持课程级/课时级 scope。

Constraints:
- 不改 B 站导入。
- 不重写 `CourseImportProvider`。
- 不绕过 `ApiClient` / `CourseLessonApi`。
- 不改变 CourseImportPage 行为。
- 不实现课程导出或课程设置。

Allowed files:
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/resource_upload_models.dart`
- `client_flutter/lib/shared/providers/course_import_provider.dart`
- 新增 shared upload provider/service under `client_flutter/lib/shared/providers/` or `shared/services/`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- `server/**` unless tests prove existing upload API is insufficient
- `client_flutter/lib/app/theme/**`
- graph/export/report pages

Steps:
1. Add CourseLessonApi upload/list/delete wrapper methods if missing.
2. Extract reusable upload execution logic or add workbench upload controller.
3. Wire course resource card button.
4. Add lesson-scoped upload entry where minimal and safe.
5. Refresh workbench/lesson state after success.
6. Add provider and widget tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
cd client_flutter && flutter test test/shared
```

Acceptance:
- Workbench upload button triggers real upload sequence.
- Course-level resources appear after upload.
- Lesson-level resources can be bound to a lesson.
- Failed item is retryable.
- Existing course import tests still pass.

---

## Goal 3: Lesson progress persistence

Objective:
- 保存并恢复课时播放位置、当前讲义块和阅读进度，避免高频请求。

Constraints:
- 不引入新状态管理框架。
- 不在 video listener 中每 tick 请求后端。
- 不阻塞视频播放。
- 不改 handout generation 后端。
- 不实现本节复习完整页。

Allowed files:
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/test/**`

Disallowed files:
- `server/**` unless existing progress API tests fail
- `client_flutter/lib/features/course_review/**`
- graph/export/report pages

Steps:
1. Add progress state to lesson study controller.
2. Restore from lesson detail/progress.
3. Track player position locally.
4. Add throttled save for playback.
5. Flush on pause, block jump, dispose.
6. Add tests for debounce/flush/error.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

Acceptance:
- Refresh after pause restores near last position.
- Block jump persists `lastHandoutBlockId`.
- 60s playback does not create high-frequency PUTs.
- API failure does not crash playback.

---

## Goal 4: Create lesson metadata persistence

Objective:
- 让新建课时表单的学习目标、掌握程度、时间预算和来源信息进入后端持久化 contract。

Constraints:
- `metaJson` 必须 optional。
- 不破坏旧 `CreateLessonRequest`。
- 不做课程设置完整功能。
- 不重写 lesson repository。
- 不删除 existing lesson tests。

Allowed files:
- `server/schemas/requests.py`
- `server/domain/services/lessons.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/tests/**`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- unrelated routers/services
- graph/export/report code
- UI theme files

Steps:
1. Add optional `metaJson` to backend create schema.
2. Pass `meta_json` through LessonService to repository.
3. Ensure memory and SQL repositories persist and return it.
4. Extend Flutter lesson models to parse it defensively.
5. Include form fields in create lesson request.
6. Add backend and Flutter tests.
7. Update docs/contracts.

Verification:
```bash
python -m pytest server/tests/test_lessons.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
```

Acceptance:
- New lesson request contains `metaJson`.
- Backend returns `lesson.metaJson`.
- Old request without `metaJson` passes.
- Invalid time budget blocks submit.

---

## Goal 5: Bilibili import from new lesson dialog

Objective:
- 将新建课时中的 B 站链接接入 preview/create import/poll，并绑定到新建课时。

Constraints:
- 不重写 B 站后端。
- 不实现复杂多 P 课程导入器。
- 不重复创建 lesson on retry。
- 无登录态不得创建假成功。
- 不影响本地文件新建课时流程。

Allowed files:
- `client_flutter/lib/shared/models/bilibili_import_models.dart`
- `client_flutter/lib/shared/models/bilibili_import_state.dart`
- `client_flutter/lib/shared/providers/bilibili_import_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/test/**`
- `server/tests/**` only for bind-existing validation gaps
- `docs/contracts/*.md`

Disallowed files:
- Bilibili downloader internals unless tests prove bind-existing is broken
- unrelated course import redesign
- UI theme files

Steps:
1. Extend Flutter create import request model with bind-existing fields.
2. Add preview state to new lesson dialog.
3. On submit with URL, create lesson once and create import with `lessonMode=bind_existing`.
4. Poll import run status.
5. Refresh workbench/lesson after `imported`.
6. Add auth inactive/error/retry/cancel UI states.
7. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
cd client_flutter && flutter test test/shared/bilibili_import_models_test.dart
python -m pytest server/tests/test_bilibili_sql_runtime.py server/tests/test_bilibili_url.py
```

Acceptance:
- B 站 URL can preview.
- Submit creates lesson and bind-existing import.
- Imported run refreshes lesson primary video.
- Retry does not duplicate lesson.
- No-login state is explicit.

---

## Goal 6: Quiz submit to review polling closure

Objective:
- 完成 quiz submit → `reviewTaskRunId` → review run polling → review read model 展示闭环。

Constraints:
- 不从零实现 review 后端。
- 不自动 regenerate review when existing run id is present。
- 不使用 20ms 生产轮询。
- 不改主观题判卷。
- 不破坏手动“重新生成复习”。

Allowed files:
- `client_flutter/lib/shared/providers/quiz_provider.dart`
- `client_flutter/lib/shared/providers/review_provider.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- `client_flutter/lib/features/review/review_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- `server/domain/services/review*` unless existing tests fail
- graph/report/export code
- subjective grading code

Steps:
1. Add ReviewProvider method to poll existing run id.
2. Make ReviewPage consume route query or CourseFlow run id.
3. After terminal status, fetch course review.
4. Guard consumed run id from repeated polling.
5. Restore production polling interval.
6. Add tests for null/non-null run id.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/review test/features/quiz
python -m pytest server/tests
```

Acceptance:
- Quiz submit with run id leads ReviewPage to poll status.
- Null run id shows normal review empty/read model.
- Manual regenerate still works.
- Mark complete still refreshes stats.

---

## Goal 7: Course library search/filter/sort

Objective:
- 将课程库静态筛选 UI 接入真实 query/provider/API。

Constraints:
- 不实现 archive/restore actions in this goal, except archived filter state if needed。
- 不改课程卡片主视觉。
- 不绕过 CourseLessonApi。
- 不删除 selection mode。
- 不实现 course settings。

Allowed files:
- `client_flutter/lib/shared/providers/course_library_provider.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- backend course router/service unless tests show API missing
- theme files
- workbench page except route expectations if needed

Steps:
1. Add query state model/provider.
2. Parameterize library fetch.
3. Replace static fields with real controls.
4. Add loading/error/empty/refresh handling.
5. Add debounce for search.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_library
```

Acceptance:
- Query params are passed correctly.
- Search/filter/sort update list.
- Empty and error states are visible.
- Continue learning still works.

---

## Goal 8: QA session history

Objective:
- 接入课程级/课时级 QA session list、history messages 和继续历史 session。

Constraints:
- 不实现 streaming。
- 不做单资料 QA。
- 不混用 course/lesson scope。
- 不改 QA 后端生成策略。
- 不引入新状态管理框架。

Allowed files:
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/models/handout_models.dart`
- `client_flutter/lib/shared/providers/*qa*`
- `client_flutter/lib/features/course_qa/course_qa_page.dart`
- `client_flutter/test/**`
- `server/domain/services/qa.py`
- `server/infra/repositories/*`
- `server/tests/**`
- `docs/contracts/*.md`

Disallowed files:
- unrelated inquiry page unless compile requires
- graph/report/export code
- LLM/QA orchestrator internals unless message fields impossible otherwise

Steps:
1. Add `QaSessionModel`.
2. Extend message model with question/createdAt if backend returns it.
3. Add providers for sessions/messages.
4. Refactor CourseQaPage to use provider-backed active session.
5. Send with active session id.
6. If backend messages omit question, extend service/repository response and tests.
7. Add widget/provider tests.

Verification:
```bash
python -m pytest server/tests/test_qa.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_qa
```

Acceptance:
- Session list loads for course and lesson scope.
- Clicking session shows question+answer history.
- Continuing a session reuses session id.
- New session creates separate history.
- Scope does not leak.

---

## Goal 9: Lesson embedded QA question-answer pairs

Objective:
- 课时学习页内嵌 AI 问答展示用户问题、回答、错误和重试。

Constraints:
- 不实现 QA history full sidebar here。
- 不实现 streaming。
- 不改 lesson handout layout beyond QA panel needs。
- 不做单资料 QA。
- 不破坏 CourseQaPage。

Allowed files:
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/test/**`

Disallowed files:
- backend QA files unless API contract fails
- course_qa_page except shared model compile fixes
- theme files

Steps:
1. Add lesson QA exchange state.
2. Optimistically append question and pending answer.
3. Update exchange on success/error.
4. Add retry per failed exchange.
5. Render question bubble and answer bubble.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

Acceptance:
- User question is visible.
- Pending answer is visible.
- Success answer/citations visible.
- Failed exchange has retry.
- Block-specific grouping remains.

---

## Goal 10: Lesson materials dialog actions

Objective:
- 让“本节资料”弹窗至少支持删除、刷新和视频预览；根据 contract 增加下载、重绑定和课程 QA 可见性操作。

Constraints:
- 不实现课程导出。
- 不假装非视频下载成功。
- 不让刷新资料重置视频播放状态。
- 不绕过 CourseLessonApi。
- 不做大 UI 重设计。

Allowed files:
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/test/**`
- `server/api/routers/resources.py`
- `server/domain/services/resources.py`
- `server/schemas/requests.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/*`
- `server/tests/**`
- `docs/contracts/*.md`

Disallowed files:
- export/report/graph pages
- object storage implementation unless generic download requires a small service call
- theme files

Steps:
1. Add item-level dialog state.
2. Wire delete with confirmation and refresh.
3. Wire mp4 preview via playback.
4. Decide and implement generic download endpoint if required by contract.
5. Decide and implement resource PATCH for rebind/visibleToCourseQa if in scope.
6. Add UI controls and tests.
7. Update docs.

Verification:
```bash
python -m pytest server/tests/test_resources.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

Acceptance:
- Dialog is not read-only.
- Delete works and refreshes.
- Delete blocker shows error.
- mp4 preview gets playback URL.
- Download/toggle/rebind either works with tests or is explicitly disabled with contract note.

---

## Goal 11: Lesson management MVP: rename/delete/reorder

Objective:
- 在工作台课时卡片增加管理入口，支持重命名、删除、上移/下移排序。

Constraints:
- 不实现 merge/split/set primary video in this goal。
- 不破坏卡片点击继续学习。
- 不做拖拽排序 unless simple and tested。
- 不删除 existing lesson tests。
- 不改后端架构。

Allowed files:
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- backend lessons files unless wrapper mismatch is found
- lesson study page
- theme files

Steps:
1. Add lesson card management menu.
2. Add rename dialog using PATCH.
3. Add delete confirmation using DELETE.
4. Add up/down reorder using reorder endpoint.
5. Refresh workbench after mutation.
6. Add tests for each action and continue-learning unaffected.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
python -m pytest server/tests/test_lessons.py
```

Acceptance:
- Rename persists.
- Delete removes lesson.
- Reorder persists.
- Continue-learning route still works.
- Mutation errors are visible.

---

## Goal 12: Lesson management advanced: merge/split/set primary video

Objective:
- 补齐相邻课时合并、按时间拆分、设置主视频入口。

Constraints:
- 只允许合并相邻课时。
- 不复制视频 resource。
- 不隐藏 stale artifact response。
- 不破坏 rename/delete/reorder。
- 不实现视频剪辑或转码。

Allowed files:
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `server/tests/**` if existing backend behavior needs coverage
- `docs/contracts/*.md`

Disallowed files:
- Bilibili downloader/tasks
- video player internals
- graph/export/report pages

Steps:
1. Fix `setLessonPrimaryVideo` request type to int if needed.
2. Add adjacent multi-select merge UI.
3. Add split dialog with timestamp validation.
4. Add set primary video dialog listing mp4 resources.
5. Display stale artifact warning after merge/split.
6. Add tests.

Verification:
```bash
python -m pytest server/tests/test_lessons.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
```

Acceptance:
- Adjacent merge works.
- Non-adjacent merge is blocked or shows 409.
- Valid split creates two lessons.
- Invalid split shows error.
- Set primary video changes lesson playback source.

---

## Goal 13: Quiz history

Objective:
- 新增课程 quiz history API、provider 和页面，并让 workbench 历史按钮进入真实历史列表。

Constraints:
- 不实现主观题判卷。
- 不改 quiz detail contract except history item links。
- 不破坏 existing course/lesson quiz generation。
- 不把 history 塞成复杂报表。
- 不做学习报告。

Allowed files:
- `server/api/routers/quizzes.py`
- `server/domain/services/quizzes.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/tests/**`
- `client_flutter/lib/app/router/app_router.dart`
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/models/quiz_models.dart`
- `client_flutter/lib/shared/providers/*quiz*`
- `client_flutter/lib/features/quiz/**`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- review service unless compile requires
- graph/report/export pages
- subjective grading implementation

Steps:
1. Add backend quiz history list endpoint.
2. Add repository/service tests.
3. Add Flutter model/provider.
4. Add QuizHistoryPage and route.
5. Wire workbench history button.
6. Add widget tests.

Verification:
```bash
python -m pytest server/tests/test_quizzes.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/quiz test/features/course_workbench
```

Acceptance:
- History endpoint returns course quizzes.
- History page lists items.
- Clicking item opens `/quizzes/:quizId`.
- Empty state works.
- Existing quiz tests pass.

---

## Goal 14: Regenerate quiz semantics

Objective:
- 让 workbench “重新生成课程测试”真实触发 course quiz generate，而非仅跳转。

Constraints:
- 不自动触发普通 quiz route。
- 不在 rebuild 中重复 generate。
- 不影响 lesson quiz。
- 不实现 quiz history in this goal unless already present。
- 不做 subjective grading。

Allowed files:
- `client_flutter/lib/app/router/app_router.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- `client_flutter/lib/shared/providers/quiz_provider.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- backend quiz service/router
- review provider except compile fixes
- graph/report/export pages

Steps:
1. Pass `regenerate=1` query from workbench button.
2. Add `autoRegenerate` handling in router/QuizPage.
3. Trigger `generateAndPoll` once after entry sync.
4. Add duplicate guard.
5. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/quiz test/features/course_workbench
```

Acceptance:
- Regenerate button calls generate API.
- Start quiz button does not auto-generate.
- Rebuild does not call twice.
- Lesson quiz unaffected.

---

## Goal 15: Course delete impact, archive, and restore

Objective:
- 接入 delete-impact 确认、课程归档、查看归档和恢复。

Constraints:
- 不做物理删除。
- impact 加载失败时不得直接删除。
- 不破坏课程库筛选。
- 不实现课程设置。
- 不改后端 API unless response shape tests fail。

Allowed files:
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- 可新增 `client_flutter/lib/shared/models/course_management_models.dart`
- `client_flutter/lib/shared/providers/course_library_provider.dart`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/test/**`
- `server/tests/test_courses.py` or existing course tests
- `docs/contracts/*.md`

Disallowed files:
- workbench page except route side effects if active course archived
- lesson/quiz/review services
- theme files

Steps:
1. Add ApiClient/CourseLessonApi wrappers.
2. Add delete impact model.
3. Fetch impact before delete dialog.
4. Implement partial success/failure delete.
5. Add archive/restore mutations.
6. Add archived filter UI if not already done.
7. Add tests.

Verification:
```bash
python -m pytest server/tests/test_courses.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_library
```

Acceptance:
- Delete dialog shows real impact counts.
- Partial failures are visible.
- Archive hides course from default list.
- Archived-only filter shows archived courses.
- Restore returns course to default list.

---

## Goal 16: Final regression, docs, and handoff

Objective:
- 完整回归测试、更新 contract/handoff 文档，证明没有破坏旧的课程导入、讲义、测试、复习链路。

Constraints:
- 不新增大功能。
- 不实现 Non-goals。
- 不删除失败测试来“过关”。
- 不修改 UI 风格。
- 不重写架构。

Allowed files:
- `docs/contracts/*.md`
- `docs/v2/**`
- `client_flutter/test/**`
- `server/tests/**`
- 小范围 bugfix 所需文件

Disallowed files:
- 大规模 feature files unless fixing regression
- theme replacement
- new state management framework

Steps:
1. Run full backend tests.
2. Run Flutter analyze/test.
3. Run targeted feature tests.
4. Update contract docs.
5. Add handoff doc with manual verification checklist.
6. Confirm Non-goals untouched.
7. Record known limitations.

Verification:
```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Acceptance:
- Full regression commands pass or documented environment-only failures are justified.
- Contract docs match implemented APIs.
- Handoff checklist covers upload, lesson progress, metadata, B 站, QA, quiz, review, library management.
- No Non-goal implementation appears in diff.
