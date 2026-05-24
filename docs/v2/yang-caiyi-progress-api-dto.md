# Yang Caiyi Progress API DTO

本文整理任务 19：最近学习位置 DTO 文档。只说明 progress 读取和保存字段。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | progress API contract |
| `server/api/routers/progress.py` | router entry |
| `server/domain/services/progress.py` | progress service |

## APIs

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/courses/{courseId}/progress` | 读取最近学习位置 |
| `POST` | `/api/v1/courses/{courseId}/progress` | 保存最近学习位置 |

## Response DTO

| Field | Type | Meaning |
|---|---|---|
| `courseId` | integer | 课程 id |
| `handoutVersionId` | integer | 最近讲义版本 |
| `lastHandoutBlockId` | integer | 最近讲义块 |
| `lastVideoResourceId` | integer | 最近视频资源 |
| `lastPositionSec` | integer | 视频播放位置 |
| `lastDocResourceId` | integer | 最近文档资源 |
| `lastPageNo` | integer | 最近文档页码 |
| `lastActivityAt` | datetime | 最近活动时间 |

## Save Request DTO

| Field | Type | Meaning |
|---|---|---|
| `handoutVersionId` | integer | 最近讲义版本 |
| `lastHandoutBlockId` | integer | 最近讲义块 |
| `lastVideoResourceId` | integer | 最近视频资源 |
| `lastPositionSec` | integer | 视频播放位置 |
| `lastDocResourceId` | integer | 最近文档资源 |
| `lastPageNo` | integer | 最近文档页码 |

`courseId` 以 path 为准，请求体不重复传 `courseId`。`lastActivityAt` 由服务端补写。

## Integration Notes

| Scenario | Expected |
|---|---|
| 首次进入课程 | 可返回空值或默认位置，前端需兼容 |
| 视频播放进度 | 保存 `lastVideoResourceId` 和 `lastPositionSec` |
| 文档阅读进度 | 保存 `lastDocResourceId` 和 `lastPageNo` |
| 讲义定位 | 保存 `handoutVersionId` 和 `lastHandoutBlockId` |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理 progress DTO 和联调记录 | 可做 |
| 新增学习统计或推荐算法字段 | 不做 |
