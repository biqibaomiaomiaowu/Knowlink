# PLAN.md

## Execution strategy: parallel lanes with integration checkpoints

本计划面向 Codex goal mode，并假设 Codex 会配合 `superpowers` skill 做 evidence-driven implementation、测试闭环和阶段验收。为缩短总耗时，任务不再按 P0/P1/P2 完全线性执行，而是采用“Phase 0 串行锁 contract，随后按 lane 并行，最后统一集成回归”的方式。

### Parallelization summary

| Stage | Parallelism | Rule |
|---|---:|---|
| Phase 0 | 串行 | 先锁真实 contract、测试基线、文件所有权。 |
| Phase 1A | 可并行 | Backend contract lane、Lesson study lane、Course library lane 可同时启动。 |
| Phase 1B | 可并行但有门禁 | Workbench lane 可先做 upload/metadata UI，但 B 站最终 wiring 依赖 Backend contract audit；QA page lane 依赖 QA message contract；Quiz/Review lane 可先做 review closure。 |
| Phase 2 | 可并行 | 各 lane 做 P1/P2 扩展，但不得同时修改同一高冲突文件。 |
| Phase 3 | 串行集成 | 统一 merge/rebase、全量测试、文档和 handoff。 |

### Lane ownership

| Lane | Owner files | Main goals | Can run with |
|---|---|---|---|
| A. Backend contract lane | `server/**`, `docs/contracts/**` | `metaJson`, QA message question audit, resource PATCH/download, quiz history API | B/C/D/F 的前端预备工作 |
| B. Workbench lane | `course_workbench_page.dart`, workbench provider/models | upload, create lesson metadata UI, B 站 dialog, lesson management, quiz buttons | C/D/E; 与 F 在 router/quiz button 处需 checkpoint |
| C. Lesson study lane | `lesson_study_provider.dart`, `lesson_study_page.dart`, `lesson_study_state.dart` | progress, embedded QA pair, materials dialog | B/D/E/F; materials enhanced 依赖 A |
| D. Course library lane | `course_library_page.dart`, `course_library_provider.dart` | search/filter/sort, delete-impact, archive/restore | B/C/E/F; delete-impact wrappers may depend on A audit |
| E. QA page lane | `course_qa_page.dart`, QA providers/models | session list/history/continue | B/C/D/F; message fields depend on A |
| F. Quiz/Review lane | `quiz_page.dart`, `quiz_provider.dart`, `review_page.dart`, `review_provider.dart`, router | quiz submit → review run, quiz history UI, regenerate semantics | C/D/E; router/button changes need B checkpoint |

### High-conflict files

以下文件同一时间只能由一个 active goal 修改：

- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- `client_flutter/lib/app/router/app_router.dart`
- `client_flutter/lib/core/network/api_client.dart`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `docs/contracts/*.md`

如两个 goals 都需要共享 wrapper，例如 `api_client.dart`，优先由一个 lane 先增加 wrapper，其他 lane 只消费已合并 wrapper。

---

## Phase 0：Baseline audit and contract lock

### Goal name

Baseline audit and contract lock

### Scope

先检查现状，锁定真实 contract、缺口、测试基线和文件所有权，避免并行执行时误改或重复实现。

### Files likely to modify

- `docs/contracts/v2-course-lesson-workbench-contract.md`
- `docs/contracts/api-contract.md`
- 可新增 `docs/contracts/frontend-backend-finalization-contract.md`
- 可新增 `docs/v2/*handoff*.md`

### Implementation steps

1. 对比 `main...codex/rerecreate`，记录前后端真实差异。
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
4. 写入并行 lane ownership 和 high-conflict files。
5. 跑基线测试，记录失败项。
6. 更新 docs/contracts 的本轮范围、Non-goals、风险和测试策略。

### Tests to add/update

- 本 phase 不强制新增测试。
- 可新增轻量 contract consistency test。

### Verification commands

