# V2 Phase 1 Cao Le Bilibili Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Cao Le's independently deliverable V2 phase 1 backend scope: V2 Bilibili import contract, KnowLink-owned small Bilibili downloader, import state machine, resource import path, course/recommendation semantics, and handoff documentation.

**Architecture:** Keep KnowLink as the source of truth for import state through `bilibili_import_runs` plus existing `async_tasks`. Implement a small Bilidown-inspired `server/infra/bilibili` adapter layer for QR login, metadata, playurl, HTTP download, and ffmpeg merge, but do not embed Bilidown's app, database, or task system. Route APIs through `BilibiliService`; workers run `BilibiliImportRunner` and update repository state, object storage, and `course_resources`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, Alembic, pytest, Dramatiq, MinIO object storage, stdlib `urllib`, ffmpeg subprocess.

---

## Context And Constraints

- Work branch: `codex/v2-phase1-caole`.
- Approved design spec: `docs/superpowers/specs/2026-05-18-v2-phase1-caole-bilibili-design.md`.
- V2 owner boundary: `docs/v2/phase-plan.md` makes Cao Le responsible for Bilibili core backend, state machine, download/merge, errors, failure recovery, course/recommendation semantics, and handoff docs.
- Do not edit Flutter files; Zhu Chunwen owns front-end and Android UX.
- Do not assign Yang Caiyi complex backend, download, cancel, recovery, or state machine work; handoff docs should give her simple DTO/status/query/documentation boundaries.
- Use `canceled`, not `cancelled`.
- Use project virtualenv for verification, for example `.venv/bin/python -m pytest -s server/tests/test_bilibili_service.py -q`.
- If `.venv` lacks dependencies, run `.venv/bin/python -m pip install -e ".[dev]"` before tests.

## File Structure

Create:

- `docs/contracts/v2-bilibili-import-contract.md`: V2 Bilibili API, state, DTO, and error contract.
- `docs/v2/phase1-cao-le-handoff.md`: handoff document for Cao Le phase 1 backend scope.
- `server/infra/bilibili/__init__.py`: adapter exports.
- `server/infra/bilibili/models.py`: typed Bilibili domain dataclasses.
- `server/infra/bilibili/url.py`: URL parser for single video, multi-P, collection, bangumi.
- `server/infra/bilibili/client.py`: Bili API client and fakeable transport boundary.
- `server/infra/bilibili/downloader.py`: HTTP stream downloader with cancellation.
- `server/infra/bilibili/ffmpeg.py`: ffmpeg stream-copy merger with cancellation.
- `server/infra/db/models/bilibili.py`: SQLAlchemy models for QR sessions, auth sessions, import runs, and items.
- `server/tasks/bilibili_import.py`: import runner and task actor implementation.
- `alembic/versions/9f42a7d8c6b1_add_bilibili_import_tables.py`: migration for SQL runtime.
- `server/tests/test_bilibili_contract.py`: doc and contract freeze tests.
- `server/tests/test_bilibili_url.py`: URL parser and request/response schema tests.
- `server/tests/test_bilibili_service.py`: service-level state machine tests.
- `server/tests/test_bilibili_import_runner.py`: runner tests for download/merge/upload/resource import.
- `server/tests/test_bilibili_sql_runtime.py`: SQL repository/model persistence tests.

Modify:

- `docs/README.md`: add V2 Bilibili and phase 1 handoff links.
- `docs/contracts/api-contract.md`: add V2 Bilibili contract entry and point V1 stub text to V2 override.
- `docs/contracts/error-codes.md`: freeze V2 Bilibili errors.
- `server/api/deps.py`: build `BilibiliService` with repository, async task repo, dispatcher, object storage, and Bili adapters.
- `server/api/routers/bilibili.py`: add preview route and route real service responses.
- `server/domain/repositories/interfaces.py`: add Bilibili repository protocol and dispatcher method.
- `server/domain/services/bilibili.py`: replace 501 stub with service implementation.
- `server/infra/db/models/__init__.py`: export Bilibili SQL models.
- `server/infra/repositories/memory.py`: expose Bilibili repository methods.
- `server/infra/repositories/memory_runtime.py`: store QR sessions, auth session, import runs, and import items.
- `server/infra/repositories/sqlalchemy.py`: implement Bilibili repository methods.
- `server/infra/storage/object_store.py`: add `upload_file` to `ObjectStorage`, `MinioObjectStorage`, and `DemoObjectStorage`.
- `server/schemas/requests.py`: replace stub `BilibiliImportRequest` and add preview request.
- `server/schemas/responses.py`: expand Bilibili response DTOs and add preview DTOs.
- `server/tasks/dispatcher.py`: add `enqueue_bilibili_import` to dispatchers.
- `server/tasks/payloads.py`: add `BilibiliImportPayload`.
- `server/tasks/worker.py`: register `bilibili_import` Dramatiq actor.
- `server/seeds/course_catalog.json`: add V2 course catalog fields.
- `server/domain/services/courses.py`: add course detail and current-course switch semantics.
- `server/domain/services/recommendations.py`: add V2 catalog fields and next action in recommendation cards.
- `server/api/routers/courses.py`: add course detail/current/switch routes.
- `server/schemas/common.py`: keep `bilibili_import_run` entity support.
- `server/tests/test_api.py`: replace V1 Bilibili 501 expectations with V2 behavior tests.
- `server/tests/test_contract_freeze.py`: add V2 docs/contract freeze checks and keep V1 historical wording checks.
- `server/tests/test_scaffold_consistency.py`: add course catalog V2 field completeness checks.
- `server/tests/test_storage.py`: add `upload_file` coverage.

---

## Task 0: Baseline Environment And Focused Test Harness

**Files:**
- Read: `pyproject.toml`
- Read: `.venv/`

- [ ] **Step 1: Verify virtualenv dependencies**

Run:

```bash
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -c "import langchain_core, pytest, fastapi, sqlalchemy, minio"
```

Expected: exit 0. If dependencies install, do not commit environment changes.

- [ ] **Step 2: Run current focused baseline**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_api.py::test_bilibili_routes_require_auth server/tests/test_api.py::test_bilibili_reserved_routes_return_not_implemented server/tests/test_contract_freeze.py::test_bilibili_reserved_contract_is_aligned_across_docs -q
```

Expected before implementation: auth test passes; V1 stub tests pass on current baseline. After Task 4 these V1 stub assertions will be updated.

- [ ] **Step 3: Record baseline in final task notes**

No file change. Note the exact command and outcome in the implementer response.

**Commit:** no commit for Task 0.

---

## Task 1: V2 Contract, Error Codes, And Handoff Skeleton

**Files:**
- Create: `docs/contracts/v2-bilibili-import-contract.md`
- Create: `docs/v2/phase1-cao-le-handoff.md`
- Create: `server/tests/test_bilibili_contract.py`
- Modify: `docs/README.md`
- Modify: `docs/contracts/api-contract.md`
- Modify: `docs/contracts/error-codes.md`
- Modify: `server/tests/test_contract_freeze.py`

- [ ] **Step 1: Write failing contract tests**

Create `server/tests/test_bilibili_contract.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v2_bilibili_contract_is_linked_from_docs():
    docs_readme = text("docs/README.md")
    api_contract = text("docs/contracts/api-contract.md")

    assert "contracts/v2-bilibili-import-contract.md" in docs_readme
    assert "v2-bilibili-import-contract.md" in api_contract
    assert "phase1-cao-le-handoff.md" in docs_readme


def test_v2_bilibili_contract_freezes_states_and_paths():
    contract = text("docs/contracts/v2-bilibili-import-contract.md")

    for path in (
        "POST /api/v1/bilibili/auth/qr/sessions",
        "GET /api/v1/bilibili/auth/session",
        "POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview",
        "POST /api/v1/courses/{courseId}/resources/imports/bilibili",
        "GET /api/v1/bilibili-import-runs/{importRunId}/status",
        "POST /api/v1/bilibili-import-runs/{importRunId}/cancel",
    ):
        assert path in contract

    for status in (
        "pending",
        "fetching_metadata",
        "waiting_download",
        "downloading",
        "merging",
        "uploading",
        "imported",
        "failed",
        "recoverable",
        "canceled",
    ):
        assert f"`{status}`" in contract

    assert "cancelled" not in contract
    assert "`bilibili_import_run` 和 `async_tasks`" in contract


def test_v2_bilibili_error_codes_are_frozen():
    error_codes = text("docs/contracts/error-codes.md")

    for error_code in (
        "bilibili.auth_required",
        "bilibili.auth_expired",
        "bilibili.unsupported_url",
        "bilibili.access_denied",
        "bilibili.metadata_failed",
        "bilibili.playurl_failed",
        "bilibili.download_failed",
        "bilibili.merge_failed",
        "bilibili.upload_failed",
        "bilibili.import_failed",
        "bilibili.cancel_failed",
        "bilibili.run_not_found",
        "bilibili.selection_invalid",
    ):
        assert f"`{error_code}`" in error_codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py -q
```

Expected: FAIL because the V2 contract and handoff docs are not created or linked.

- [ ] **Step 3: Add V2 Bilibili contract**

Create `docs/contracts/v2-bilibili-import-contract.md` with these sections:

```markdown
# KnowLink V2 B站导入 Contract

日期：2026-05-18

## 1. 适用范围

本文冻结 V2 阶段一 B站真实导入的 API、DTO、状态机、错误码和验收口径。V1 的 `501 bilibili.not_implemented` stub 只保留为历史口径；V2 接通后以本文为准。

## 2. 真相源

B站导入状态以 KnowLink `bilibili_import_run` 和 `async_tasks` 为真相源，不引入 Bilidown 的数据库、任务状态或后台服务。KnowLink 实现一个模仿 Bilidown 关键做法的小型下载器。

## 3. API

### POST /api/v1/bilibili/auth/qr/sessions

响应 `data`：

```json
{
  "sessionId": "bili_qr_session_001",
  "status": "pending_scan",
  "qrCodeUrl": "https://passport.bilibili.com/qrcode-demo",
  "expiresAt": "2026-05-18T12:15:00+00:00"
}
```

