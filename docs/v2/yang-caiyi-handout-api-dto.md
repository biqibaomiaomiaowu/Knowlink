# Yang Caiyi Handout API DTO

本文整理任务 15：讲义查询接口 DTO 文档。只整理 latest、outline、blocks、block status、current-block 和 jump-target 字段，不改讲义生成逻辑。

## Source

| Source | Purpose |
|---|---|
| `docs/contracts/api-contract.md` | handout API contract |
| `docs/contracts/week2-cao-le-parse-inquiry-contract.md` | outline、block、citation 业务语义 |
| `server/api/routers/handouts.py` | router entry |
| `server/domain/services/handouts.py` | handout service |

## APIs

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/courses/{courseId}/handouts/generate` | 创建讲义生成任务 |
| `GET` | `/api/v1/handout-versions/{handoutVersionId}/status` | 查询讲义版本状态 |
| `GET` | `/api/v1/courses/{courseId}/handouts/latest` | 查询最新讲义摘要 |
| `GET` | `/api/v1/courses/{courseId}/handouts/latest/outline` | 查询两级讲义目录 |
| `GET` | `/api/v1/courses/{courseId}/handouts/latest/blocks` | 查询讲义块列表 |
| `POST` | `/api/v1/handout-blocks/{blockId}/generate` | 触发单个讲义块生成 |
| `GET` | `/api/v1/handout-blocks/{blockId}/status` | 查询单个讲义块状态 |
| `GET` | `/api/v1/courses/{courseId}/handouts/current-block?currentSec=335` | 根据播放时间查询当前 block |
| `GET` | `/api/v1/handout-blocks/{blockId}/jump-target` | 查询视频 / 文档跳转目标 |

## Async Trigger DTO

| Field | Type | Meaning |
|---|---|---|
| `taskId` | integer | 异步任务 id |
| `status` | string | `queued` 等 async task 状态 |
| `nextAction` | string | 通常为 `poll` |
| `entity.type` | string | `handout_version` 或 `handout_block` |
| `entity.id` | integer | 对应实体 id |

## Latest Handout DTO

| Field | Type | Meaning |
|---|---|---|
| `handoutVersionId` | integer | 讲义版本 id |
| `title` | string | 讲义标题 |
| `summary` | string | 讲义摘要 |
| `totalBlocks` | integer | block 总数 |
| `status` | string | 讲义版本状态 |

## Outline DTO

| Field | Type | Meaning |
|---|---|---|
| `handoutVersionId` | integer | 讲义版本 id |
| `title` | string | 目录标题 |
| `summary` | string | 目录摘要 |
| `items` | array | 顶层大标题数组 |

## `items[]` and `children[]`

| Field | Parent item | Child item | Meaning |
|---|---|---|---|
| `outlineKey` | yes | yes | 稳定目录 key |
| `blockId` | no | yes | 只有 child 绑定 block |
| `title` | yes | yes | 标题 |
| `summary` | yes | yes | 摘要 |
| `startSec` | yes | yes | 视频开始秒 |
| `endSec` | yes | yes | 视频结束秒 |
| `sortNo` | yes | yes | 排序 |
| `children` | yes | no | child 目录项 |
| `generationStatus` | no | yes | `pending`、`generating`、`ready`、`failed` |
| `sourceSegmentKeys` | no | yes | 来源 segment key |
| `topicTags` | no | yes | 展示标签 |

## Block DTO

| Field | Type | Meaning |
|---|---|---|
| `blockId` | integer | block id |
| `handoutVersionId` | integer | 讲义版本 id |
| `outlineKey` | string | 对应 child outline key |
| `title` | string | block 标题 |
| `summary` | string | block 摘要 |
| `status` | string | block 状态 |
| `generationStatus` | string | 生成状态 |
| `contentMd` | string or null | 讲义正文，未生成时可为 null |
| `startSec` / `endSec` | integer | 视频定位 |
| `sourceSegmentKeys` | array | 来源 segment key |
| `knowledgePoints` | array | block 级知识点 |
| `generationMetadata` | object | 生成来源元数据，ready 时返回 |
| `citations` | array | public citation |

## Jump Target DTO

| Field | Type | Meaning |
|---|---|---|
| `blockId` | integer | block id |
| `videoResourceId` | integer | 视频资源 id |
| `startSec` / `endSec` | integer | 视频跳转区间 |
| `docResourceId` | integer or null | 文档资源 id |
| `pageNo` / `slideNo` / `anchorKey` | integer / string | 文档定位字段，按资源类型互斥使用 |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理讲义 read DTO 和联调检查表 | 可做 |
| 记录 Android 当前 block / jump-target 联调结果 | 可做 |
| 修改讲义生成、懒生成、citation 反查策略 | 不做 |
