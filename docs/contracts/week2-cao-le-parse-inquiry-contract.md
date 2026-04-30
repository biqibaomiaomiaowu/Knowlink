# 曹乐 Week 2 解析与问询契约

本文件冻结曹乐 Week 2 负责的解析产物、解析步骤、`pipeline-status` 语义和问询题到 `learning_preferences` 的映射。它只定义业务 contract，不要求同步完成 FastAPI、worker、仓储或 Flutter 实现。

- 适用时间：2026-04-27 至 2026-05-03
- 适用范围：`course_segments`、`knowledge_points`、`segment_knowledge_points`、`knowledge_point_evidences`、`vector_documents` 的产物语义；解析步骤映射；解析聚合状态；问询答案落入 `learning_preferences` 的字段规则
- 不包含：表迁移、API DTO 实现、worker provider 接入、Flutter 页面改动
- owner 口径：字段业务含义和解析输出结构由曹乐冻结；接口、任务和落库实现仍按 [TEAM_DIVISION.md](../../TEAM_DIVISION.md) 执行

若本文件与 Week 1 冻结稿冲突，以本文件对 Week 2 解析与问询链路的补充为准；引用定位规则仍沿用 [api-contract.md](./api-contract.md) 第 1 节。

冻结的 schema 文件：

- [schemas/parse/normalized_document.schema.json](../../schemas/parse/normalized_document.schema.json)
- [schemas/ai/knowledge_point_extraction.schema.json](../../schemas/ai/knowledge_point_extraction.schema.json)

命名约定：

- 本文件描述落库字段时使用 snake_case，例如 `segment_type`、`page_no`、`section_path`。
- `schemas/parse/normalized_document.schema.json` 描述 parser 产物时使用 camelCase，例如 `segmentType`、`pageNo`、`sectionPath`。
- `normalized_document.segments[].segmentType` 与 `course_segments.segment_type` 使用同一组业务枚举。

解析质量门禁：

- 所有 parser 输出 normalized document 前必须统一清洗 `textContent`，成功 segment 不得包含 `U+FFFF`、`U+FFFD`、NUL、C0/C1 控制字符等乱码。
- 纯点线、纯符号噪声行和清洗后空行必须过滤；清洗后无有效文本的 segment 不得进入成功产物。
- PDF 文本层缺失或出现强乱码时，优先尝试页级 OCR / 视觉增强；增强失败且无干净文本时跳过该页，若所有页均不可用则解析失败。
- PPTX / DOCX 原生文本、表格和 OMML 公式优先结构化抽取；内嵌图片、截图型公式或截图型图表可走视觉增强，输出仍必须保留原资源定位。
- OCR / 视觉增强默认关闭；仅在配置 `KNOWLINK_ENABLE_MARKITDOWN_OCR` 或 `KNOWLINK_VIVO_APP_KEY` 等环境变量后启用，未配置 key 时不得访问网络。

视觉增强环境变量：

| 变量 | 语义 |
|---|---|
| `KNOWLINK_ENABLE_MARKITDOWN_OCR` | 是否启用 MarkItDown 作为 PDF 页级 OCR fallback，默认关闭。 |
| `KNOWLINK_VIVO_APP_KEY` | 蓝心 / vivo 视觉能力调用 key；为空时不发起网络请求。 |
| `KNOWLINK_VIVO_BASE_URL` | 蓝心 / vivo 视觉能力基础地址。 |
| `KNOWLINK_VIVO_VISION_MODEL` | 视觉模型标识，用于 OCR、截图公式和图表说明。 |

## 1. 解析产物字段说明

### 1.1 `course_segments`

`course_segments` 是所有解析来源归一化后的最小可引用内容片段。讲义、问答、测验、复习和向量检索都不得直接引用原始文件任意位置，必须回到 segment 或由 segment 派生的引用。