### GET /api/v1/bilibili/auth/qr/sessions/{sessionId}

响应 `data` 与创建二维码会话一致，`status` 可取 `pending_scan`、`scanned`、`confirmed`、`expired`、`failed`。

### GET /api/v1/bilibili/auth/session

响应 `data`：

```json
{
  "loginStatus": "active",
  "userNickname": "KnowLink Demo",
  "expiresAt": "2026-05-18T14:00:00+00:00"
}
```

响应不得包含 `SESSDATA`、`bili_jct`、`DedeUserID` 或完整 cookie。

### DELETE /api/v1/bilibili/auth/session

响应 `data`：

```json
{
  "deleted": true
}
```

### POST /api/v1/courses/{courseId}/resources/imports/bilibili/preview

请求：

```json
{
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
}
```

响应 `data`：

```json
{
  "previewId": "bili_preview_9101",
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "sourceType": "multi_p",
  "title": "课程样例",
  "coverUrl": "https://i0.hdslb.com/bfs/archive/demo.jpg",
  "totalParts": 2,
  "parts": [
    {
      "partId": "cid-1001",
      "title": "P1 导论",
      "durationSec": 600,
      "cid": 1001,
      "pageNo": 1,
      "selectedByDefault": false
    },
    {
      "partId": "cid-1002",
      "title": "P2 例题",
      "durationSec": 900,
      "cid": 1002,
      "pageNo": 2,
      "selectedByDefault": true
    }
  ],
  "defaultSelectionMode": "current_part"
}
```

### POST /api/v1/courses/{courseId}/resources/imports/bilibili

请求：

```json
{
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "selectionMode": "current_part",
  "selectedPartIds": ["cid-1002"],
  "qualityPreference": "android_safe"
}
```

响应 `data`：

```json
{
  "taskId": 7201,
  "status": "queued",
  "nextAction": "poll",
  "entity": {
    "type": "bilibili_import_run",
    "id": 9101
  }
}
```

### GET /api/v1/courses/{courseId}/resources/imports/bilibili

响应 `data.items[]` 字段至少包含 `importRunId`、`courseId`、`sourceUrl`、`sourceType`、`status`、`progressPct`、`stage`、`taskId`、`resourceIds`、`errorCode`、`failureReason`、`recoverable`。

### GET /api/v1/bilibili-import-runs/{importRunId}/status

响应 `data`：

```json
{
  "importRunId": 9101,
  "courseId": 101,
  "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
  "sourceType": "multi_p",
  "status": "downloading",
  "progressPct": 45,
  "stage": "downloading",
  "taskId": 7201,
  "resourceIds": [],
  "nextAction": "poll",
  "errorCode": null,
  "failureReason": null,
  "recoverable": false
}
```

### POST /api/v1/bilibili-import-runs/{importRunId}/cancel

响应 `data`：

```json
{
  "taskId": 7201,
  "status": "canceled",
  "nextAction": "none",
  "entity": {
    "type": "bilibili_import_run",
    "id": 9101
  }
}
```

## 4. 状态机

状态固定为：`pending`、`fetching_metadata`、`waiting_download`、`downloading`、`merging`、`uploading`、`imported`、`failed`、`recoverable`、`canceled`。

映射：

| bilibili_import_run.status | async_tasks.status |
|---|---|
| `pending` | `queued` |
| `fetching_metadata` | `running` |
| `waiting_download` | `queued` |
| `downloading` | `running` |
| `merging` | `running` |
| `uploading` | `running` |
| `imported` | `succeeded` |
| `failed` | `failed` |
| `recoverable` | `failed` |
| `canceled` | `canceled` |

## 5. 错误码

错误码以 `docs/contracts/error-codes.md` 的 Bilibili 节为准。

## 6. 取消与清理

取消必须停止尚未完成的 HTTP 下载和 ffmpeg 子进程，删除临时视频、音频和合并输出。已完成 `imported` 的导入不能取消。
```

- [ ] **Step 4: Add handoff skeleton**

Create `docs/v2/phase1-cao-le-handoff.md`:

```markdown
# V2 阶段一曹乐后端交接文档

日期：2026-05-18

## 1. 曹乐独立交付范围

- B站导入核心后端、状态机、错误码、取消语义和任务链路。
- 小型 B站下载器边界：QR 登录、元数据、playurl、下载、ffmpeg 合并、对象存储上传。
- 课程库字段、推荐规则、推荐理由和多课程基础语义。
- 复杂版面增强最低验收标准。

## 2. 非曹乐独立交付范围

- Flutter 页面、Android 真机录屏、页面视觉优化由朱春雯负责。
- 简单接口文档整理、状态样例、测试数据整理和联调记录由杨彩艺在曹乐冻结字段后负责。

## 3. 前端联调速查

前端只读取二维码、登录状态、预览、任务进度、失败原因和取消结果。前端不得接触 B站 cookie。

## 4. 辅助后端边界

杨彩艺可以整理状态查询、任务列表展示、字段说明和测试样例，不负责下载、ffmpeg、取消副作用、任务恢复和复杂状态机。

## 5. 接口入口

详见 `docs/contracts/v2-bilibili-import-contract.md`。

## 6. 状态与错误码

状态统一使用 `canceled`，错误码以 `docs/contracts/error-codes.md` 为准。

## 7. 验收证据

曹乐独立验收至少包含后端测试、固定预览样例、导入任务状态返回、课程资源入库记录和本地运行命令。

## 8. 本地命令

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py server/tests/test_bilibili_url.py server/tests/test_bilibili_service.py server/tests/test_bilibili_import_runner.py -q
```

## 9. 风险

B站风控、账号权限、地区限制、ffmpeg 缺失和对象存储不可达会影响真实联调；单元测试使用 fake adapter 保证后端状态机稳定。
```

- [ ] **Step 5: Link docs and freeze error codes**

Modify `docs/README.md` V2/Contract sections to include:

```markdown
- [contracts/v2-bilibili-import-contract.md](./contracts/v2-bilibili-import-contract.md)：V2 阶段一 B站真实导入 API、状态机、错误码和取消语义。
- [v2/phase1-cao-le-handoff.md](./v2/phase1-cao-le-handoff.md)：曹乐阶段一后端交接说明。
```

Modify `docs/contracts/api-contract.md` section `1.3 V2 contract 过渡口径` to include:

```markdown
- V2 B站真实导入 contract 已单独冻结在 [v2-bilibili-import-contract.md](./v2-bilibili-import-contract.md)；该文档覆盖本文 B站 V1 `501` stub 的历史口径。
```

Modify `docs/contracts/error-codes.md` Bilibili section so every V2 code from Step 1 appears as a bullet with a one-line Chinese explanation.

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py server/tests/test_contract_freeze.py::test_bilibili_reserved_contract_is_aligned_across_docs -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add docs/contracts/v2-bilibili-import-contract.md docs/v2/phase1-cao-le-handoff.md docs/README.md docs/contracts/api-contract.md docs/contracts/error-codes.md server/tests/test_bilibili_contract.py server/tests/test_contract_freeze.py
git commit -m "docs(v2): 冻结B站导入契约和交接口径"
```

---

## Task 2: Bilibili Schemas, Domain Models, And URL Parsing

**Files:**
- Create: `server/infra/bilibili/__init__.py`
- Create: `server/infra/bilibili/models.py`
- Create: `server/infra/bilibili/url.py`
- Create: `server/tests/test_bilibili_url.py`
- Modify: `server/schemas/requests.py`
- Modify: `server/schemas/responses.py`

- [ ] **Step 1: Write failing URL and schema tests**

Create `server/tests/test_bilibili_url.py`:

```python
import pytest
from pydantic import ValidationError

from server.infra.bilibili.url import BilibiliUrlKind, parse_bilibili_url
from server.schemas.requests import BilibiliImportRequest, BilibiliPreviewRequest
from server.schemas.responses import BilibiliImportRunStatusData, BilibiliPreviewData


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("https://www.bilibili.com/video/BV1xx411c7mD/", BilibiliUrlKind.VIDEO),
        ("https://www.bilibili.com/video/BV1xx411c7mD?p=2", BilibiliUrlKind.MULTI_P),
        ("https://space.bilibili.com/123/channel/collectiondetail?sid=456", BilibiliUrlKind.COLLECTION),
        ("https://www.bilibili.com/bangumi/play/ep123456", BilibiliUrlKind.BANGUMI),
        ("https://b23.tv/BV1xx411c7mD", BilibiliUrlKind.SHORT),
    ],
)
def test_parse_supported_bilibili_urls(url, kind):
    parsed = parse_bilibili_url(url)

    assert parsed.kind == kind
    assert parsed.original_url == url


def test_parse_rejects_unsupported_url():
    with pytest.raises(ValueError, match="unsupported Bilibili URL"):
        parse_bilibili_url("https://example.com/video/BV1xx411c7mD")