```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

### Done criteria

- Contract gap 已清楚标为“已有可复用 / 已有但需扩展 / 需要新增”。
- 并行 lane ownership 已写入文档。
- 测试基线已记录。
- 没有生产行为改动。

### Rollback/safety notes

- Phase 0 只改文档时可直接 revert。
- 不得在 Phase 0 实现 UI 或后端功能。
- 不得删除/跳过测试。

### Dependencies on earlier phases

无。

---

## Phase 1：Parallel P0 core lanes

### Goal name

Parallel P0 core integration

### Scope

并行补 P0 主流程可信度。该 phase 拆成多个可并行 lane，不是一个 Codex goal 一次性做完。

### Parallel lanes

#### Lane A1：Backend contract foundation

**Scope**

- `CreateLessonRequest.metaJson`。
- QA history message 字段审计；如缺 question 则补 response。
- B 站 bind-existing 行为审计和测试。
- Review run status contract audit。

**Files likely to modify**

- `server/schemas/requests.py`
- `server/domain/services/lessons.py`
- `server/domain/services/qa.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/tests/**`
- `docs/contracts/*.md`

**Implementation steps**

1. Add optional `metaJson` to `CreateLessonRequest`.
2. Pass `meta_json` into lesson repository create and return it.
3. Add backward compatibility tests.
4. Audit QA session messages for question field; extend if missing.
5. Add B 站 bind-existing validation test if missing.
6. Update contract docs.

**Tests**

```bash
python -m pytest server/tests/test_lessons.py server/tests/test_qa.py server/tests/test_bilibili_sql_runtime.py server/tests/test_bilibili_url.py
```

**Done criteria**

- `metaJson` optional and persisted.
- QA history messages expose question or documented fallback with tests.
- B 站 bind-existing target lesson behavior tested.

**Can run in parallel with**

- Lane C1 Lesson progress.
- Lane D1 Course library query frontend.
- Lane F1 Review closure frontend, if no backend changes needed.

---

#### Lane B1：Workbench upload and create lesson frontend

**Scope**

- Workbench course/lesson resource upload.
- New lesson metadata frontend wiring.

**Files likely to modify**

- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/resource_upload_models.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/providers/course_import_provider.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`

**Implementation steps**

1. Add or expose upload wrappers through `CourseLessonApi`.
2. Extract reusable upload execution from CourseImportProvider, or add workbench upload controller reusing same models.
3. Wire course resource card upload button.
4. Add minimal lesson-scoped upload entry where safe.
5. Include new lesson form fields in create lesson request once backend `metaJson` is available; before backend merge, keep code behind model/request compatibility if possible.
6. Refresh workbench after success.

**Tests**

```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
cd client_flutter && flutter test test/shared
```

**Done criteria**

- Workbench upload button executes real upload sequence.
- Course-level resource appears after upload.
- Lesson-scoped resource can be bound to selected lesson.
- New lesson metadata is included when backend contract is ready.
- CourseImportPage remains green.

**Can run in parallel with**

- Lane A1 for backend contract, but final metadata tests depend on A1.
- Lane C1/D1/E1/F1 if no shared file conflict.

---

#### Lane C1：Lesson progress persistence

**Scope**

- Persist and restore lesson playback position, active handout block, read percent.

**Files likely to modify**

- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/test/**`

**Implementation steps**

1. Add progress save state to lesson study controller.
2. Restore from lesson detail/progress.
3. Track player position locally.
4. Add throttled save for playback.
5. Flush on pause, block jump, dispose.
6. Add debounce/flush/error tests.

**Tests**

```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

**Done criteria**

- Refresh after pause restores near last position.
- Block jump persists `lastHandoutBlockId`.
- 60s playback does not create high-frequency PUTs.
- Progress save failure does not crash playback.

**Can run in parallel with**

- A1/B1/D1/E1/F1, provided no one else modifies `lesson_study_*` files.

---

#### Lane F1：Quiz submit to review polling closure

**Scope**

- Connect quiz submit `reviewTaskRunId` to ReviewPage existing run polling.

**Files likely to modify**

- `client_flutter/lib/shared/providers/quiz_provider.dart`
- `client_flutter/lib/shared/providers/review_provider.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- `client_flutter/lib/features/review/review_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

**Implementation steps**

1. Add ReviewProvider method to poll existing run id.
2. Make ReviewPage consume query `runId` or CourseFlow run id.
3. After terminal status, fetch course review.
4. Guard consumed run id from repeated polling.
5. Restore production polling interval; use short interval only in tests.
6. Add null/non-null run id tests.

**Tests**

```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/review test/features/quiz
python -m pytest server/tests/test_review_strategy.py server/tests/test_quiz_strategy.py
```

**Done criteria**

- Quiz submit with run id leads ReviewPage to poll status.
- Null run id shows normal review empty/read model.
- Manual regenerate still works.
- Mark complete still refreshes stats.

**Can run in parallel with**

- A1/B1/C1/D1/E1, unless router or workbench quiz buttons are touched.

---

## Phase 2：Parallel P1 interaction completion

### Goal name

Parallel P1 interaction completion

### Scope

各 lane 在 P0 targeted tests 通过后继续补交互。可以并行，但同 lane 内串行。

### Parallel lanes

#### Lane D1：Course library search/filter/sort

**Files likely to modify**

- `client_flutter/lib/shared/providers/course_library_provider.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/test/**`

**Steps**

1. Add query state model/provider.
2. Parameterize library fetch.
3. Replace static fields with real controls.
4. Add debounce for search.
5. Add loading/error/empty/clear filters.

**Verification**

```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_library
```

**Done criteria**

- Query params passed correctly.
- Search/filter/sort update list.
- Empty/error states visible.
- Continue learning still works.

---

#### Lane E1：QA session history

**Files likely to modify**

- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/models/handout_models.dart`
- `client_flutter/lib/shared/providers/*qa*`
- `client_flutter/lib/features/course_qa/course_qa_page.dart`
- `client_flutter/test/**`
- backend QA files only if A1 proves question missing.

**Steps**

1. Add `QaSessionModel`.
2. Extend message model with question/createdAt if backend supports it.
3. Add providers for sessions/messages.
4. Refactor CourseQaPage to provider-backed active session.
5. Send with active session id.
6. Refresh sessions after send.

**Verification**

```bash
python -m pytest server/tests/test_qa.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_qa
```

**Done criteria**

- Course and lesson session lists load.
- Clicking session shows question+answer history.
- Continuing a session reuses session id.
- New session creates separate history.
- Scope does not leak.

---

#### Lane C2：Lesson embedded QA pair and materials dialog

**Files likely to modify**

- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/lib/core/network/api_client.dart` only if missing material wrappers.
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/test/**`

**Steps**

1. Add lesson QA exchange state: pending/success/error/retry.
2. Render question bubble and answer bubble with citations.
3. Add materials dialog item actions: refresh, delete, mp4 preview.
4. If backend resource PATCH/download exists, add visibleToCourseQa/rebind/download operations; otherwise show disabled states.
5. Add tests.

**Verification**

```bash
python -m pytest server/tests/test_resources.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

**Done criteria**

- Embedded QA displays question and answer.
- Failed QA has retry.
- Materials dialog is not read-only.
- Delete works and refreshes.
- mp4 preview obtains playback URL.

---

#### Lane B2：Lesson management in workbench

**Files likely to modify**

- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`

**Steps**

1. Add lesson card management menu separate from continue learning.
2. Implement rename/delete/reorder first.
3. Add adjacent merge, split, set primary video after MVP tests pass.
4. Display stale artifact notice from merge/split.
5. Add tests for each operation.

**Verification**

```bash
python -m pytest server/tests/test_lessons.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
```

**Done criteria**

- Rename/delete/reorder persist.
- Merge only adjacent lessons.
- Split validates timestamp.
- Set primary video changes playback source.
- Continue learning route still works.

---

## Phase 3：Parallel P2 management polish

### Goal name

Parallel P2 management polish

### Scope

补 quiz history、重新生成语义、删除影响确认、归档/恢复。D lane 与 F lane 可并行，Workbench/Router 接口处做 checkpoint。

### Parallel lanes

#### Lane F2：Quiz history and regenerate semantics

**Files likely to modify**

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
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart` only after Workbench lane checkpoint.
- `client_flutter/test/**`
- `docs/contracts/*.md`

**Steps**

1. Add backend `GET /courses/{courseId}/quizzes`.
2. Add repository/service tests for history and latest attempt.
3. Add Flutter model/provider/page and route `/courses/:courseId/quizzes`.
4. Wire workbench history button after B lane checkpoint.
5. Implement `?regenerate=1` and `autoRegenerate` once-only behavior.
6. Add tests.

**Verification**

```bash
python -m pytest server/tests/test_quizzes.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/quiz test/features/course_workbench
```

**Done criteria**

- History endpoint and page work.
- Clicking history item opens `/quizzes/:quizId`.
- Regenerate button calls generate API.
- Ordinary quiz route does not auto-generate.

---

#### Lane D2：Delete impact, archive, restore

**Files likely to modify**

- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- 可新增 `client_flutter/lib/shared/models/course_management_models.dart`
- `client_flutter/lib/shared/providers/course_library_provider.dart`
- `client_flutter/lib/features/course_library/course_library_page.dart`
- `client_flutter/test/**`
- `server/tests/test_courses.py` or existing course tests。
- `docs/contracts/*.md`

**Steps**

1. Add ApiClient/CourseLessonApi wrappers for delete-impact/archive/restore.
2. Add delete impact model.
3. Fetch impact before delete dialog.
4. Implement partial success/failure delete.
5. Add archive/restore mutations and archived filter UI.
6. Add tests.

**Verification**

```bash
python -m pytest server/tests/test_courses.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_library
```

**Done criteria**

- Delete dialog shows real impact counts.
- Impact failure blocks delete.
- Partial failures visible.
- Archive hides course from default list.
- Archived-only filter shows archived courses.
- Restore returns course to default list.

---

## Phase 4：Regression, docs, and handoff

### Goal name

Regression, docs, and handoff

### Scope

所有并行 lanes 合并后，统一测试、contract 文档、手工验收说明和回归证明。

### Files likely to modify

- `docs/contracts/*.md`
- `docs/v2/**`
- `client_flutter/test/**`
- `server/tests/**`
- 小范围 bugfix 所需文件。

### Implementation steps

1. 确认所有 lane 已合并，无 high-conflict 文件未解决冲突。
2. 跑完整后端测试。
3. 跑 Flutter analyze/test。
4. 跑重点手工路径。
5. 更新 contract docs：所有新增字段/API、Non-goals、已知限制、手工验收路径。
6. 写 handoff：完成 goal、验证命令、失败/跳过项、风险和后续建议。
7. 确认没有实现 Non-goals。

### Tests to add/update

- 不新增大测试，除非发现覆盖缺口。
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

- 全量回归通过，或环境限制有明确记录。
- Contract docs 与实现一致。
- Handoff checklist 覆盖 upload、lesson progress、metadata、B 站、QA、quiz、review、library management。
- 没有 Non-goal 实现。

### Rollback/safety notes

- Phase 4 不新增功能。
- 回归修复小步提交。
- 文档和测试改动可独立 revert。

### Dependencies on earlier phases

依赖 Phase 1–3 lanes 完成并合并。

---

# Codex Goal Pack

## Goal 1: Baseline audit and lane lock

Objective:
- 锁定当前真实状态、API contract、测试基线和并行 lane ownership。

Constraints:
- 不实现功能。
- 不改 UI。
- 不删除测试。
- 不处理 Non-goals。
- 不重写后端架构。

Allowed files:
- `docs/contracts/*.md`
- `docs/v2/**`

Disallowed files:
- `client_flutter/lib/**`
- `server/api/**`
- `server/domain/**`
- `server/infra/**`
- `server/tasks/**`

Steps:
1. Inspect required frontend/backend files.
2. Record existing vs missing contract.
3. Record high-conflict files.
4. Run baseline tests.
5. Update docs with lane ownership and Non-goals.

Verification:
```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Acceptance:
- Contract gap and lane ownership documented.
- No production code changed.

Parallel group:
- Must complete before all other goals.

---

## Goal 2A: Backend contract foundation

Objective:
- 完成 `metaJson`、QA history message 字段、B 站 bind-existing contract 审计和测试。

Constraints:
- 不做前端 UI。
- 不实现 quiz history API here unless explicitly assigned to Goal 13A。
- `metaJson` optional and backward compatible。
- 不重写 repository 架构。
- 不删除 existing tests。

Allowed files:
- `server/schemas/requests.py`
- `server/domain/services/lessons.py`
- `server/domain/services/qa.py`
- `server/domain/repositories/interfaces.py`
- `server/infra/repositories/memory.py`
- `server/infra/repositories/memory_runtime.py`
- `server/infra/repositories/sqlalchemy.py`
- `server/tests/**`
- `docs/contracts/*.md`

Disallowed files:
- `client_flutter/lib/**`
- graph/export/report backend
- subjective grading code

Steps:
1. Add optional lesson `metaJson` create support.
2. Persist and return metaJson in memory and SQL repos.
3. Audit/extend QA session messages to include question.
4. Add B 站 bind-existing tests if missing.
5. Update docs.

Verification:
```bash
python -m pytest server/tests/test_lessons.py server/tests/test_qa.py server/tests/test_bilibili_sql_runtime.py server/tests/test_bilibili_url.py
```

Acceptance:
- Old lesson create requests still pass.
- New create request persists metaJson.
- QA history messages include question or tested fallback.
- B 站 bind-existing validation covered.

Parallel group:
- Can run after Goal 1 in parallel with Goals 2B, 2C, 2D, 2F.

---

## Goal 2B: Workbench upload and lesson metadata UI

Objective:
- 接入工作台课程/课时资源上传，并让新建课时表单字段进入 request。

Constraints:
- 不做 B 站 import wiring in this goal。
- 不重写 CourseImportProvider。
- 不绕过 ApiClient/CourseLessonApi。
- 不改变 CourseImportPage 行为。
- 不实现课时管理。

Allowed files:
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/resource_upload_models.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/providers/course_import_provider.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- `server/**` except docs
- lesson study files
- course library files
- graph/export/report pages

Steps:
1. Add/upload wrappers as needed.
2. Reuse or extract upload execution.
3. Wire course resource upload.
4. Add minimal lesson-scoped upload.
5. Include form metadata in create lesson request when backend contract is available.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
cd client_flutter && flutter test test/shared
```

Acceptance:
- Upload button performs upload-init/object PUT/upload-complete.
- Resources refresh in workbench.
- New lesson metadata request is formed correctly.
- Existing CourseImportPage tests pass.

Parallel group:
- Can run after Goal 1. Final metadata acceptance depends on Goal 2A.

---

## Goal 2C: Lesson progress persistence

Objective:
- 保存并恢复课时播放位置、当前讲义块和阅读进度。

Constraints:
- 不引入新状态管理框架。
- 不在 video listener 中每 tick 请求。
- 不阻塞视频播放。
- 不做 embedded QA/materials changes in this goal。
- 不改后端 progress API。

Allowed files:
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/test/**`

Disallowed files:
- `server/**`
- course workbench files
- course library files
- QA page files

Steps:
1. Add progress save state.
2. Restore progress on load.
3. Track player position locally.
4. Throttle playback saves.
5. Flush on pause/block jump/dispose.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

Acceptance:
- Pause then refresh restores position.
- Block jump persists block id.
- Saves are throttled.
- Save failure does not crash.

Parallel group:
- Can run after Goal 1 in parallel with Goals 2A, 2B, 2D, 2F.

---

## Goal 2D: Course library search/filter/sort

Objective:
- 接入课程库真实搜索、筛选、排序 provider 和 UI。

Constraints:
- 不做 delete-impact/archive/restore in this goal。
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
- backend course files unless tests prove API missing
- workbench files
- lesson study files
- theme files

Steps:
1. Add query state/provider.
2. Parameterize fetch.
3. Replace static filter fields.
4. Add debounce.
5. Add empty/error/retry/clear filters.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_library
```

Acceptance:
- Query params passed correctly.
- Search/filter/sort refresh list.
- Empty/error states visible.
- Continue learning still works.

Parallel group:
- Can run after Goal 1 in parallel with P0 frontend/backend goals.

---

## Goal 2F: Quiz submit to review polling closure

Objective:
- 完成 quiz submit run id 到 ReviewPage existing run polling 的闭环。

Constraints:
- 不从零实现 review 后端。
- 不自动 regenerate when existing run id exists。
- 不使用 20ms 生产轮询。
- 不做 quiz history/regenerate semantics here。
- 不改主观题判卷。

Allowed files:
- `client_flutter/lib/shared/providers/quiz_provider.dart`
- `client_flutter/lib/shared/providers/review_provider.dart`
- `client_flutter/lib/shared/providers/course_flow_providers.dart`
- `client_flutter/lib/features/quiz/quiz_page.dart`
- `client_flutter/lib/features/review/review_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- backend review service unless existing tests fail
- course_workbench_page.dart
- app_router.dart
- graph/export/report pages

Steps:
1. Add ReviewProvider poll existing run action.
2. Make ReviewPage consume query/CourseFlow run id.
3. Fetch course review after terminal status.
4. Guard against repeated polling.
5. Restore production interval.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/review test/features/quiz
python -m pytest server/tests/test_review_strategy.py server/tests/test_quiz_strategy.py
```

Acceptance:
- Non-null run id polls status then fetches review.
- Null run id normal-loads review.
- Manual regenerate still works.
- Complete task refreshes stats.

Parallel group:
- Can run after Goal 1 with other lanes.

---

## Goal 3B: Bilibili import from new lesson dialog

Objective:
- 将新建课时 B 站链接接入 preview/create bind-existing import/poll。

Constraints:
- 不重写 B 站后端。
- 不实现复杂多 P 课程导入器。
- Retry 不重复创建 lesson。
- 无登录态不得创建假成功。
- 不影响本地文件新建课时。

Allowed files:
- `client_flutter/lib/shared/models/bilibili_import_models.dart`
- `client_flutter/lib/shared/models/bilibili_import_state.dart`
- `client_flutter/lib/shared/providers/bilibili_import_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- Bilibili downloader internals unless tests prove bind-existing is broken
- lesson study files
- course library files
- theme files

Steps:
1. Extend import request model with bind-existing fields.
2. Add preview/auth/import UI state to new lesson dialog.
3. Create lesson once, then import with `lessonMode=bind_existing`.
4. Poll import status.
5. Refresh workbench/lesson after `imported`.
6. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
cd client_flutter && flutter test test/shared/bilibili_import_models_test.dart
python -m pytest server/tests/test_bilibili_sql_runtime.py server/tests/test_bilibili_url.py
```

Acceptance:
- URL can preview.
- Submit creates lesson and bind-existing import.
- Imported run refreshes primary video.
- Retry does not duplicate lesson.
- No-login state explicit.

Parallel group:
- Depends on Goal 2A and Goal 2B. Can run in parallel with Goals 3C, 3D, 3E, 3F.

---

## Goal 3C: Lesson embedded QA and materials MVP

Objective:
- 补课时内嵌 QA pair 和本节资料弹窗最小操作闭环。

Constraints:
- 不实现 full QA history sidebar。
- 不实现 streaming。
- 不假装非视频下载成功。
- 不做大 UI 重设计。
- 不破坏 progress persistence。

Allowed files:
- `client_flutter/lib/shared/models/lesson_study_state.dart`
- `client_flutter/lib/shared/providers/lesson_study_provider.dart`
- `client_flutter/lib/features/lesson_study/lesson_study_page.dart`
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/test/**`

Disallowed files:
- course_qa_page.dart
- course_workbench_page.dart
- backend files unless material delete/playback API fails

Steps:
1. Add QA exchange state.
2. Render user question and assistant answer.
3. Add failed exchange retry.
4. Add materials refresh/delete/mp4 preview.
5. Add tests.

Verification:
```bash
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/lesson_study
```

Acceptance:
- Embedded QA question/answer visible.
- Failed QA retry works.
- Materials delete refreshes list.
- mp4 preview gets playback URL.

Parallel group:
- Depends on Goal 2C. Can run with Goals 3B, 3D, 3E, 3F.

---

## Goal 3E: QA session history page

Objective:
- 接入课程级/课时级 QA session list、history messages 和 continue session。

Constraints:
- 不实现 streaming。
- 不做单资料 QA。
- 不混用 course/lesson scope。
- 不改 QA 生成策略。
- 不引入新状态管理框架。

Allowed files:
- `client_flutter/lib/core/network/api_client.dart`
- `client_flutter/lib/shared/models/handout_models.dart`
- `client_flutter/lib/shared/providers/*qa*`
- `client_flutter/lib/features/course_qa/course_qa_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- lesson_study_page.dart
- backend files unless Goal 2A left required work
- graph/report/export code

Steps:
1. Add `QaSessionModel`.
2. Extend message model with question/createdAt.
3. Add providers for sessions/messages.
4. Refactor CourseQaPage to provider-backed active session.
5. Send with active session id.
6. Add tests.

Verification:
```bash
python -m pytest server/tests/test_qa.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_qa
```

Acceptance:
- Session list loads.
- Clicking session shows history.
- Continue session reuses session id.
- New session separated.
- Scope does not leak.

Parallel group:
- Depends on Goal 2A. Can run with Goals 3B, 3C, 3D, 3F.

---

## Goal 3D: Course delete impact, archive, restore

Objective:
- 接入 delete-impact 确认、课程归档、查看归档和恢复。

Constraints:
- 不做物理删除。
- Impact 加载失败不得直接删除。
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
- workbench files
- lesson/quiz/review services
- theme files

Steps:
1. Add wrappers for delete-impact/archive/restore.
2. Add delete impact model.
3. Fetch impact before delete dialog.
4. Implement partial delete success/failure.
5. Add archive/restore mutations and archived filter UI.
6. Add tests.

Verification:
```bash
python -m pytest server/tests/test_courses.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_library
```

Acceptance:
- Delete dialog shows impact counts.
- Impact failure blocks delete.
- Partial failures visible.
- Archive/restore work with filters.

Parallel group:
- Depends on Goal 2D. Can run with Goals 3B, 3C, 3E, 3F.

---

## Goal 3F: Quiz history and regenerate semantics

Objective:
- 新增 quiz history API/page，并让重新生成课程测试真实触发 generate。

Constraints:
- 不实现主观题判卷。
- 不破坏 quiz detail/submit。
- 不在普通 quiz route 自动 generate。
- 不在 rebuild 中重复 generate。
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
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart` only after Workbench checkpoint
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- review service unless compile requires
- graph/report/export pages
- subjective grading implementation

Steps:
1. Add backend quiz history endpoint and tests.
2. Add Flutter model/provider/page and route.
3. Wire workbench history button.
4. Add `?regenerate=1` auto regenerate once-only behavior.
5. Add tests.

Verification:
```bash
python -m pytest server/tests/test_quizzes.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/quiz test/features/course_workbench
```

Acceptance:
- History endpoint/page work.
- History item opens quiz detail.
- Regenerate button calls generate API.
- Ordinary route does not auto-generate.

Parallel group:
- Depends on Goal 2F and Workbench checkpoint. Can run with Goals 3C/3D/3E if no router/workbench conflict.

---

## Goal 4B: Lesson management in workbench

Objective:
- 给 workbench 课时卡片增加管理入口：rename/delete/reorder/merge/split/set primary video。

Constraints:
- 不破坏继续学习入口。
- 合并只允许相邻课时。
- 不复制视频 resource。
- 不实现视频剪辑/转码。
- 不隐藏 stale artifacts。

Allowed files:
- `client_flutter/lib/shared/services/course_lesson_api.dart`
- `client_flutter/lib/shared/models/course_lesson_models.dart`
- `client_flutter/lib/shared/providers/course_workbench_provider.dart`
- `client_flutter/lib/features/course_workbench/course_workbench_page.dart`
- `client_flutter/test/**`
- `docs/contracts/*.md`

Disallowed files:
- lesson_study_page.dart
- Bilibili downloader/tasks
- graph/export/report pages

Steps:
1. Add lesson card management menu.
2. Implement rename/delete/reorder.
3. Implement adjacent merge.
4. Implement split dialog.
5. Implement set primary video dialog.
6. Display stale artifact warning.
7. Add tests.

Verification:
```bash
python -m pytest server/tests/test_lessons.py
cd client_flutter && flutter analyze
cd client_flutter && flutter test test/features/course_workbench
```

Acceptance:
- Rename/delete/reorder persist.
- Merge/split/set primary video work with error handling.
- Continue learning still works.

Parallel group:
- Depends on Goal 2B and should not run concurrently with Goal 3B or 3F if they modify `course_workbench_page.dart`.

---

## Goal 5: Final regression, docs, and handoff

Objective:
- 所有 lanes 合并后，跑全量回归、更新 contract/handoff，确认没有破坏旧链路。

Constraints:
- 不新增大功能。
- 不实现 Non-goals。
- 不删除失败测试来过关。
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
1. Resolve high-conflict file merges.
2. Run full backend tests.
3. Run Flutter analyze/test.
4. Run manual checklist.
5. Update docs/contracts and handoff.
6. Confirm Non-goals untouched.

Verification:
```bash
python -m pytest
cd client_flutter && flutter analyze
cd client_flutter && flutter test
```

Acceptance:
- Full regression passes or environment-only failures documented.
- Contract docs match implementation.
- Handoff checklist covers all main flows.
- No Non-goal implementation appears in diff.

Parallel group:
- Must run after all selected implementation goals are merged.