| 字段 | 语义 |
|---|---|
| `course_id` | 所属课程。 |
| `resource_id` | 来源资源。一个 segment 只能来自一个上传资源或导入资源。 |
| `parse_run_id` | 产出该 segment 的解析版本。重解析必须生成新版本 segment，不覆盖旧版本。 |
| `segment_type` | 片段类型，MVP 固定为 `video_caption`、`pdf_page_text`、`ppt_slide_text`、`docx_block_text`、`ocr_text`、`formula`、`image_caption`。 |
| `title` | 片段标题，可来自章节标题、slide 标题、页标题或模型生成的短标题；用于展示，不作为唯一键。 |
| `section_path` | 从文档结构推导出的章节路径，例如 `["第 1 章", "1.2 极限"]`；无法识别时为空数组。 |
| `text_content` | 保留格式的正文，允许包含 Markdown 公式、列表和换行。 |
| `plain_text` | 用于抽取、检索和 token 统计的纯文本，不保留复杂排版。 |
| `start_sec` / `end_sec` | 视频或字幕片段的闭区间时间定位，只允许 `mp4` / `srt` 来源使用；`end_sec` 必须大于 `start_sec`。 |
| `page_no` | PDF 页码，从 1 开始，只允许 PDF 来源使用。 |
| `slide_no` | PPTX slide 编号，从 1 开始，只允许 PPTX 来源使用。 |
| `image_key` | 页面截图、slide 渲染图或 OCR 图片在对象存储中的 key；没有视觉衍生产物时为空。 |
| `formula_text` | 从片段中识别出的核心公式文本；不是公式片段时为空。 |
| `bbox_json` | OCR 或版面解析定位框，结构为 `{ "page": 1, "boxes": [{"x":0,"y":0,"w":0,"h":0}] }`；坐标单位由解析器固定为页面归一化比例。 |
| `order_no` | 同一 `parse_run_id` 内的稳定顺序号，用于还原课程材料顺序。 |
| `token_count` | `plain_text` 的估算 token 数，用于切块和预算控制。 |
| `is_active` | 当前解析版本内是否参与下游生成。低质量、重复或被过滤片段置为 `false`，但不得物理删除。 |

定位约束：

- 每条 segment 必须且只能使用与 `resourceType` 匹配的一组定位字段。
- `mp4` / `srt` 使用 `start_sec + end_sec`；`pdf` 使用 `page_no`；`pptx` 使用 `slide_no`；`docx` 在 segment 层使用 `section_path + order_no`，对外 citation 使用 `anchorKey`。
- 不得为 DOCX 伪造页码，不得把 PDF 页码和视频时间写入同一条 segment。
- DOCX 的 `docx_block_text`、`ocr_text`、`formula`、`image_caption` 均只能使用 `section_path + order_no` 定位，不得使用 `page_no`、`slide_no`、`start_sec` 或 `end_sec`。

### 1.2 `knowledge_points`

`knowledge_points` 是解析版本内的知识点目录。它表达“课程中有哪些概念/技能/考点”，不直接保存证据文本。

| 字段 | 语义 |
|---|---|
| `course_id` | 所属课程。 |
| `parse_run_id` | 所属解析版本。 |
| `parent_id` | 父知识点；为空表示一级知识点。MVP 只要求最多两层。 |
| `display_name` | 面向用户展示的名称。 |
| `canonical_name` | 归一化名称，用于去重；同一 `course_id + parse_run_id` 内唯一。 |
| `description` | 1 到 3 句知识点说明，供讲义和问询摘要使用。 |
| `difficulty_level` | 难度枚举：`beginner`、`intermediate`、`advanced`。 |
| `importance_score` | 重要性评分，0 到 100，越高越优先进入讲义和复习。 |
| `aliases_json` | 别名数组，例如公式名、简称、英文名。 |
| `is_active` | 是否参与当前版本下游生成。合并或过滤后的知识点置为 `false`。 |

抽取约束：

- `canonical_name` 应去除无意义空白、统一大小写和常见符号，但不要把语义不同的知识点强行合并。
- `importance_score` 综合出现频率、标题层级、教师强调语句、考试关键词和用户目标。
- `parent_id` 只表达目录层级，不表达先修、相似或依赖关系；MVP 不冻结复杂知识图谱边类型。

