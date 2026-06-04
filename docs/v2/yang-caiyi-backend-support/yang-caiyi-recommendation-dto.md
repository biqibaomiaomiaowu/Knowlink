# 杨彩艺 推荐接口 DTO 文档

来源：

- `docs/contracts/api-contract.md`
- `docs/contracts/week1-cao-le-freeze.md`
- `server/seeds/course_catalog.json`

用途：整理推荐链路已冻结的请求字段、响应字段、推荐理由规则和 seed 数据来源，供杨彩艺做接口文档、联调记录和测试数据整理。本文只整理已冻结 DTO 和 seed 字段，不修改推荐算法，不新增推荐字段。

## 接口清单

| 接口 | 方法 | 路径 | 用途 | 幂等要求 | 杨彩艺可做事项 |
|---|---|---|---|---|---|
| 获取课程推荐 | `POST` | `/api/v1/recommendations/courses` | 根据学习目标、基础、时间和偏好返回课程推荐列表 | 未列入写接口幂等清单 | 整理请求/响应 DTO、推荐理由、测试样例 |
| 确认入课 | `POST` | `/api/v1/recommendations/{catalogId}/confirm` | 根据推荐目录创建课程 | 必须支持 `Idempotency-Key` | 整理确认入课 DTO、返回课程字段、联调记录 |

## 获取课程推荐请求 DTO

接口：`POST /api/v1/recommendations/courses`

| 字段 | 类型 | 必填 | 示例 | 已冻结说明 | 杨彩艺记录重点 |
|---|---|---|---|---|---|
| `goalText` | string | 是 | `高等数学期末复习` | 学习目标文本 | 记录用户目标和推荐结果是否匹配 |
| `selfLevel` | string | 是 | `intermediate` | 当前基础水平 | 记录与课程 `level` 的匹配情况 |
| `timeBudgetMinutes` | number | 是 | `240` | 时间预算，单位分钟 | 记录与课程 `estimatedHours` 的关系 |
| `examAt` | string, datetime | 否 | `2026-06-15T09:00:00+08:00` | 考试或目标截止时间 | 若为空，记录推荐是否仍可返回 |
| `preferredStyle` | string | 是 | `exam` | 偏好讲义/学习风格 | 记录是否命中 `supportedStyles` |

请求示例：

```json
{
  "goalText": "高等数学期末复习",
  "selfLevel": "intermediate",
  "timeBudgetMinutes": 240,
  "examAt": "2026-06-15T09:00:00+08:00",
  "preferredStyle": "exam"
}
```

## 获取课程推荐响应 DTO

响应 `data` 顶层：

| 字段 | 类型 | 说明 | 杨彩艺记录重点 |
|---|---|---|---|
| `recommendations` | array | 推荐课程列表 | 按 `fitScore` 降序检查 |
| `requestEcho` | object | 请求回显 | 检查是否与请求一致 |

`recommendations[]`：

| 字段 | 类型 | 示例 | 已冻结说明 | 数据来源 |
|---|---|---|---|---|
| `catalogId` | string | `math-final-01` | 推荐目录 ID | `server/seeds/course_catalog.json` |
| `title` | string | `高等数学期末冲刺` | 推荐课程标题 | `server/seeds/course_catalog.json` |
| `provider` | string | `KnowLink Seed` | 课程来源 | `server/seeds/course_catalog.json` |
| `level` | string | `intermediate` | 课程难度 | `server/seeds/course_catalog.json` |
| `estimatedHours` | number | `4` | 预计学习小时数 | `server/seeds/course_catalog.json` |
| `fitScore` | number | `96` | 推荐匹配分 | 推荐服务输出 |
| `reasons` | array[string] | `难度与当前基础匹配` | 推荐理由展示文案 | 优先使用冻结文案 |
| `reasonMaterials` | array[string] | `覆盖高频考点` | 课程详情页和推荐卡片解释材料，不参与排序 | `server/seeds/course_catalog.json` |
| `nextAction` | object | `{ "type": "confirm_course" }` | 下一步动作；`confirm_course` 表示调用确认入课接口 | 推荐响应 |
| `defaultResourceManifest` | array[object] | 见下表 | 默认资源清单 | `server/seeds/course_catalog.json` |

`defaultResourceManifest[]`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `resourceType` | string | `mp4` | 资源类型，可为 `mp4`、`pdf`、`pptx`、`docx`、`srt` |
| `required` | boolean | `true` | 是否为推荐课程默认必需资源 |
| `description` | string | `主课程视频` | 资源说明 |

`requestEcho`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `goalText` | string | 原请求学习目标 |
| `selfLevel` | string | 原请求基础水平 |
| `timeBudgetMinutes` | number | 原请求时间预算 |
| `examAt` | string, datetime | 原请求考试或截止时间 |
| `preferredStyle` | string | 原请求偏好 |

## 推荐理由规则

| 规则 | 已冻结口径 |
|---|---|
| 排序 | `recommendations` 按 `fitScore` 降序返回 |
| 同分排序 | 若 `fitScore` 相同，保持 `server/seeds/course_catalog.json` 中的种子顺序 |
| `reasons[]` 来源 | 优先使用 Week 1 冻结文案 |
| `reasonMaterials[]` 用途 | 来自 seed，用于课程详情页和推荐卡片解释，不参与排序 |
| `nextAction.type` | `confirm_course` 表示前端下一步调用 `POST /api/v1/recommendations/{catalogId}/confirm` |

Week 1 冻结推荐理由文案：

