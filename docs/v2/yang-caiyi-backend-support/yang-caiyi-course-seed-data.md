# 杨彩艺 课程 seed 测试数据说明

来源：

- `server/seeds/course_catalog.json`
- `docs/contracts/api-contract.md`
- `docs/contracts/week1-cao-le-freeze.md`

用途：整理当前课程推荐 seed，可用于推荐接口联调、课程详情展示核对、确认入课测试数据和阶段验收材料。本文只整理已有 seed，不新增课程、不修改推荐规则。

## Seed 总览

| `catalogId` | 课程标题 | 学科 | 课程代码 | 难度 | 预计时长 | 支持风格 |
|---|---|---|---|---|---|---|
| `math-final-01` | 高等数学期末冲刺 | `math` | `MATH-FINAL-01` | `intermediate` | 4 小时 | `exam`、`balanced` |
| `math-grad-02` | 考研数学基础巩固 | `math` | `MATH-GRAD-02` | `beginner` | 6 小时 | `detailed`、`balanced` |
| `linear-final-01` | 线性代数高频题型课 | `linear_algebra` | `LINEAR-FINAL-01` | `intermediate` | 3 小时 | `exam`、`quick` |

## 推荐理由与展示素材

| `catalogId` | 课程标题 | `reasonMaterials` | `highlights` | `importHints` |
|---|---|---|---|---|
| `math-final-01` | 高等数学期末冲刺 | 覆盖高频考点；适合考前冲刺；讲义和视频能组成完整复习闭环 | 高频题型；考前节奏；讲义引用完整 | 优先导入主课程视频；配套 PDF 用于公式与例题引用定位 |
| `math-grad-02` | 考研数学基础巩固 | 适合基础补齐；学习节奏更细；覆盖考研数学入门知识点 | 基础巩固；细粒度讲解；考研导向 | 先导入体系化视频；PDF 讲义用于建立基础知识点索引 |
| `linear-final-01` | 线性代数高频题型课 | 覆盖线代高频题型；适合短时刷题；重点突出矩阵和特征值 | 高频题型；短时冲刺；矩阵专题 | 视频优先覆盖题型讲解；PDF/PPTX 用于题目和证明定位 |

说明：

- `reasonMaterials[]` 来自 seed，用于课程详情页和推荐卡片解释，不参与排序。
- 推荐接口的 `reasons[]` 优先使用 Week 1 冻结文案。
- `fitScore` 由推荐服务输出；同分时保持 `course_catalog.json` 中的 seed 顺序。

## 默认资源清单

| `catalogId` | 课程标题 | 必需资源 | 可选资源 | 备注 |
|---|---|---|---|---|
| `math-final-01` | 高等数学期末冲刺 | `mp4` 主课程视频；`pdf` 配套讲义 PDF | `pptx` 配套课件；`docx` 补充讲义；`srt` 字幕文件 | 覆盖视频、PDF、PPTX、DOCX、SRT 展示 |
| `math-grad-02` | 考研数学基础巩固 | `mp4` 主课程视频；`pdf` 配套讲义 PDF | `pptx` 配套课件；`docx` 补充讲义 | 当前 seed 未包含 `srt` |
| `linear-final-01` | 线性代数高频题型课 | `mp4` 主课程视频；`pdf` 配套讲义 PDF | `pptx` 配套课件；`docx` 补充讲义；`srt` 字幕文件 | 覆盖视频、PDF、PPTX、DOCX、SRT 展示 |

资源类型说明：

| `resourceType` | 说明 | 联调关注点 |
|---|---|---|
| `mp4` | 主课程视频 | 后续播放地址需设备可达 |
| `pdf` | 配套讲义 PDF | citation 使用 `pageNo` |
| `pptx` | 配套课件 PPTX | citation 使用 `slideNo` |
| `docx` | 补充讲义 DOCX | citation 使用 `anchorKey`，不伪造页码 |
| `srt` | 字幕文件，可选辅助输入 | 不单独构成联调通过条件 |

## 课程详情字段整理

| 字段 | 说明 | 示例 |
|---|---|---|
| `catalogId` | 推荐目录 ID | `math-final-01` |
| `title` | 课程标题 | `高等数学期末冲刺` |
| `provider` | 来源 | `KnowLink Seed` |
| `subject` | 学科 | `math` |
| `courseCode` | 课程代码 | `MATH-FINAL-01` |
| `level` | 难度 | `intermediate` |
| `targetAudience` | 目标人群 | `需要高等数学期末冲刺复习的学生` |
| `estimatedHours` | 预计学习时长 | `4` |
| `tags` | 课程标签 | `高等数学`、`期末`、`极限`、`导数` |
| `knowledgeTags` | 知识点标签 | `极限`、`连续`、`导数`、`积分`、`高频题型` |
| `prerequisites` | 先修要求 | `函数基础`、`基础代数`、`初等函数` |
| `outline` | 课程大纲 | `极限与连续`、`导数与应用`、`积分与综合题` |
| `importHints` | 导入提示 | `优先导入主课程视频` |
| `reasonMaterials` | 推荐解释素材 | `覆盖高频考点` |
| `coverUrl` | 封面 URL | 当前均为 `null` |
| `highlights` | 课程亮点 | `高频题型` |
| `supportedStyles` | 支持偏好 | `exam`、`balanced` |
| `defaultResourceManifest` | 默认资源清单 | 见上表 |

## 推荐联调测试样例

| 场景 | 请求重点 | 预期关注点 |
|---|---|---|
| 高数期末冲刺 | `goalText=高等数学期末复习`、`selfLevel=intermediate`、`preferredStyle=exam` | 优先关注 `math-final-01`，推荐理由应能解释期末、基础和时间匹配 |
| 考研基础补齐 | `goalText=考研数学基础复习`、`selfLevel=beginner`、`preferredStyle=detailed` | 关注 `math-grad-02`，推荐理由应体现基础补齐和细粒度讲解 |
| 线代短时刷题 | `goalText=线性代数期末刷题`、`selfLevel=intermediate`、`preferredStyle=exam` | 关注 `linear-final-01`，推荐理由应体现高频题型和短时冲刺 |

## 联调记录模板

| 记录项 | 填写内容 |
|---|---|
| 测试时间 |  |
| 请求接口 | `POST /api/v1/recommendations/courses` |
| 请求参数 | `goalText`、`selfLevel`、`timeBudgetMinutes`、`examAt`、`preferredStyle` |
| 返回课程数量 |  |
| 第一推荐 `catalogId` |  |
| 第一推荐标题 |  |
| `fitScore` |  |
| `reasons[]` |  |
| `reasonMaterials[]` |  |
| `defaultResourceManifest[]` |  |
| 是否可确认入课 |  |
| 证据 | 响应 JSON、截图或录屏 |

## 杨彩艺边界

| 可做 | 不做 |
|---|---|
| 整理 seed 字段说明 | 修改 `course_catalog.json` 中的课程内容 |
| 整理课程标题、推荐理由、资源清单 | 改推荐排序算法 |
| 准备推荐接口测试样例 | 新增未冻结字段 |
| 整理联调记录和验收材料 | 扩写个性化推荐增强逻辑 |