### 1.3 `segment_knowledge_points`

`segment_knowledge_points` 是 segment 与知识点的多对多关联。

| 字段 | 语义 |
|---|---|
| `segment_id` | 来源片段。 |
| `knowledge_point_id` | 被该片段覆盖或解释的知识点。 |
| `relevance_score` | 相关度，0 到 1。`>= 0.7` 可作为强相关证据，`0.4 到 0.7` 只作为弱上下文。 |

约束：

- 一个 segment 可关联多个知识点，一个知识点必须至少有一条强相关 segment 才能置为 active。
- 关联只表示“该片段能支持该知识点”，不表示掌握度、推荐顺序或讲义块归属。

### 1.4 `knowledge_point_evidences`

`knowledge_point_evidences` 是知识点的可展示证据清单，用于解释“为什么抽取出这个知识点”。

| 字段 | 语义 |
|---|---|
| `knowledge_point_id` | 被证明的知识点。 |
| `segment_id` | 证据来源片段。 |
| `evidence_type` | 证据类型，MVP 固定为 `definition`、`example`、`formula`、`teacher_emphasis`、`exercise`、`summary`。 |
| `sort_no` | 同一知识点下的证据展示顺序。 |

约束：

- evidence 不复制原文，只保存关系；展示时从 `course_segments` 回读文本和定位。
- 同一知识点至少保留 1 条 evidence，最多优先展示 5 条。
- `teacher_emphasis` 只可来自视频字幕、SRT 或带明确强调语句的文档片段。

### 1.5 `vector_documents`

`vector_documents` 是 RAG 的统一向量读模型，不是业务真相源。它从 segment、知识点或讲义块投影生成，可重建。

| 字段 | 语义 |
|---|---|
| `course_id` | 所属课程，检索必须强制过滤。 |
| `parse_run_id` | 来源解析版本。segment / knowledge_point 投影必填。 |
| `handout_version_id` | 讲义块投影所属讲义版本；segment / knowledge_point 投影为空。 |
| `owner_type` | 投影来源：`segment`、`knowledge_point`、`handout_block`。 |
| `owner_id` | 对应来源表主键。 |
| `resource_id` | 原始资源；`segment` 投影必填，其他投影可为空。 |
| `content_text` | 实际送 embedding 的文本，应是可回答用户问题的完整短文本。 |
| `metadata_json` | 检索辅助元数据，至少包含 `resourceType`、合法定位字段、`title`、`sectionPath`、`knowledgePointIds`。 |
| `embedding` | 向量值，由 embedding provider 写入。 |

投影规则：

- `owner_type = segment`：`content_text` 来自 `plain_text`，metadata 必须带来源定位。
- `owner_type = knowledge_point`：`content_text` 由 `display_name + description + aliases` 组成，metadata 记录强相关 segment id 列表。
- `owner_type = handout_block`：只在讲义生成后创建，metadata 记录 `handoutVersionId` 和引用的 segment / knowledge point。
- 查询必须限制在当前 `course_id`，并默认只使用当前 `active_parse_run_id` 与当前 active handout version。

## 2. 解析步骤映射

`pipeline-status.steps[].code` 对前端冻结为以下 5 个阶段。底层 `async_tasks.task_type` 可以更细，但必须聚合到这些阶段。

| step code | 展示名 | 输入 | 主要产出 | 底层任务映射 |
|---|---|---|---|---|
| `resource_validate` | 资源校验 | `course_resources`、对象存储元数据、MIME、checksum | 可解析资源清单、不可解析原因 | `resource_validate` |
| `caption_extract` | 字幕提取 | `mp4`、可选 `srt` | 视频 caption segment、视频时间轴 | `subtitle_extract`、`asr` |
| `document_parse` | 文档解析 | `pdf`、`pptx`、`docx` | 文档文本 segment、页面/slide/docx anchor、OCR 衍生产物 | `doc_parse`、`ocr` |
| `knowledge_extract` | 知识抽取 | active segments | `knowledge_points`、`segment_knowledge_points`、`knowledge_point_evidences` | `knowledge_extract` |
| `vectorize` | 向量化 | active segments、active knowledge points、必要时 handout blocks | `vector_documents` | `embed` |