def test_preview_request_uses_source_url_and_import_request_keeps_selection():
    preview = BilibiliPreviewRequest(sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD?p=2")
    payload = BilibiliImportRequest(
        sourceUrl=preview.source_url,
        selectionMode="selected_parts",
        selectedPartIds=["cid-1002"],
        qualityPreference="android_safe",
    )

    assert preview.source_url.endswith("p=2")
    assert payload.selection_mode == "selected_parts"
    assert payload.selected_part_ids == ["cid-1002"]


def test_import_request_rejects_empty_selected_parts_for_selected_mode():
    with pytest.raises(ValidationError):
        BilibiliImportRequest(
            sourceUrl="https://www.bilibili.com/video/BV1xx411c7mD",
            selectionMode="selected_parts",
            selectedPartIds=[],
        )


def test_preview_and_status_response_shapes_use_camel_case():
    preview = BilibiliPreviewData(
        preview_id="bili_preview_1",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="video",
        title="导入样例",
        cover_url=None,
        total_parts=1,
        parts=[
            {
                "partId": "cid-1001",
                "title": "P1",
                "durationSec": 600,
                "cid": 1001,
                "pageNo": 1,
                "selectedByDefault": True,
            }
        ],
        default_selection_mode="current_part",
    )
    status = BilibiliImportRunStatusData(
        import_run_id=9101,
        course_id=101,
        status="downloading",
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="video",
        progress_pct=42,
        stage="downloading",
        task_id=7201,
        resource_ids=[],
        next_action="poll",
        error_code=None,
        failure_reason=None,
        recoverable=False,
    )

    assert preview.model_dump(by_alias=True)["previewId"] == "bili_preview_1"
    assert status.model_dump(by_alias=True)["progressPct"] == 42
    assert "videoUrl" not in status.model_dump(by_alias=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_url.py -q
```

Expected: FAIL because `server.infra.bilibili` and new DTOs do not exist.

- [ ] **Step 3: Implement Bilibili dataclasses**

Create `server/infra/bilibili/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BilibiliSourceType(StrEnum):
    VIDEO = "video"
    MULTI_P = "multi_p"
    COLLECTION = "collection"
    BANGUMI = "bangumi"
    SHORT = "short"


@dataclass(frozen=True)
class BilibiliPart:
    part_id: str
    title: str
    duration_sec: int
    cid: int | None = None
    aid: int | None = None
    page_no: int | None = None
    selected_by_default: bool = False

    def to_api(self) -> dict[str, object]:
        return {
            "partId": self.part_id,
            "title": self.title,
            "durationSec": self.duration_sec,
            "cid": self.cid,
            "aid": self.aid,
            "pageNo": self.page_no,
            "selectedByDefault": self.selected_by_default,
        }


@dataclass(frozen=True)
class BilibiliPreview:
    preview_id: str
    source_url: str
    source_type: str
    title: str
    cover_url: str | None
    total_parts: int
    parts: list[BilibiliPart] = field(default_factory=list)
    default_selection_mode: str = "current_part"

    def to_api(self) -> dict[str, object]:
        return {
            "previewId": self.preview_id,
            "sourceUrl": self.source_url,
            "sourceType": self.source_type,
            "title": self.title,
            "coverUrl": self.cover_url,
            "totalParts": self.total_parts,
            "parts": [part.to_api() for part in self.parts],
            "defaultSelectionMode": self.default_selection_mode,
        }
```

- [ ] **Step 4: Implement URL parser**

Create `server/infra/bilibili/url.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, urlparse


class BilibiliUrlKind(StrEnum):
    VIDEO = "video"
    MULTI_P = "multi_p"
    COLLECTION = "collection"
    BANGUMI = "bangumi"
    SHORT = "short"


@dataclass(frozen=True)
class ParsedBilibiliUrl:
    original_url: str
    kind: BilibiliUrlKind
    bvid: str | None = None
    page_no: int | None = None
    collection_id: str | None = None
    episode_id: str | None = None


def parse_bilibili_url(value: str) -> ParsedBilibiliUrl:
    url = value.strip()
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    query = parse_qs(parsed.query)

    if host == "b23.tv":
        return ParsedBilibiliUrl(original_url=url, kind=BilibiliUrlKind.SHORT)

    if not host.endswith("bilibili.com"):
        raise ValueError("unsupported Bilibili URL")

    if path.startswith("video/"):
        bvid = path.split("/", 1)[1].split("/", 1)[0]
        page_no = _int_value(query.get("p", [None])[0])
        return ParsedBilibiliUrl(
            original_url=url,
            kind=BilibiliUrlKind.MULTI_P if page_no and page_no > 1 else BilibiliUrlKind.VIDEO,
            bvid=bvid,
            page_no=page_no,
        )

    if "collectiondetail" in path:
        sid = query.get("sid", [None])[0]
        return ParsedBilibiliUrl(original_url=url, kind=BilibiliUrlKind.COLLECTION, collection_id=sid)

    if path.startswith("bangumi/play/"):
        episode_id = path.rsplit("/", 1)[-1]
        return ParsedBilibiliUrl(original_url=url, kind=BilibiliUrlKind.BANGUMI, episode_id=episode_id)

    raise ValueError("unsupported Bilibili URL")


def _int_value(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
```

Create `server/infra/bilibili/__init__.py`:

```python
from server.infra.bilibili.models import BilibiliPart, BilibiliPreview, BilibiliSourceType
from server.infra.bilibili.url import BilibiliUrlKind, ParsedBilibiliUrl, parse_bilibili_url

__all__ = [
    "BilibiliPart",
    "BilibiliPreview",
    "BilibiliSourceType",
    "BilibiliUrlKind",
    "ParsedBilibiliUrl",
    "parse_bilibili_url",
]
```

- [ ] **Step 5: Replace Bilibili request DTOs**

Modify `server/schemas/requests.py`:

```python
class BilibiliPreviewRequest(CamelModel):
    source_url: str = Field(min_length=1)


class BilibiliImportRequest(CamelModel):
    source_url: str = Field(min_length=1)
    selection_mode: Literal["current_part", "all_parts", "selected_parts"] = "current_part"
    selected_part_ids: list[str] = []
    quality_preference: Literal["android_safe"] = "android_safe"

    @field_validator("selected_part_ids")
    @classmethod
    def _selected_part_ids_must_not_be_blank(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @field_validator("selected_part_ids")
    @classmethod
    def _selected_mode_requires_part_ids(cls, value: list[str], info):
        if info.data.get("selection_mode") == "selected_parts" and not value:
            raise ValueError("selectedPartIds is required when selectionMode is selected_parts.")
        return value
```

If Pydantic field validator order prevents `selection_mode` access, replace with `@model_validator(mode="after")`:

```python
    @model_validator(mode="after")
    def _selected_mode_requires_part_ids(self):
        self.selected_part_ids = [item.strip() for item in self.selected_part_ids if item.strip()]
        if self.selection_mode == "selected_parts" and not self.selected_part_ids:
            raise ValueError("selectedPartIds is required when selectionMode is selected_parts.")
        return self
```

- [ ] **Step 6: Expand Bilibili response DTOs**

Modify `server/schemas/responses.py` by replacing Bilibili DTOs with:

```python
class BilibiliPreviewPart(CamelModel):
    part_id: str
    title: str
    duration_sec: int
    cid: int | None = None
    aid: int | None = None
    page_no: int | None = None
    selected_by_default: bool = False


class BilibiliPreviewData(CamelModel):
    preview_id: str
    source_url: str
    source_type: str
    title: str
    cover_url: str | None = None
    total_parts: int
    parts: list[BilibiliPreviewPart]
    default_selection_mode: str


class BilibiliImportRunSummary(CamelModel):
    import_run_id: int
    course_id: int
    status: str
    source_url: str
    source_type: str
    progress_pct: int
    stage: str | None = None
    task_id: int | None = None
    resource_ids: list[int] = []
    error_code: str | None = None
    failure_reason: str | None = None
    recoverable: bool = False


class BilibiliImportListData(CamelModel):
    items: list[BilibiliImportRunSummary]


class BilibiliImportRunStatusData(BilibiliImportRunSummary):
    next_action: str | None = None


class BilibiliAuthQrSessionData(CamelModel):
    session_id: str
    status: str
    qr_code_url: str | None = None
    expires_at: datetime | None = None


class BilibiliAuthSessionData(CamelModel):
    login_status: str
    user_nickname: str | None = None
    expires_at: datetime | None = None


class BilibiliAuthSessionDeleteData(CamelModel):
    deleted: bool
```

- [ ] **Step 7: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_url.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add server/infra/bilibili server/schemas/requests.py server/schemas/responses.py server/tests/test_bilibili_url.py
git commit -m "feat(api): 增加B站导入DTO和URL解析"
```

---

## Task 3: Object Storage Upload File Boundary

**Files:**
- Modify: `server/infra/storage/object_store.py`
- Modify: `server/tests/test_storage.py`

- [ ] **Step 1: Write failing storage upload tests**

Append to `server/tests/test_storage.py`:

```python
def test_demo_object_storage_upload_file_records_file_size(tmp_path):
    from server.infra.storage.object_store import DemoObjectStorage

    source = tmp_path / "demo.mp4"
    source.write_bytes(b"video-bytes")
    storage = DemoObjectStorage()

    stat = storage.upload_file("raw/1/101/bilibili/9101/demo.mp4", source, content_type="video/mp4")

    assert stat.size_bytes == len(b"video-bytes")
    assert stat.checksum_required is False


def test_minio_object_storage_upload_file_calls_fput_object(tmp_path):
    source = tmp_path / "demo.mp4"
    source.write_bytes(b"video-bytes")

    class UploadingMinioClient(RecordingMinioClient):
        def __init__(self):
            super().__init__()
            self.fput_call = None

        def fput_object(self, bucket_name, object_name, file_path, *, content_type=None, metadata=None):
            self.fput_call = {
                "bucketName": bucket_name,
                "objectName": object_name,
                "filePath": file_path,
                "contentType": content_type,
                "metadata": metadata,
            }
            return SimpleNamespace(etag="etag-upload")

    client = UploadingMinioClient()
    storage = MinioObjectStorage(client=client, bucket_name="knowlink")

    stat = storage.upload_file(
        "raw/1/101/bilibili/9101/demo.mp4",
        source,
        content_type="video/mp4",
        metadata={"x-amz-meta-source-type": "bilibili"},
    )

    assert client.fput_call["bucketName"] == "knowlink"
    assert client.fput_call["objectName"] == "raw/1/101/bilibili/9101/demo.mp4"
    assert client.fput_call["contentType"] == "video/mp4"
    assert stat.etag == "etag-upload"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_storage.py::test_demo_object_storage_upload_file_records_file_size server/tests/test_storage.py::test_minio_object_storage_upload_file_calls_fput_object -q
```

Expected: FAIL because `upload_file` is not defined.

- [ ] **Step 3: Implement `upload_file`**

Modify `server/infra/storage/object_store.py`:

```python
    def upload_file(
        self,
        object_key: str,
        source_path: str | Path,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectStat:
        raise NotImplementedError
```

Add to `MinioObjectStorage`:

```python
    def upload_file(
        self,
        object_key: str,
        source_path: str | Path,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectStat:
        try:
            result = self.client.fput_object(
                self.bucket_name,
                object_key,
                str(source_path),
                content_type=content_type,
                metadata=dict(metadata or {}),
            )
        except Exception as exc:  # pragma: no cover - defensive adapter boundary.
            raise ObjectStorageUnavailable("Failed to upload object") from exc
        return ObjectStat(
            size_bytes=Path(source_path).stat().st_size,
            etag=getattr(result, "etag", None),
            metadata=dict(metadata or {}),
            checksum_required=False,
        )
```

Add to `DemoObjectStorage`:

```python
    def upload_file(
        self,
        object_key: str,
        source_path: str | Path,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectStat:
        return ObjectStat(
            size_bytes=Path(source_path).stat().st_size,
            metadata=dict(metadata or {}),
            checksum_required=False,
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_storage.py::test_demo_object_storage_upload_file_records_file_size server/tests/test_storage.py::test_minio_object_storage_upload_file_calls_fput_object -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add server/infra/storage/object_store.py server/tests/test_storage.py
git commit -m "feat(storage): 支持后端任务上传文件"
```

---

## Task 4: Bilibili Persistence In Memory And SQL Runtime

**Files:**
- Create: `server/infra/db/models/bilibili.py`
- Create: `alembic/versions/9f42a7d8c6b1_add_bilibili_import_tables.py`
- Create: `server/tests/test_bilibili_sql_runtime.py`
- Modify: `server/domain/repositories/interfaces.py`
- Modify: `server/infra/db/models/__init__.py`
- Modify: `server/infra/repositories/memory.py`
- Modify: `server/infra/repositories/memory_runtime.py`
- Modify: `server/infra/repositories/sqlalchemy.py`

- [ ] **Step 1: Write failing repository tests**

Create `server/tests/test_bilibili_sql_runtime.py`:

```python
from datetime import timedelta

from server.infra.db.base import Base, utcnow
from server.infra.db.models import BilibiliImportRun, BilibiliQrSession
from server.infra.db.session import create_engine_and_sessionmaker
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


def test_memory_bilibili_import_run_lifecycle():
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Bili course",
        entry_type="manual_import",
        goal_text="导入 B站",
        preferred_style="balanced",
    )

    qr = repo.create_bilibili_qr_session(
        session_id="qr-1",
        status="pending_scan",
        qr_code_url="https://qr.test",
        expires_at=utcnow() + timedelta(minutes=5),
    )
    run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="video",
        preview_json={"title": "Bili demo"},
        selection_json={"selectionMode": "current_part"},
    )
    updated = repo.update_bilibili_import_run(
        run["importRunId"],
        status="downloading",
        progress_pct=40,
        stage="downloading",
        task_id=7201,
    )

    assert qr["sessionId"] == "qr-1"
    assert updated["status"] == "downloading"
    assert updated["progressPct"] == 40
    assert repo.list_bilibili_import_runs(course_id=course["courseId"])[0]["importRunId"] == run["importRunId"]


def test_sql_bilibili_models_are_mapped_and_repository_round_trips(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'runtime.db'}"
    engine, SessionLocal = create_engine_and_sessionmaker(database_url)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        repo = SqlAlchemyRuntimeRepository(session)
        course = repo.create_course(
            title="Bili SQL course",
            entry_type="manual_import",
            goal_text="导入 B站",
            preferred_style="balanced",
        )
        qr = repo.create_bilibili_qr_session(
            session_id="qr-sql-1",
            status="pending_scan",
            qr_code_url="https://qr.test",
            expires_at=utcnow() + timedelta(minutes=5),
        )
        run = repo.create_bilibili_import_run(
            course_id=course["courseId"],
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            source_type="video",
            preview_json={"title": "Bili demo"},
            selection_json={"selectionMode": "current_part"},
        )
        updated = repo.update_bilibili_import_run(
            run["importRunId"],
            status="imported",
            progress_pct=100,
            stage="imported",
            resource_ids=[501],
        )

        assert session.query(BilibiliQrSession).count() == 1
        assert session.query(BilibiliImportRun).count() == 1
        assert qr["sessionId"] == "qr-sql-1"
        assert updated["resourceIds"] == [501]
    finally:
        session.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_sql_runtime.py -q
```

Expected: FAIL because Bilibili models and repository methods do not exist.

- [ ] **Step 3: Add repository protocol methods**

Modify `server/domain/repositories/interfaces.py`:

```python
class BilibiliImportRepository(Protocol):
    def create_bilibili_qr_session(
        self,
        *,
        session_id: str,
        status: str,
        qr_code_url: str | None,
        expires_at: datetime | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def get_bilibili_qr_session(self, session_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def update_bilibili_qr_session(self, session_id: str, **changes: Any) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_bilibili_auth_session(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def save_bilibili_auth_session(
        self,
        *,
        login_status: str,
        user_nickname: str | None,
        expires_at: datetime | None,
        cookies_json: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def delete_bilibili_auth_session(self) -> bool:
        raise NotImplementedError

    def create_bilibili_import_run(
        self,
        *,
        course_id: int,
        source_url: str,
        source_type: str,
        preview_json: dict[str, Any],
        selection_json: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def get_bilibili_import_run(self, import_run_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    def list_bilibili_import_runs(self, *, course_id: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def update_bilibili_import_run(self, import_run_id: int, **changes: Any) -> dict[str, Any] | None:
        raise NotImplementedError
```

- [ ] **Step 4: Add SQLAlchemy models and export them**

Create `server/infra/db/models/bilibili.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.infra.db.base import Base, ID_TYPE, JSON_TYPE, TimestampMixin


class BilibiliQrSession(Base, TimestampMixin):
    __tablename__ = "bilibili_qr_sessions"
    __table_args__ = (Index("ix_bilibili_qr_sessions_status", "status"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    qr_code_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)


class BilibiliAuthSession(Base, TimestampMixin):
    __tablename__ = "bilibili_auth_sessions"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    login_status: Mapped[str] = mapped_column(String(50), nullable=False)
    user_nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cookies_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class BilibiliImportRun(Base, TimestampMixin):
    __tablename__ = "bilibili_import_runs"
    __table_args__ = (
        Index("ix_bilibili_import_runs_course_status", "course_id", "status"),
        Index("ix_bilibili_import_runs_task", "task_id"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("async_tasks.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preview_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    selection_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    resource_ids_json: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    temp_dir: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recoverable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BilibiliImportItem(Base, TimestampMixin):
    __tablename__ = "bilibili_import_items"
    __table_args__ = (Index("ix_bilibili_import_items_run_sort", "import_run_id", "sort_no"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("bilibili_import_runs.id"), nullable=False)
    part_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cid: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    aid: Mapped[int | None] = mapped_column(ID_TYPE, nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("course_resources.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
```

Modify `server/infra/db/models/__init__.py` to import/export `BilibiliAuthSession`, `BilibiliImportItem`, `BilibiliImportRun`, `BilibiliQrSession`.

- [ ] **Step 5: Add Alembic migration**

Create `alembic/versions/9f42a7d8c6b1_add_bilibili_import_tables.py` with `down_revision = "0d4ea7c5f2a9"` and create/drop the four tables and indexes matching Step 4.

- [ ] **Step 6: Implement memory repository methods**

Modify `RuntimeStore` with fields:

```python
bilibili_qr_sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
bilibili_auth_session: dict[str, Any] | None = None
bilibili_import_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
bilibili_import_runs_by_course: dict[int, list[int]] = field(default_factory=dict)
```

Add counter:

```python
"bilibili_import_run": 9100,
```

Add methods on `MemoryScaffoldRepository` that return camelCase dictionaries with keys from tests. `create_bilibili_import_run` must set `status="pending"`, `progressPct=0`, `stage="pending"`, `resourceIds=[]`, and `recoverable=False`.

- [ ] **Step 7: Implement SQL repository methods**

Modify `server/infra/repositories/sqlalchemy.py` to import Bilibili models and add methods matching the protocol. Use helper conversion:

```python
def _bilibili_import_run_dict(run: BilibiliImportRun) -> dict[str, Any]:
    return {
        "importRunId": run.id,
        "courseId": run.course_id,
        "taskId": run.task_id,
        "sourceUrl": run.source_url,
        "sourceType": run.source_type,
        "status": run.status,
        "progressPct": run.progress_pct,
        "stage": run.stage,
        "preview": run.preview_json,
        "selection": run.selection_json,
        "resourceIds": list(run.resource_ids_json or []),
        "errorCode": run.error_code,
        "failureReason": run.failure_reason,
        "recoverable": run.recoverable,
        "finishedAt": run.finished_at,
    }
```

When `update_bilibili_import_run` receives `resource_ids`, write to `resource_ids_json`; when it receives terminal status, set `finished_at=utcnow()`.

- [ ] **Step 8: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_sql_runtime.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
git add server/domain/repositories/interfaces.py server/infra/db/models/bilibili.py server/infra/db/models/__init__.py server/infra/repositories/memory.py server/infra/repositories/memory_runtime.py server/infra/repositories/sqlalchemy.py alembic/versions/9f42a7d8c6b1_add_bilibili_import_tables.py server/tests/test_bilibili_sql_runtime.py
git commit -m "feat(domain): 增加B站导入运行时仓储"
```

---

## Task 5: Bilibili Service, Auth, Preview, Import, Status, Cancel

**Files:**
- Create: `server/tests/test_bilibili_service.py`
- Modify: `server/domain/services/bilibili.py`
- Modify: `server/api/routers/bilibili.py`
- Modify: `server/api/deps.py`
- Modify: `server/tests/test_api.py`

- [ ] **Step 1: Write failing service tests**

Create `server/tests/test_bilibili_service.py`:

```python
from datetime import timedelta

import pytest

from server.domain.services.bilibili import BilibiliService
from server.domain.services.errors import ServiceError
from server.infra.bilibili.models import BilibiliPart, BilibiliPreview
from server.infra.db.base import utcnow
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore


class FakeBiliClient:
    def create_qr_session(self):
        return {
            "sessionId": "qr-1",
            "status": "pending_scan",
            "qrCodeUrl": "https://qr.test/1",
            "expiresAt": utcnow() + timedelta(minutes=5),
        }

    def get_qr_session(self, session_id):
        return {
            "sessionId": session_id,
            "status": "pending_scan",
            "qrCodeUrl": "https://qr.test/1",
            "expiresAt": utcnow() + timedelta(minutes=5),
        }

    def get_auth_session(self, saved):
        return {"loginStatus": "active", "userNickname": "Bili User", "expiresAt": utcnow() + timedelta(hours=2)}

    def preview(self, source_url, cookies):
        return BilibiliPreview(
            preview_id="bili_preview_1",
            source_url=source_url,
            source_type="multi_p",
            title="Bili demo",
            cover_url=None,
            total_parts=2,
            parts=[
                BilibiliPart(part_id="cid-1001", title="P1", duration_sec=600, cid=1001, page_no=1),
                BilibiliPart(part_id="cid-1002", title="P2", duration_sec=900, cid=1002, page_no=2, selected_by_default=True),
            ],
            default_selection_mode="current_part",
        )


class RecordingDispatcher:
    def __init__(self):
        self.calls = []

    def enqueue_bilibili_import(self, *, task_id, payload):
        self.calls.append({"taskId": task_id, "payload": payload})


def build_service():
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Bili course",
        entry_type="manual_import",
        goal_text="导入 B站",
        preferred_style="balanced",
    )
    repo.save_bilibili_auth_session(
        login_status="active",
        user_nickname="Bili User",
        expires_at=utcnow() + timedelta(hours=2),
        cookies_json={"SESSDATA": "hidden", "bili_jct": "csrf"},
    )
    dispatcher = RecordingDispatcher()
    service = BilibiliService(
        courses=repo,
        bilibili=repo,
        async_tasks=repo,
        task_dispatcher=dispatcher,
        bili_client=FakeBiliClient(),
    )
    return service, repo, dispatcher, course["courseId"]


def test_auth_session_hides_cookies():
    service, _, _, _ = build_service()

    session = service.get_auth_session()

    assert session["loginStatus"] == "active"
    assert "SESSDATA" not in str(session)
    assert "bili_jct" not in str(session)


def test_preview_requires_course_and_returns_parts():
    service, _, _, course_id = build_service()

    preview = service.preview_import(
        course_id=course_id,
        source_url="https://www.bilibili.com/video/BV1xx411c7mD?p=2",
    )

    assert preview["sourceType"] == "multi_p"
    assert preview["parts"][1]["selectedByDefault"] is True


def test_create_import_creates_run_task_and_enqueue_payload():
    service, repo, dispatcher, course_id = build_service()

    trigger = service.create_import(
        course_id=course_id,
        source_url="https://www.bilibili.com/video/BV1xx411c7mD?p=2",
        selection_mode="current_part",
        selected_part_ids=[],
        quality_preference="android_safe",
        idempotency_key="bili-import-1",
    )
    run_id = trigger["entity"]["id"]
    run = repo.get_bilibili_import_run(run_id)

    assert trigger["entity"] == {"type": "bilibili_import_run", "id": run_id}
    assert trigger["status"] == "queued"
    assert run["status"] == "pending"
    assert dispatcher.calls[0]["payload"]["importRunId"] == run_id


def test_cancel_import_marks_run_and_task_canceled():
    service, repo, _, course_id = build_service()
    trigger = service.create_import(
        course_id=course_id,
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        selection_mode="current_part",
        selected_part_ids=[],
        quality_preference="android_safe",
        idempotency_key="bili-import-cancel",
    )
    run_id = trigger["entity"]["id"]

    canceled = service.cancel_import(import_run_id=run_id, idempotency_key="cancel-1")
    run = repo.get_bilibili_import_run(run_id)

    assert canceled["status"] == "canceled"
    assert run["status"] == "canceled"


def test_cancel_import_rejects_imported_run():
    service, repo, _, course_id = build_service()
    trigger = service.create_import(
        course_id=course_id,
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        selection_mode="current_part",
        selected_part_ids=[],
        quality_preference="android_safe",
        idempotency_key="bili-import-imported",
    )
    run_id = trigger["entity"]["id"]
    repo.update_bilibili_import_run(run_id, status="imported", progress_pct=100, stage="imported", resource_ids=[501])

    with pytest.raises(ServiceError) as exc_info:
        service.cancel_import(import_run_id=run_id, idempotency_key="cancel-imported")

    assert exc_info.value.error_code == "bilibili.cancel_failed"
```

- [ ] **Step 2: Run service tests to verify fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_service.py -q
```

Expected: FAIL because service constructor and methods are not implemented.

- [ ] **Step 3: Implement `BilibiliService`**

Replace `server/domain/services/bilibili.py` with a service that:

- Accepts `courses`, `bilibili`, `async_tasks`, `task_dispatcher`, and `bili_client`.
- `_ensure_course(course_id)` raises `course.not_found`.
- `_require_auth_session()` raises `bilibili.auth_required` if no active session exists.
- `create_qr_session()` calls `bili_client.create_qr_session()` and saves it.
- `get_qr_session()` refreshes status using `bili_client.get_qr_session(session_id)` and saves changes.
- `get_auth_session()` returns only `loginStatus`, `userNickname`, `expiresAt`.
- `delete_auth_session()` deletes saved auth session and returns `{"deleted": True}`.
- `preview_import()` parses URL, checks auth, calls `bili_client.preview()`, and returns API dict.
- `create_import()` validates selection, creates import run, creates async task with `task_type="bilibili_import"`, target `bilibili_import_run`, updates run task id, then enqueues dispatcher.
- `get_import_status()` returns run plus `nextAction` computed from status.
- `list_imports()` returns a dictionary whose `items` value is the list returned by `bilibili.list_bilibili_import_runs(course_id=course_id)`.
- `cancel_import()` idempotently marks run and task `canceled` unless already `imported`.

Use `run_scoped_idempotent` for create/cancel actions with action names:

```python
f"bilibili.import_create:{course_id}"
f"bilibili.import_cancel:{import_run_id}"
```

- [ ] **Step 4: Add preview route and route payload fields**

Modify `server/api/routers/bilibili.py`:

```python
from server.schemas.requests import BilibiliImportRequest, BilibiliPreviewRequest


@router.post("/courses/{courseId}/resources/imports/bilibili/preview")
async def preview_bilibili_import(
    courseId: int,
    payload: BilibiliPreviewRequest,
    request: Request,
    service: BilibiliService = Depends(get_bilibili_service),
):
    return api_ok(
        request,
        service.preview_import(course_id=courseId, source_url=payload.source_url),
    )
```

Update `create_bilibili_import` to pass `source_url`, `selection_mode`, `selected_part_ids`, and `quality_preference`.

- [ ] **Step 5: Wire dependencies**

Modify `server/api/deps.py`:

```python
from server.infra.bilibili.client import BiliClient


@lru_cache
def _get_bili_client() -> BiliClient:
    return BiliClient()


async def get_bilibili_service(
    repo=Depends(get_week2_runtime_repository),
    async_tasks=Depends(get_async_task_repository),
    task_dispatcher=Depends(get_task_dispatcher),
) -> BilibiliService:
    return BilibiliService(
        courses=repo,
        bilibili=repo,
        async_tasks=async_tasks,
        task_dispatcher=task_dispatcher,
        bili_client=_get_bili_client(),
    )
```

`BiliClient` can be a stub class until Task 6, but it must expose the methods called by service and raise `ServiceError` with Bilibili-specific codes instead of `bilibili.not_implemented`.

- [ ] **Step 6: Update API tests from V1 stub to V2 behavior**

In `server/tests/test_api.py`, replace `test_bilibili_reserved_routes_return_not_implemented` with dependency-overridden V2 route tests that use the memory service and fake client from `test_bilibili_service.py`.

Add:

```python
def test_bilibili_preview_and_import_routes_return_v2_contract():
    from server.api.deps import get_bilibili_service
    from server.tests.test_bilibili_service import FakeBiliClient, RecordingDispatcher
    from server.domain.services.bilibili import BilibiliService
    from server.infra.db.base import utcnow
    from server.infra.repositories.memory import MemoryScaffoldRepository
    from server.infra.repositories.memory_runtime import RuntimeStore
    from datetime import timedelta

    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Bili API route course",
        entry_type="manual_import",
        goal_text="导入 B站",
        preferred_style="balanced",
    )
    repo.save_bilibili_auth_session(
        login_status="active",
        user_nickname="Bili User",
        expires_at=utcnow() + timedelta(hours=2),
        cookies_json={"SESSDATA": "hidden"},
    )
    dispatcher = RecordingDispatcher()

    async def override_service():
        return BilibiliService(
            courses=repo,
            bilibili=repo,
            async_tasks=repo,
            task_dispatcher=dispatcher,
            bili_client=FakeBiliClient(),
        )

    app.dependency_overrides[get_bilibili_service] = override_service
    try:
        preview_status, preview_body = asyncio.run(
            request(
                "POST",
                f"/api/v1/courses/{course['courseId']}/resources/imports/bilibili/preview",
                headers=AUTH_HEADERS,
                json_body={"sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2"},
            )
        )
        import_status, import_body = asyncio.run(
            request(
                "POST",
                f"/api/v1/courses/{course['courseId']}/resources/imports/bilibili",
                headers=AUTH_HEADERS | {"idempotency-key": "api-bili-import-1"},
                json_body={
                    "sourceUrl": "https://www.bilibili.com/video/BV1xx411c7mD?p=2",
                    "selectionMode": "current_part",
                },
            )
        )
    finally:
        app.dependency_overrides.clear()

    assert preview_status == 200
    assert preview_body["data"]["sourceType"] == "multi_p"
    assert import_status == 200
    assert import_body["data"]["entity"]["type"] == "bilibili_import_run"
```

Keep `test_bilibili_routes_require_auth`.

- [ ] **Step 7: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_service.py server/tests/test_api.py::test_bilibili_routes_require_auth server/tests/test_api.py::test_bilibili_preview_and_import_routes_return_v2_contract -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add server/domain/services/bilibili.py server/api/routers/bilibili.py server/api/deps.py server/tests/test_bilibili_service.py server/tests/test_api.py
git commit -m "feat(api): 接通B站导入服务状态机"
```

---

## Task 6: BiliClient, Downloader, And FFmpeg Adapter Boundaries

**Files:**
- Create: `server/infra/bilibili/client.py`
- Create: `server/infra/bilibili/downloader.py`
- Create: `server/infra/bilibili/ffmpeg.py`
- Modify: `server/infra/bilibili/__init__.py`
- Modify: `server/tests/test_bilibili_service.py`

- [ ] **Step 1: Write failing adapter tests**

Append to `server/tests/test_bilibili_service.py`:

```python
def test_bili_client_preview_normalizes_video_metadata():
    from server.infra.bilibili.client import BiliClient

    class FakeTransport:
        def get_json(self, url, *, headers=None, params=None):
            if "x/web-interface/view" in url:
                return {
                    "code": 0,
                    "data": {
                        "title": "真实样例",
                        "pic": "https://i0.hdslb.com/demo.jpg",
                        "bvid": "BV1xx411c7mD",
                        "aid": 100,
                        "pages": [
                            {"cid": 1001, "page": 1, "part": "P1", "duration": 600},
                            {"cid": 1002, "page": 2, "part": "P2", "duration": 900},
                        ],
                    },
                }
            raise AssertionError(url)

    client = BiliClient(transport=FakeTransport())

    preview = client.preview("https://www.bilibili.com/video/BV1xx411c7mD?p=2", {"SESSDATA": "demo"})

    assert preview.title == "真实样例"
    assert preview.source_type == "multi_p"
    assert preview.parts[1].selected_by_default is True


def test_downloader_writes_stream_and_reports_progress(tmp_path):
    from server.infra.bilibili.downloader import BiliDownloader

    progress = []

    class FakeStream:
        def open(self, url, headers):
            assert url == "https://upos.test/video.m4s"
            return [b"abc", b"def"]

    downloader = BiliDownloader(stream=FakeStream())
    output = tmp_path / "video.m4s"

    downloader.download("https://upos.test/video.m4s", output, headers={}, on_progress=progress.append)

    assert output.read_bytes() == b"abcdef"
    assert progress[-1]["downloadedBytes"] == 6


def test_ffmpeg_merger_builds_stream_copy_command(tmp_path):
    from server.infra.bilibili.ffmpeg import FfmpegMerger

    calls = []

    def fake_run(command):
        calls.append(command)
        Path(command[-1]).write_bytes(b"merged")

    video = tmp_path / "video.m4s"
    audio = tmp_path / "audio.m4s"
    output = tmp_path / "out.mp4"
    video.write_bytes(b"v")
    audio.write_bytes(b"a")

    merger = FfmpegMerger(run_command=fake_run)
    merger.merge(video, audio, output)

    assert "-c" in calls[0]
    assert "copy" in calls[0]
    assert output.read_bytes() == b"merged"
```

Import `Path` at top of `test_bilibili_service.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_service.py::test_bili_client_preview_normalizes_video_metadata server/tests/test_bilibili_service.py::test_downloader_writes_stream_and_reports_progress server/tests/test_bilibili_service.py::test_ffmpeg_merger_builds_stream_copy_command -q
```

Expected: FAIL because adapter classes do not exist.

- [ ] **Step 3: Implement `BiliClient` with fakeable transport**

Create `server/infra/bilibili/client.py`:

```python
from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from server.infra.bilibili.models import BilibiliPart, BilibiliPreview
from server.infra.bilibili.url import BilibiliUrlKind, parse_bilibili_url
from server.infra.repositories.memory_runtime import utcnow


class UrllibBiliTransport:
    def get_json(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, object] | None = None):
        if params:
            url = f"{url}?{urlencode(params)}"
        request = Request(url, headers=headers or {})
        with urlopen(request, timeout=15) as response:
            import json
            return json.loads(response.read().decode("utf-8"))


class BiliClient:
    def __init__(self, *, transport: object | None = None) -> None:
        self.transport = transport or UrllibBiliTransport()

    def create_qr_session(self) -> dict[str, object]:
        session_id = f"bili_qr_{int(utcnow().timestamp())}"
        return {
            "sessionId": session_id,
            "status": "pending_scan",
            "qrCodeUrl": "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
            "expiresAt": utcnow() + timedelta(minutes=3),
        }

    def get_qr_session(self, session_id: str) -> dict[str, object]:
        return {
            "sessionId": session_id,
            "status": "pending_scan",
            "qrCodeUrl": None,
            "expiresAt": utcnow() + timedelta(minutes=3),
        }

    def get_auth_session(self, saved: dict[str, object] | None) -> dict[str, object]:
        if not saved:
            return {"loginStatus": "anonymous", "userNickname": None, "expiresAt": None}
        return {
            "loginStatus": saved.get("loginStatus", "active"),
            "userNickname": saved.get("userNickname"),
            "expiresAt": saved.get("expiresAt"),
        }

    def preview(self, source_url: str, cookies: dict[str, object] | None) -> BilibiliPreview:
        parsed = parse_bilibili_url(source_url)
        if parsed.kind not in {BilibiliUrlKind.VIDEO, BilibiliUrlKind.MULTI_P}:
            return self._preview_reserved_collection_or_bangumi(source_url, parsed.kind.value)
        data = self.transport.get_json(
            "https://api.bilibili.com/x/web-interface/view",
            headers=self._headers(cookies),
            params={"bvid": parsed.bvid},
        )
        payload = data.get("data") or {}
        pages = payload.get("pages") or []
        selected_page = parsed.page_no or 1
        parts = [
            BilibiliPart(
                part_id=f"cid-{page.get('cid')}",
                title=str(page.get("part") or payload.get("title") or "Bilibili part"),
                duration_sec=int(page.get("duration") or 0),
                cid=int(page.get("cid")) if page.get("cid") is not None else None,
                aid=int(payload.get("aid")) if payload.get("aid") is not None else None,
                page_no=int(page.get("page") or index + 1),
                selected_by_default=int(page.get("page") or index + 1) == selected_page,
            )
            for index, page in enumerate(pages)
        ]
        source_type = "multi_p" if len(parts) > 1 or parsed.kind == BilibiliUrlKind.MULTI_P else "video"
        return BilibiliPreview(
            preview_id=f"bili_preview_{parsed.bvid or 'video'}",
            source_url=source_url,
            source_type=source_type,
            title=str(payload.get("title") or "Bilibili video"),
            cover_url=payload.get("pic"),
            total_parts=len(parts),
            parts=parts,
            default_selection_mode="current_part",
        )

    def _preview_reserved_collection_or_bangumi(self, source_url: str, source_type: str) -> BilibiliPreview:
        return BilibiliPreview(
            preview_id=f"bili_preview_{source_type}",
            source_url=source_url,
            source_type=source_type,
            title="Bilibili collection preview",
            cover_url=None,
            total_parts=0,
            parts=[],
            default_selection_mode="all_parts",
        )

    def _headers(self, cookies: dict[str, object] | None) -> dict[str, str]:
        if not cookies:
            return {}
        cookie = "; ".join(f"{key}={value}" for key, value in cookies.items())
        return {"Cookie": cookie, "User-Agent": "KnowLink/0.1"}
```

- [ ] **Step 4: Implement downloader**

Create `server/infra/bilibili/downloader.py`:

```python
from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen


class UrllibStream:
    def open(self, url: str, headers: dict[str, str]):
        request = Request(url, headers=headers)
        response = urlopen(request, timeout=30)
        try:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()


class BiliDownloader:
    def __init__(self, *, stream: object | None = None) -> None:
        self.stream = stream or UrllibStream()

    def download(self, url: str, destination: str | Path, *, headers: dict[str, str], on_progress=None) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        with path.open("wb") as file_obj:
            for chunk in self.stream.open(url, headers):
                file_obj.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None:
                    on_progress({"downloadedBytes": downloaded})
        return path
```

- [ ] **Step 5: Implement ffmpeg merger**

Create `server/infra/bilibili/ffmpeg.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


class FfmpegMerger:
    def __init__(self, *, ffmpeg_path: str = "ffmpeg", run_command=None) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.run_command = run_command or self._run_command

    def merge(self, video_path: str | Path, audio_path: str | Path, output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c",
            "copy",
            str(output),
        ]
        self.run_command(command)
        return output

    def _run_command(self, command: list[str]) -> None:
        subprocess.run(command, check=True)
```

Modify `server/infra/bilibili/__init__.py` to export `BiliClient`, `BiliDownloader`, `FfmpegMerger`.

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_service.py::test_bili_client_preview_normalizes_video_metadata server/tests/test_bilibili_service.py::test_downloader_writes_stream_and_reports_progress server/tests/test_bilibili_service.py::test_ffmpeg_merger_builds_stream_copy_command -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add server/infra/bilibili server/tests/test_bilibili_service.py
git commit -m "feat(infra): 增加小型B站下载器边界"
```

---

## Task 7: Import Runner, Dispatcher, And Resource Creation

**Files:**
- Create: `server/tasks/bilibili_import.py`
- Create: `server/tests/test_bilibili_import_runner.py`
- Modify: `server/tasks/dispatcher.py`
- Modify: `server/tasks/payloads.py`
- Modify: `server/tasks/worker.py`
- Modify: `server/domain/repositories/interfaces.py`
- Modify: `server/infra/repositories/memory_runtime.py`
- Modify: `server/infra/repositories/sqlalchemy.py`

- [ ] **Step 1: Write failing runner tests**

Create `server/tests/test_bilibili_import_runner.py`:

```python
from pathlib import Path

from server.infra.bilibili.models import BilibiliPart, BilibiliPreview
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.tasks.bilibili_import import BilibiliImportRunner


class FakeClient:
    def preview(self, source_url, cookies):
        return BilibiliPreview(
            preview_id="bili_preview_1",
            source_url=source_url,
            source_type="video",
            title="Runner demo",
            cover_url=None,
            total_parts=1,
            parts=[BilibiliPart(part_id="cid-1001", title="P1", duration_sec=30, cid=1001, selected_by_default=True)],
            default_selection_mode="current_part",
        )

    def playurl(self, *, source_url, part, cookies, quality_preference):
        return {
            "videoUrl": "https://upos.test/video.m4s",
            "audioUrl": "https://upos.test/audio.m4s",
            "headers": {"Referer": source_url},
        }


class FakeDownloader:
    def download(self, url, destination, *, headers, on_progress=None):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(url.encode("utf-8"))
        if on_progress:
            on_progress({"downloadedBytes": path.stat().st_size})
        return path


class FakeMerger:
    def merge(self, video_path, audio_path, output_path):
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(Path(video_path).read_bytes() + b"|" + Path(audio_path).read_bytes())
        return output


class FakeStorage:
    def __init__(self):
        self.uploads = []

    def upload_file(self, object_key, source_path, *, content_type=None, metadata=None):
        self.uploads.append({"objectKey": object_key, "sourcePath": str(source_path), "contentType": content_type})
        from server.infra.storage import ObjectStat

        return ObjectStat(size_bytes=Path(source_path).stat().st_size, checksum_required=False)


def test_runner_imports_bilibili_video_into_course_resource(tmp_path):
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Runner course",
        entry_type="manual_import",
        goal_text="导入 B站",
        preferred_style="balanced",
    )
    run = repo.create_bilibili_import_run(
        course_id=course["courseId"],
        source_url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_type="video",
        preview_json={"title": "Runner demo"},
        selection_json={"selectionMode": "current_part", "selectedPartIds": []},
    )
    storage = FakeStorage()
    runner = BilibiliImportRunner(
        bilibili=repo,
        resources=repo,
        async_tasks=repo,
        storage=storage,
        bili_client=FakeClient(),
        downloader=FakeDownloader(),
        merger=FakeMerger(),
        runtime_dir=tmp_path,
    )

    runner.run({"courseId": course["courseId"], "importRunId": run["importRunId"], "taskId": 7001})
    updated = repo.get_bilibili_import_run(run["importRunId"])
    resources = repo.list_resources(course["courseId"])

    assert updated["status"] == "imported"
    assert updated["progressPct"] == 100
    assert updated["resourceIds"] == [resources[0]["resourceId"]]
    assert resources[0]["sourceType"] == "bilibili"
    assert resources[0]["resourceType"] == "mp4"
    assert storage.uploads[0]["objectKey"].startswith(f"raw/1/{course['courseId']}/bilibili/{run['importRunId']}/")
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_import_runner.py -q
```

Expected: FAIL because runner and dispatcher support do not exist.

- [ ] **Step 3: Add task payload**

Modify `server/tasks/payloads.py`:

```python
class BilibiliImportPayload(CamelModel):
    course_id: int
    import_run_id: int


TASK_PAYLOAD_MODELS = {
    "parse_pipeline": ParsePipelinePayload,
    "handout_generate": HandoutGeneratePayload,
    "handout_block_generate": HandoutBlockGeneratePayload,
    "quiz_generate": QuizGeneratePayload,
    "review_refresh": ReviewRefreshPayload,
    "bilibili_import": BilibiliImportPayload,
}
```

- [ ] **Step 4: Add dispatcher method**

Modify `TaskDispatcher` protocol in `server/domain/repositories/interfaces.py`:

```python
    def enqueue_bilibili_import(self, *, task_id: int, payload: dict[str, Any]) -> None:
        raise NotImplementedError
```

Modify `NoopTaskDispatcher`, `InMemoryTaskDispatcher`, and `DramatiqTaskDispatcher` in `server/tasks/dispatcher.py` to add `enqueue_bilibili_import`. The no-op and in-memory implementations append:

```python
{
    "taskId": task_id,
    "taskType": "bilibili_import",
    "payload": payload,
    "adapter": "noop"  # or "in_memory"
}
```

`DramatiqTaskDispatcher` must load actor from env var `KNOWLINK_BILIBILI_IMPORT_ACTOR`, default `server.tasks.worker:bilibili_import`.

- [ ] **Step 5: Implement runner**

Create `server/tasks/bilibili_import.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from server.infra.bilibili import BiliClient, BiliDownloader, FfmpegMerger
from server.infra.repositories.memory_runtime import utcnow
from server.infra.storage import ObjectStorage


class BilibiliImportRunner:
    def __init__(
        self,
        *,
        bilibili,
        resources,
        async_tasks,
        storage: ObjectStorage,
        bili_client: BiliClient,
        downloader: BiliDownloader,
        merger: FfmpegMerger,
        runtime_dir: str | Path = "runtime/bilibili",
    ) -> None:
        self.bilibili = bilibili
        self.resources = resources
        self.async_tasks = async_tasks
        self.storage = storage
        self.bili_client = bili_client
        self.downloader = downloader
        self.merger = merger
        self.runtime_dir = Path(runtime_dir)

    def run(self, message: dict[str, Any]) -> None:
        course_id = int(message["courseId"])
        import_run_id = int(message["importRunId"])
        task_id = int(message["taskId"])
        run = self.bilibili.get_bilibili_import_run(import_run_id)
        if run is None:
            return
        source_url = str(run["sourceUrl"])
        selection = dict(run.get("selection") or {})
        cookies = {}

        self._mark(import_run_id, task_id, status="fetching_metadata", progress_pct=5, stage="fetching_metadata")
        preview = self.bili_client.preview(source_url, cookies)
        part = self._select_part(preview.parts, selection)

        self._mark(import_run_id, task_id, status="downloading", progress_pct=20, stage="downloading")
        playurl = self.bili_client.playurl(
            source_url=source_url,
            part=part,
            cookies=cookies,
            quality_preference=str(selection.get("qualityPreference") or "android_safe"),
        )
        run_dir = self.runtime_dir / str(import_run_id)
        video_path = self.downloader.download(
            playurl["videoUrl"],
            run_dir / "video.m4s",
            headers=dict(playurl.get("headers") or {}),
            on_progress=lambda _: self._mark(import_run_id, task_id, status="downloading", progress_pct=45, stage="downloading"),
        )
        audio_path = self.downloader.download(
            playurl["audioUrl"],
            run_dir / "audio.m4s",
            headers=dict(playurl.get("headers") or {}),
            on_progress=lambda _: self._mark(import_run_id, task_id, status="downloading", progress_pct=60, stage="downloading"),
        )

        self._mark(import_run_id, task_id, status="merging", progress_pct=70, stage="merging")
        output_path = self.merger.merge(video_path, audio_path, run_dir / "merged.mp4")

        self._mark(import_run_id, task_id, status="uploading", progress_pct=85, stage="uploading")
        object_key = f"raw/1/{course_id}/bilibili/{import_run_id}/{_safe_name(part.title)}.mp4"
        stat = self.storage.upload_file(
            object_key,
            output_path,
            content_type="video/mp4",
            metadata={"x-amz-meta-source-type": "bilibili"},
        )
        resource = self.resources.create_resource(
            course_id,
            {
                "resourceType": "mp4",
                "sourceType": "bilibili",
                "originUrl": source_url,
                "objectKey": object_key,
                "originalName": f"{part.title}.mp4",
                "mimeType": "video/mp4",
                "sizeBytes": stat.size_bytes,
                "checksum": stat.checksum,
                "parsePolicyJson": {"source": "bilibili", "importRunId": import_run_id},
            },
        )
        self._mark(
            import_run_id,
            task_id,
            status="imported",
            progress_pct=100,
            stage="imported",
            resource_ids=[resource["resourceId"]],
        )

    def _select_part(self, parts, selection):
        selected = selection.get("selectedPartIds") or []
        if selected:
            for part in parts:
                if part.part_id in selected:
                    return part
        for part in parts:
            if part.selected_by_default:
                return part
        return parts[0]

    def _mark(self, import_run_id: int, task_id: int, **changes: Any) -> None:
        self.bilibili.update_bilibili_import_run(import_run_id, **changes)
        self.async_tasks.update_async_task(
            task_id,
            status=_task_status(changes["status"]),
            progress_pct=changes.get("progress_pct"),
        )


def _task_status(run_status: str) -> str:
    if run_status == "imported":
        return "succeeded"
    if run_status == "canceled":
        return "canceled"
    if run_status in {"failed", "recoverable"}:
        return "failed"
    if run_status in {"pending", "waiting_download"}:
        return "queued"
    return "running"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value).strip("_") or "bilibili"
```

- [ ] **Step 6: Register worker actor**

Modify `server/tasks/worker.py`:

```python
from server.tasks.bilibili_import import run_bilibili_import


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
def bilibili_import(message: dict[str, Any]) -> None:
    run_bilibili_import(message, object_storage=build_object_storage(get_settings()))
```

Add `run_bilibili_import` function in `server/tasks/bilibili_import.py` that builds SQL repository/session for runtime use. For this task, it can raise a clear `RuntimeError("Bilibili import worker runtime wiring is not configured.")` if called without injected repository; tests use `BilibiliImportRunner` directly.

- [ ] **Step 7: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_import_runner.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add server/tasks/bilibili_import.py server/tasks/dispatcher.py server/tasks/payloads.py server/tasks/worker.py server/domain/repositories/interfaces.py server/infra/repositories/memory_runtime.py server/infra/repositories/sqlalchemy.py server/tests/test_bilibili_import_runner.py
git commit -m "feat(tasks): 增加B站导入任务执行器"
```

---

## Task 8: Course Catalog, Recommendation, And Multi-Course Semantics

**Files:**
- Modify: `server/seeds/course_catalog.json`
- Modify: `server/schemas/responses.py`
- Modify: `server/domain/services/recommendations.py`
- Modify: `server/domain/services/courses.py`
- Modify: `server/api/routers/courses.py`
- Modify: `server/infra/repositories/memory_runtime.py`
- Modify: `server/infra/repositories/sqlalchemy.py`
- Modify: `server/tests/test_api.py`
- Modify: `server/tests/test_scaffold_consistency.py`

- [ ] **Step 1: Write failing tests for V2 catalog fields and course detail**

Append to `server/tests/test_scaffold_consistency.py`:

```python
def test_v2_course_catalog_fields_are_present():
    catalog = load_json("server/seeds/course_catalog.json")
    required = {
        "subject",
        "courseCode",
        "targetAudience",
        "prerequisites",
        "knowledgeTags",
        "outline",
        "importHints",
        "reasonMaterials",
        "coverUrl",
        "highlights",
    }

    for item in catalog:
        assert required <= set(item)
        assert item["knowledgeTags"]
        assert item["outline"]
        assert item["reasonMaterials"]
```

Append to `server/tests/test_api.py`:

```python
def test_course_detail_and_current_course_switch():
    course_id, _ = create_manual_course(idempotency_key="v2-course-detail", title="V2 多课程语义")

    detail_status, detail = asyncio.run(
        request("GET", f"/api/v1/courses/{course_id}", headers=AUTH_HEADERS)
    )
    switch_status, switched = asyncio.run(
        request("POST", f"/api/v1/courses/{course_id}/switch-current", headers=AUTH_HEADERS)
    )
    current_status, current = asyncio.run(
        request("GET", "/api/v1/courses/current", headers=AUTH_HEADERS)
    )

    assert detail_status == 200
    assert detail["data"]["course"]["courseId"] == course_id
    assert switch_status == 200
    assert switched["data"]["currentCourseId"] == course_id
    assert current_status == 200
    assert current["data"]["course"]["courseId"] == course_id
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_scaffold_consistency.py::test_v2_course_catalog_fields_are_present server/tests/test_api.py::test_course_detail_and_current_course_switch -q
```

Expected: FAIL because catalog fields and course current routes are missing.

- [ ] **Step 3: Extend course catalog seed**

Modify every item in `server/seeds/course_catalog.json` to include:

```json
{
  "subject": "math",
  "courseCode": "MATH-FINAL-01",
  "targetAudience": "期末复习学生",
  "prerequisites": ["函数基础", "基础代数"],
  "knowledgeTags": ["极限", "导数", "积分"],
  "outline": [
    {"title": "极限与连续", "estimatedMinutes": 45},
    {"title": "导数与应用", "estimatedMinutes": 60}
  ],
  "importHints": ["优先导入课程视频", "配套 PDF 用于引用定位"],
  "reasonMaterials": ["覆盖高频考点", "适合考前冲刺"],
  "coverUrl": null,
  "highlights": ["高频题型", "讲义引用完整"]
}
```

Use subject/tag values that match each existing course title.

- [ ] **Step 4: Add course detail/current service methods**

Modify `RuntimeStore`:

```python
current_course_id: int | None = None
```

Add methods to memory and SQL repositories:

```python
def set_current_course(self, course_id: int) -> dict[str, Any] | None
def get_current_course(self) -> dict[str, Any] | None
```

For SQL, store current course in memory of repository instance is not durable. Use existing single-user scope by selecting most recently updated course if no explicit durable preference exists, then update course `updated_at` on switch. Return selected course. Document this as phase one basic current-course semantics in handoff.

Modify `CourseService`:

```python
def get_course(self, *, course_id: int) -> dict[str, object]:
    course = self.courses.get_course(course_id)
    if course is None:
        raise ServiceError(message="Course was not found.", error_code="course.not_found", status_code=404)
    return {"course": course}

def switch_current_course(self, *, course_id: int) -> dict[str, object]:
    course = self.courses.set_current_course(course_id)
    if course is None:
        raise ServiceError(message="Course was not found.", error_code="course.not_found", status_code=404)
    return {"currentCourseId": course["courseId"], "course": course}

def get_current_course(self) -> dict[str, object]:
    course = self.courses.get_current_course()
    if course is None:
        raise ServiceError(message="Course was not found.", error_code="course.not_found", status_code=404)
    return {"course": course}
```

- [ ] **Step 5: Add routes**

Modify `server/api/routers/courses.py`:

```python
@router.get("/current")
async def get_current_course(
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.get_current_course())


@router.get("/{courseId}")
async def get_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.get_course(course_id=courseId))


@router.post("/{courseId}/switch-current")
async def switch_current_course(
    courseId: int,
    request: Request,
    service: CourseService = Depends(get_course_service),
):
    return api_ok(request, service.switch_current_course(course_id=courseId))
```

- [ ] **Step 6: Add recommendation next action**

Modify `RecommendationCard` in `server/schemas/responses.py`:

```python
next_action: dict[str, object] | None = None
```

Modify `RecommendationService.recommend()` to include:

```python
next_action={
    "type": "confirm_course",
    "label": "确认入课并导入资料",
}
```

Add reasons from `reasonMaterials` when score context is sparse, while preserving existing V1 reason strings for current tests.

- [ ] **Step 7: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_scaffold_consistency.py::test_v2_course_catalog_fields_are_present server/tests/test_api.py::test_course_detail_and_current_course_switch server/tests/test_api.py::test_recommendation_confirm_is_idempotent -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add server/seeds/course_catalog.json server/schemas/responses.py server/domain/services/recommendations.py server/domain/services/courses.py server/api/routers/courses.py server/infra/repositories/memory_runtime.py server/infra/repositories/memory.py server/infra/repositories/sqlalchemy.py server/tests/test_api.py server/tests/test_scaffold_consistency.py
git commit -m "feat(domain): 补齐V2课程库和多课程语义"
```

---

## Task 9: Complete Handoff Document And Complex Layout Acceptance

**Files:**
- Modify: `docs/v2/phase1-cao-le-handoff.md`
- Modify: `server/tests/test_bilibili_contract.py`

- [ ] **Step 1: Write failing handoff completeness test**

Append to `server/tests/test_bilibili_contract.py`:

```python
def test_phase1_handoff_covers_team_boundaries_and_complex_layout():
    handoff = text("docs/v2/phase1-cao-le-handoff.md")

    for token in (
        "朱春雯",
        "杨彩艺",
        "扫码",
        "资源预览",
        "进度",
        "取消",
        "Android",
        "表格",
        "公式",
        "图片",
        "复杂布局",
        "不丢页",
        "引用断裂",
        ".venv/bin/python -m pytest",
        "bilibili.access_denied",
        "bilibili.merge_failed",
    ):
        assert token in handoff
```

- [ ] **Step 2: Run tests to verify fail**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py::test_phase1_handoff_covers_team_boundaries_and_complex_layout -q
```

Expected: FAIL because handoff skeleton lacks full detail.

- [ ] **Step 3: Expand handoff document**

Update `docs/v2/phase1-cao-le-handoff.md` with these sections and concrete content:

```markdown
## 曹乐已完成

- V2 B站导入 API contract。
- V2 B站导入状态机和错误码。
- 小型下载器后端边界。
- 导入任务和课程资源入库后端测试。
- 课程库、推荐、多课程基础语义。

## 给朱春雯

页面只需要展示 `qrCodeUrl`、`loginStatus`、`preview.parts`、`status`、`progressPct`、`stage`、`failureReason`、`nextAction`。前端不读取 cookie。取消按钮调用 `POST /api/v1/bilibili-import-runs/{importRunId}/cancel`。

## 给杨彩艺

可以整理状态查询样例、任务列表样例、错误码说明和联调记录。不要实现下载、ffmpeg、取消副作用、任务恢复和复杂状态机。

## 复杂版面最低验收标准

- 表格：保留行列结构或 Markdown 表格。
- 公式：不能出现明显乱码；无法结构化时保留原文或 OCR 文本并记录 issue。
- 图片：保留 caption、位置和来源引用。
- 复杂布局：不丢页，不让引用断裂，不把不同页或 slide 的 citation 混在同一条引用中。
```

Include a command block with focused test command:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py server/tests/test_bilibili_url.py server/tests/test_bilibili_service.py server/tests/test_bilibili_import_runner.py server/tests/test_bilibili_sql_runtime.py -q
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/v2/phase1-cao-le-handoff.md server/tests/test_bilibili_contract.py
git commit -m "docs(v2): 完善曹乐阶段一交接文档"
```

---

## Task 10: Final Focused Verification And Review Prep

**Files:**
- No planned source edits unless verification exposes a regression.

- [ ] **Step 1: Run focused Bilibili and course tests**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_bilibili_contract.py server/tests/test_bilibili_url.py server/tests/test_bilibili_service.py server/tests/test_bilibili_import_runner.py server/tests/test_bilibili_sql_runtime.py server/tests/test_storage.py::test_demo_object_storage_upload_file_records_file_size server/tests/test_storage.py::test_minio_object_storage_upload_file_calls_fput_object server/tests/test_api.py::test_bilibili_routes_require_auth server/tests/test_api.py::test_bilibili_preview_and_import_routes_return_v2_contract server/tests/test_api.py::test_course_detail_and_current_course_switch server/tests/test_scaffold_consistency.py::test_v2_course_catalog_fields_are_present -q
```

Expected: PASS.

- [ ] **Step 2: Run contract freeze tests**

Run:

```bash
.venv/bin/python -m pytest -s server/tests/test_contract_freeze.py server/tests/test_scaffold_consistency.py -q
```

Expected: PASS or identify any historical V1 wording tests that need a narrow update because V2 contract now supersedes V1 Bilibili stub.

- [ ] **Step 3: Run full backend test suite**

Run:

```bash
.venv/bin/python -m pytest -s
```

Expected: PASS. If external dependencies or environment produce unrelated failures, record exact failing tests and root cause in the final response after confirming focused tests pass.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git status --short
git diff --stat HEAD~9..HEAD
```

Expected: only V2 Bilibili/backend/docs/course-recommendation files changed.

- [ ] **Step 5: Request final code review**

Dispatch a reviewer subagent with:

```text
Review Cao Le V2 phase 1 Bilibili backend implementation on branch codex/v2-phase1-caole.
Check against docs/superpowers/specs/2026-05-18-v2-phase1-caole-bilibili-design.md and docs/superpowers/plans/2026-05-18-v2-phase1-caole-bilibili.md.
Focus on state machine correctness, owner boundary, contract/doc clarity, cancellation semantics, resource import side effects, tests, and unrelated changes.
Return findings ordered by severity with file/line references.
```

- [ ] **Step 6: Fix review findings**

If reviewer reports Critical or Important findings, fix them with TDD and rerun focused tests from Step 1.

- [ ] **Step 7: Final status**

Report:

- Branch name.
- Commits created.
- Focused verification command outcomes.
- Full-suite outcome.
- Docs created.
- Remaining integration dependencies for Zhu Chunwen and Yang Caiyi.

**Commit:** only if review fixes are needed; use a Conventional Commit with lowercase type/scope and Chinese subject.
