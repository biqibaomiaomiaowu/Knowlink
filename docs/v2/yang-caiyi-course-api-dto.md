# 杨彩艺 课程接口 DTO 文档

来源：`docs/contracts/api-contract.md`

用途：整理课程创建、最近课程、课程详情、当前课程和课程切换接口的 DTO 字段，供杨彩艺做接口文档、联调记录和测试数据整理。本文只整理已有 contract 字段，不新增多课程复杂管理字段。

实际联调记录见 [test-course.md](./test-course.md)。该记录包含课程创建、最近课程、当前课程、课程详情、课程切换、首页 dashboard、资源上传和资源删除的实际返回摘要。

## 接口清单

| 接口 | 方法 | 路径 | 用途 | 幂等要求 |
|---|---|---|---|---|
| 创建课程 | `POST` | `/api/v1/courses` | 创建手动导入课程 | 必须支持 `Idempotency-Key` |
| 最近课程 | `GET` | `/api/v1/courses/recent` | 获取最近课程列表 | 无 |
| 课程详情 | `GET` | `/api/v1/courses/{courseId}` | 获取单个课程详情 | 无 |
| 切换当前课程 | `POST` | `/api/v1/courses/{courseId}/switch-current` | 单用户下切换当前课程 | 未单独列入幂等清单 |
| 当前课程 | `GET` | `/api/v1/courses/current` | 读取当前课程 | 无 |

## 创建课程请求 DTO

接口：`POST /api/v1/courses`

| 字段 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|
| `title` | string | 是 | `KnowLink 固定联调课` | 课程标题 |
| `entryType` | string | 是 | `manual_import` | 课程入口类型 |
| `goalText` | string | 否 | `期末复习` | 学习目标 |
| `examAt` | string, datetime | 否 | `2026-06-20T09:00:00+08:00` | 考试或截止时间 |
| `preferredStyle` | string | 否 | `balanced` | 学习/讲义偏好 |

请求示例：

```json
{
  "title": "KnowLink 固定联调课",
  "entryType": "manual_import",
  "goalText": "期末复习",
  "examAt": "2026-06-20T09:00:00+08:00",
  "preferredStyle": "balanced"
}
```

## 课程摘要 DTO

以下接口会返回课程摘要或与其保持同结构：

- `POST /api/v1/courses`
- `GET /api/v1/courses/recent`
- `POST /api/v1/recommendations/{catalogId}/confirm`
- `POST /api/v1/courses/{courseId}/switch-current`

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `courseId` | number | `101` | 课程 ID |
| `title` | string | `高数期末冲刺课` | 课程标题 |
| `entryType` | string | `recommendation` | 入口类型 |
| `catalogId` | string/null | `math-final-01` | 推荐来源；手动课程可为空 |
| `lifecycleStatus` | string | `draft` | 课程生命周期状态 |
| `pipelineStage` | string | `idle` | 当前流程阶段 |
| `pipelineStatus` | string | `idle` | 当前流程状态 |
| `updatedAt` | string, datetime | `2026-04-18T15:00:00+00:00` | 更新时间 |

## 最近课程响应 DTO

接口：`GET /api/v1/courses/recent`

| 字段 | 类型 | 说明 |
|---|---|---|
| `items` | array | 最近课程摘要列表 |

`items[]` 使用“课程摘要 DTO”。

## 课程详情响应 DTO

接口：`GET /api/v1/courses/{courseId}`

| 字段 | 类型 | 说明 |
|---|---|---|
| `course` | object | 课程详情 |

`course`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `courseId` | number | `101` | 课程 ID |
| `title` | string | `高数期末冲刺课` | 课程标题 |
| `entryType` | string | `recommendation` | 入口类型 |
| `catalogId` | string/null | `math-final-01` | 推荐来源 |
| `goalText` | string/null | `高等数学期末复习` | 学习目标 |
| `examAt` | string, datetime/null | `2026-06-20T09:00:00+08:00` | 考试或截止时间 |
| `preferredStyle` | string/null | `exam` | 学习/讲义偏好 |
| `lifecycleStatus` | string | `draft` | 生命周期状态 |
| `pipelineStage` | string | `idle` | 流程阶段 |
| `pipelineStatus` | string | `idle` | 流程状态 |
| `updatedAt` | string, datetime | `2026-05-19T12:00:00+00:00` | 更新时间 |

## 课程切换响应 DTO

接口：`POST /api/v1/courses/{courseId}/switch-current`

| 字段 | 类型 | 说明 |
|---|---|---|
| `currentCourseId` | number | 当前课程 ID |
| `course` | object | 当前课程摘要 |

说明：阶段一当前课程语义为单用户基础语义，不涉及多用户、权限或班级协作。

## 当前课程响应 DTO

接口：`GET /api/v1/courses/current`

| 字段 | 类型 | 说明 |
|---|---|---|
| `course` | object | 与课程详情接口保持同结构 |

当前课程语义：

| 情况 | 返回 |
|---|---|
| 已显式切换课程 | 返回被切换的课程 |
| 没有显式切换 | 返回最近更新课程 |

## 联调记录模板

| 记录项 | 填写内容 |
|---|---|
| 测试时间 |  |
| 接口 |  |
| 请求参数 |  |
| `courseId` |  |
| `title` |  |
| `entryType` |  |
| `lifecycleStatus` |  |
| `pipelineStage` |  |
| `pipelineStatus` |  |
| `updatedAt` |  |
| 额外返回字段 | `activeParseRunId=null`, `activeHandoutVersionId=null`，DTO 未定义，待确认 |
| 证据 | 响应 JSON、截图或录屏 |

## 实际返回字段差异记录

### POST /api/v1/courses

联调过程中发现实际 response 的 `data.course` 中额外返回以下字段：

| 字段 | 实际值 | DTO 是否已定义 | 处理结论 | 备注 |
|---|---|---|---|---|
| `activeParseRunId` | null | 否 | 待确认 | 实际接口返回存在，但当前课程摘要 DTO 未定义 |
| `activeHandoutVersionId` | null | 否 | 待确认 | 实际接口返回存在，但当前课程摘要 DTO 未定义 |

说明：  
当前 DTO 文档来源于 `docs/contracts/api-contract.md`，本文只整理已有 contract 字段，不新增复杂管理字段。因此上述字段暂不直接并入课程摘要 DTO，需与后端确认是否属于课程接口正式返回字段。

联调修正：

| 原始记录 | 修正口径 |
|---|---|
| `course_id`、`updated_at` | API 对外使用 camelCase：`courseId`、`updatedAt` |
| `status=active/archived` | 当前课程状态拆为 `lifecycleStatus`、`pipelineStage`、`pipelineStatus` |
| `status=running` | 属于 pipeline / async task 语义，不应写入课程摘要 DTO |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理课程 DTO 字段 | 设计多用户语义 |
| 整理课程切换联调记录 | 实现复杂课程隔离策略 |
| 整理状态字段展示说明 | 新增归档、删除、搜索、筛选字段 |
| 准备课程创建测试数据 | 修改课程核心业务逻辑 |