顺序约束：

1. `resource_validate` 必须最先完成。
2. `caption_extract` 与 `document_parse` 可并行；课程没有视频时 `caption_extract` 为 `skipped`，没有文档时 `document_parse` 为 `skipped`。
3. `knowledge_extract` 依赖至少一个 active segment。
4. `vectorize` 依赖 active segment 和 active knowledge point；若 embedding provider 失败但结构化解析已完成，可触发 `partial_success`。

## 3. `pipeline-status` 语义

### 3.1 状态枚举

`pipeline-status` 是课程级聚合状态，不暴露底层 task 列表细节。`courseStatus.pipelineStatus` 只能取：

| 状态 | 语义 |
|---|---|
| `idle` | 当前没有进行中的 pipeline；课程可能尚未上传资源，或上一轮已结束。 |
| `queued` | 根任务已创建但还未开始执行。 |
| `running` | 至少一个必须步骤正在执行，且尚未进入最终态。 |
| `partial_success` | 必须步骤已达到可继续下游的最低条件，但存在非关键资源或非关键步骤失败。 |
| `succeeded` | 本轮解析全部必须步骤成功，且产物已可用于问询和讲义生成。 |
| `failed` | 必须步骤失败，无法进入问询。 |

步骤级 `steps[].status` 可取：`queued`、`running`、`succeeded`、`failed`、`skipped`、`partial_success`。

### 3.2 进度计算

课程解析阶段的 `progressPct` 固定按步骤权重聚合：

| step code | 权重 |
|---|---:|
| `resource_validate` | 10 |
| `caption_extract` | 20 |
| `document_parse` | 25 |
| `knowledge_extract` | 25 |
| `vectorize` | 20 |

计算规则：

- `succeeded`、`skipped` 计满权重。
- `running` 按该步骤内部进度折算；没有内部进度时计该步骤权重的 50%。
- `queued` 计 0。
- `failed` 在课程级 `failed` 时保留失败前进度；在课程级 `partial_success` 时按已可用产物比例计入。
- `progressPct` 必须是 0 到 100 的整数，最终 `succeeded` 和 `partial_success` 都返回 100。

### 3.3 失败与 `partial_success`

`failed` 的判定：

- `resource_validate` 无任何可解析资源。
- `caption_extract` 和 `document_parse` 都没有产出 active segment。
- `knowledge_extract` 未产出任何 active knowledge point。
- 数据库写入、对象存储读取或根任务异常导致产物不可确认。

`partial_success` 的判定：

- 至少有一个资源成功解析并产出 active segment。
- 至少有一个 active knowledge point 和 evidence。
- 失败项不阻断问询、讲义和检索的最低可用链路。
- 典型场景：视频 ASR 失败但 PDF/PPTX/DOCX 成功；某个 PDF 页 OCR 失败但文本层成功；embedding 部分失败但仍有可检索的 segment 投影。

`partial_success` 下游语义：

- `lifecycleStatus` 可进入 `inquiry_ready`。
- `nextAction` 返回 `enter_inquiry`。
- `sourceOverview`、`knowledgeMap` 和 `highlightSummary` 必须明确可用数量和失败提示。
- 后端可允许重试失败子任务，但不得阻塞用户进入问询。

### 3.4 `pipeline-status` 字段要求

`GET /api/v1/courses/{courseId}/pipeline-status` 的 `steps[]` 至少包含：

```json
{
  "code": "document_parse",
  "label": "文档解析",
  "status": "running",
  "progressPct": 60,
  "message": "已完成 PDF 和 PPTX，DOCX 解析中",
  "failedResourceIds": []
}
```

