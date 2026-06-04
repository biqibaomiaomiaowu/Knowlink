# Yang Caiyi Server Layer Map

本文整理任务 23：server 分层入口说明。只整理 router -> service -> repository 文件映射，不改架构。

## Layer Rule

后端依赖方向固定为：

```text
router -> service -> repository
```

DTO 固定在 `server/schemas/common.py`、`server/schemas/requests.py`、`server/schemas/responses.py`。新增能力时先补 service，再决定是否加 repository protocol。

## Router to Service Map

| Area | Router | Service | Notes |
|---|---|---|---|
| Health | `server/api/routers/health.py` | none | `/health` |
| Recommendations | `server/api/routers/recommendations.py` | `server/domain/services/recommendations.py` | 推荐和确认入课 |
| Courses | `server/api/routers/courses.py` | `server/domain/services/courses.py` | 创建、最近、详情、当前课程 |
| Home | `server/api/routers/home.py` | `server/domain/services/home.py` | 首页 dashboard |
| Resources | `server/api/routers/resources.py` | `server/domain/services/resources.py` | 上传、列表、播放、删除 |
| Bilibili | `server/api/routers/bilibili.py` | `server/domain/services/bilibili.py` | V2 B站导入 |
| Pipelines | `server/api/routers/pipelines.py` | `server/domain/services/pipelines.py` | parse、pipeline-status、retry |
| Inquiry | `server/api/routers/inquiry.py` | `server/domain/services/inquiry.py` | 问询题和答案 |
| Handouts | `server/api/routers/handouts.py` | `server/domain/services/handouts.py` | 讲义、outline、block、jump-target |
| QA | `server/api/routers/qa.py` | `server/domain/services/qa.py` | QA 消息 |
| Quizzes | `server/api/routers/quizzes.py` | `server/domain/services/quizzes.py` | 测验 |
| Reviews | `server/api/routers/reviews.py` | `server/domain/services/reviews.py` | 复习 |
| Progress | `server/api/routers/progress.py` | `server/domain/services/progress.py` | 最近学习位置 |

## Repository Entry

| File | Purpose |
|---|---|
| `server/domain/repositories/interfaces.py` | repository protocol 定义 |
| `server/infra/repositories/sqlalchemy.py` | SQLAlchemy runtime repository |
| `server/infra/repositories/memory.py` | demo / scaffold / lightweight tests |
| `server/infra/repositories/memory_runtime.py` | memory runtime helper |

## Schema Entry

| File | Purpose |
|---|---|
| `server/schemas/base.py` | Pydantic base and camelCase alias helper |
| `server/schemas/common.py` | shared DTO |
| `server/schemas/requests.py` | request DTO |
| `server/schemas/responses.py` | response DTO |

## Task Entry

| File | Purpose |
|---|---|
| `server/tasks/payloads.py` | task payload structure |
| `server/tasks/dispatcher.py` | dispatcher entry |
| `server/tasks/worker.py` | worker entry |
| `server/tasks/broker.py` | broker adapter |
| `server/tasks/parse_pipeline.py` | parse task |
| `server/tasks/handouts.py` | handout task |
| `server/tasks/quizzes.py` | quiz task |
| `server/tasks/reviews.py` | review task |
| `server/tasks/bilibili_import.py` | B站 import runner |

## Yang Caiyi Boundary

| Item | Status |
|---|---|
| 整理入口、owner 边界和联调查找路径 | 可做 |
| 修改 router/service/repository 架构 | 不做 |
| 新增 repository protocol 或 runtime adapter | 需曹乐先冻结 |