| 文案 |
|---|
| `难度与当前基础匹配` |
| `难度可控，适合作为过渡课程` |
| `时长可在当前预算内完成` |
| `需要拆分学习节奏，但仍可安排` |
| `目标关键词与课程主题高度一致` |
| `讲义风格与当前偏好一致` |

## 确认入课请求 DTO

接口：`POST /api/v1/recommendations/{catalogId}/confirm`

| 字段 | 位置 | 类型 | 必填 | 示例 | 说明 |
|---|---|---|---|---|---|
| `catalogId` | path | string | 是 | `math-final-01` | 要确认入课的推荐目录 ID |
| `goalText` | body | string | 否 | `高等数学期末复习` | 学习目标 |
| `examAt` | body | string, datetime | 否 | `2026-06-15T09:00:00+08:00` | 考试或目标截止时间 |
| `preferredStyle` | body | string | 否 | `exam` | 学习/讲义偏好 |
| `titleOverride` | body | string | 否 | `高数期末冲刺课` | 用户自定义课程标题 |

请求示例：

```json
{
  "goalText": "高等数学期末复习",
  "examAt": "2026-06-15T09:00:00+08:00",
  "preferredStyle": "exam",
  "titleOverride": "高数期末冲刺课"
}
```

## 确认入课响应 DTO

响应 `data`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `course` | object | 创建后的课程摘要 |
| `createdFromCatalogId` | string | 创建来源 catalog ID |

`course`：

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `courseId` | number | `101` | 课程 ID |
| `title` | string | `高数期末冲刺课` | 课程标题 |
| `entryType` | string | `recommendation` | 课程入口类型 |
| `catalogId` | string | `math-final-01` | 来源推荐目录 ID |
| `lifecycleStatus` | string | `draft` | 课程生命周期状态 |
| `pipelineStage` | string | `idle` | 当前流程阶段 |
| `pipelineStatus` | string | `idle` | 当前流程状态 |
| `updatedAt` | string, datetime | `2026-04-18T15:00:00+00:00` | 更新时间 |

## Seed 数据字段说明

权威来源：`server/seeds/course_catalog.json`

当前推荐演示课程：

| `catalogId` | `title` | `provider` | `level` | `estimatedHours` | `supportedStyles` |
|---|---|---|---|---|---|
| `math-final-01` | `高等数学期末冲刺` | `KnowLink Seed` | `intermediate` | `4` | `exam`、`balanced` |
| `math-grad-02` | `考研数学基础巩固` | `KnowLink Seed` | `beginner` | `6` | `detailed`、`balanced` |
| `linear-final-01` | `线性代数高频题型课` | `KnowLink Seed` | `intermediate` | `3` | `exam`、`quick` |

Seed 中可用于推荐展示或联调记录的字段：

| 字段 | 说明 | 是否参与排序 |
|---|---|---|
| `catalogId` | 推荐目录 ID | 否 |
| `title` | 课程标题 | 否 |
| `provider` | 课程来源 | 否 |
| `subject` | 学科 | 可作为展示或筛选材料，当前排序以 contract 为准 |
| `courseCode` | 课程代码 | 否 |
| `level` | 难度 | 与 `selfLevel` 匹配相关 |
| `targetAudience` | 目标人群 | 否 |
| `estimatedHours` | 预计学习小时数 | 与 `timeBudgetMinutes` 匹配相关 |
| `tags` | 课程标签 | 可用于目标关键词匹配记录 |
| `knowledgeTags` | 知识点标签 | 可用于展示，不扩写推荐增强逻辑 |
| `prerequisites` | 先修要求 | 可用于展示 |
| `outline` | 课程大纲 | 可用于课程详情页 |
| `importHints` | 导入提示 | 可用于联调和课程详情 |
| `reasonMaterials` | 推荐解释素材 | 不参与排序 |
| `coverUrl` | 封面 URL | 展示字段 |
| `highlights` | 亮点 | 展示字段 |
| `supportedStyles` | 支持偏好 | 与 `preferredStyle` 匹配相关 |
| `defaultResourceManifest` | 默认资源清单 | 展示和导入提示 |

## 联调记录模板

| 记录项 | 示例 | 说明 |
|---|---|---|
| 请求目标 | `高等数学期末复习` | 记录 `goalText` |
| 当前基础 | `intermediate` | 记录 `selfLevel` |
| 时间预算 | `240` | 记录 `timeBudgetMinutes` |
| 偏好 | `exam` | 记录 `preferredStyle` |
| 返回数量 | `3` | 记录 `recommendations.length` |
| 第一推荐 | `math-final-01 / 高等数学期末冲刺` | 记录 `catalogId` 和 `title` |
| 推荐分 | `96` | 记录 `fitScore` |
| 推荐理由 | `难度与当前基础匹配` 等 | 必须来自冻结理由或 seed 解释素材 |
| 默认资源 | `mp4 required=true`、`pdf required=true` 等 | 记录 `defaultResourceManifest` |
| 下一步 | `confirm_course` | 记录 `nextAction.type` |
| 确认入课结果 | `courseId=...`、`lifecycleStatus=draft` | 记录确认入课响应 |
| 证据 | 响应 JSON、截图、录屏 | 验收材料 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理推荐请求和响应 DTO | 修改推荐排序算法 |
| 整理 seed 字段说明 | 新增 seed 字段或改变 seed 语义 |
| 整理推荐理由固定文案 | 自行发明新的推荐理由文案 |
| 整理确认入课返回字段 | 改课程创建核心逻辑 |
| 准备推荐接口联调记录和测试样例 | 扩写个性化推荐增强逻辑 |