字段说明：

- `code`：固定使用第 2 节的 5 个 step code。
- `label`：中文展示名，可直接给 Flutter 展示。
- `status`：步骤级状态。
- `progressPct`：步骤内部进度，0 到 100；没有内部进度时可省略。
- `message`：面向用户的短提示；失败或 partial success 时必填。
- `failedResourceIds`：失败资源 id 列表；没有失败时为空数组或省略。

## 4. 问询题到 `learning_preferences` 的映射

问询题 key 固定由 `GET /api/v1/courses/{courseId}/inquiry/questions` 下发，提交时 `answers[].key` 必须命中已下发 key。服务端保存时写入 `learning_preferences`，同时保留原始答案快照到 `inquiry_answers_json`。

Week 2 v1 问询模板最低只要求接口下发 `goal_type`、`mastery_level`、`time_budget_minutes`、`handout_style`、`explanation_granularity` 5 个必填 key。`exam_at`、`language_style`、`focus_knowledge_points` 是保存与推导规则，可在后续问询模板版本中下发；本周不强制 Flutter 页面展示。

| inquiry key | 允许值 / 类型 | 写入字段 | 规则 |
|---|---|---|---|
| `goal_type` | `final_review`、`exam_sprint`、`daily_learning`、`knowledge_gap_fix` | `goal_type` | 必填；用于讲义组织、测验难度和复习优先级。 |
| `mastery_level` | `beginner`、`intermediate`、`advanced` | `self_level` | 必填；与推荐链路的 `selfLevel` 语义一致。 |
| `time_budget_minutes` | 正整数，建议 10 到 1440 | `time_budget_minutes` | 必填；超出范围按校验错误处理，不静默截断。 |
| `handout_style` | `exam`、`balanced`、`detailed` | `preferred_style` | 必填；与课程创建/推荐的 `preferredStyle` 语义一致。 |
| `explanation_granularity` | `quick`、`balanced`、`detailed` | `formula_detail_level`、`example_density` | 必填；`quick -> low/low`，`balanced -> medium/medium`，`detailed -> high/high`。 |
| `exam_at` | ISO 8601 datetime，可选 | `exam_at` | 未回答时沿用课程创建或推荐输入中的 `examAt`；仍为空则保存 null。 |
| `language_style` | `concise`、`friendly`、`formal`，可选 | `language_style` | 未回答时默认 `friendly`。 |
| `focus_knowledge_points` | knowledge point id 数组，可选 | `focus_knowledge_json` | 只能选择当前 active parse run 下的 active knowledge point；空数组表示不指定重点。 |

固定推导：

- `confirmed_at`：服务端成功保存答案时写入当前时间。
- `inquiry_answers_json`：保存提交原文、问询 `version`、服务端推导字段和 active parse run id，便于重放与排障。
- `goal_type`、`self_level`、`time_budget_minutes`、`preferred_style`、`formula_detail_level`、`example_density` 是 Week 2 最低必填偏好集合。

`explanation_granularity` 推导表：

| value | `formula_detail_level` | `example_density` |
|---|---|---|
| `quick` | `low` | `low` |
| `balanced` | `medium` | `medium` |
| `detailed` | `high` | `high` |

校验失败语义：

- 课程未进入 `inquiry_ready` 时返回 `inquiry.course_not_ready`。
- 必填 key 缺失、key 未知、枚举值非法或时间预算非法时返回 `common.validation_error`。
- `focus_knowledge_points` 引用非当前 active parse run 的知识点时返回 `common.validation_error`。

## 5. Week 2 验收口径

- 解析产物字段含义、合法定位和版本隔离规则已明确。
- `pipeline-status` 能用 5 个固定步骤解释解析进度、失败和 partial success。
- `partial_success` 允许进入问询的最低条件已明确。
- 问询题 key 与 `learning_preferences` 字段映射可被后端 DTO、service 和测试直接引用。
- 本文件被 [api-contract.md](./api-contract.md) 作为 Week 2 冻结入口引用。
