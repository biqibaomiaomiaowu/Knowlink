# KnowLink V2 三阶段功能设计

日期：2026-05-13

## 1. 目标

KnowLink 第一版已经完成核心学习闭环。第二版以“真实可用的课程学习产品”为目标，分三个阶段推进：

1. 阶段一完成真实产品闭环：B站真实登录下载导入、课程库与智能推荐基础版、多课程基础管理、Android 运行、页面设计优化、复杂版面增强的最低可用门槛。
2. 阶段二完成 AI 和图谱重能力：复杂知识图谱、实时流式输出、主观题自动判卷、多课程管理增强、课程推荐个性化增强。
3. 阶段三完成真实用户测试与体验优化：用用户任务数据决定体验修复优先级，不再新增大功能。

本设计只冻结产品语义、阶段边界、contract 方向和验收标准。若之后进入实现，需要再按 owner 边界单独拆分任务；本文不包含实施计划。

## 2. Owner 边界

本规格归曹乐负责的产品流程、业务语义、B站导入 contract、AI/图谱策略、课程推荐语义和比赛文档范围。

后续实现需要跨 owner 协作：

- 曹乐：V2 后端技术主责与 AI 主责，负责困难后端、AI、解析、B站导入核心、知识图谱、流式输出、主观题判卷和推荐策略；同时冻结 B站导入状态语义、课程库字段语义、图谱节点和边类型、AI 输出 schema、主观题评分结构、验收口径。
- 杨彩艺：后端辅助与用户测试调研主责，只负责边界清楚、低风险、可独立完成的后端辅助任务，包括基础 CRUD、简单 DTO、状态查询、接口文档、测试数据整理、简单接口联调；第三阶段总负责真实用户测试反馈调研。她不负责 B站下载合并、复杂任务状态机、SSE 核心协议、图谱生成、主观题 AI 判卷等困难后端。
- 朱春雯：负责 Flutter 页面、Android 工程、视觉优化、交互状态和真机体验。

实现时不得绕过 [docs/v2/phase-plan.md](./phase-plan.md) 的 V2 责任口径；`docs/v1/team-division.md` 仅作为 V1 分工历史和协作背景使用。

## 3. 阶段一：真实可用闭环

### 3.1 B站用户授权导入器

B站能力在第一阶段完成真实登录、下载、导入闭环，范围为：

- 单视频。
- 多 P 视频。
- 合集。
- 番剧。

第一阶段不做收藏夹、热门列表、大规模批量下载，也不做付费、DRM、地区限制内容的绕过。

推荐架构：

- Flutter 只展示二维码、登录状态、资源预览、导入进度、失败原因和取消入口，不接触 `SESSDATA`、`bili_jct` 等 cookie。
- FastAPI 提供扫码登录会话、登录态校验、元数据预览、导入任务创建、任务状态、取消和退出登录接口。
- B站适配层独立为 `BiliClient` / `BiliImportService`，负责二维码登录、cookie 校验、WBI 签名、视频/番剧/合集元数据、DASH playurl 获取。
- Worker 执行下载、ffmpeg 合并、上传 MinIO、创建 `course_resources`，请求线程只创建任务。
- 凭据只在服务端加密保存，绑定当前单用户环境，记录过期时间和最后校验时间。凭据失效后重新扫码，不做复杂静默刷新。
- DASH 下载默认选择 H.264/AVC 视频和 AAC 音频，降低 Android 播放、后续解析和 ffmpeg 合并风险。
- ffmpeg 默认使用 stream copy 做无损封装合并，不在第一阶段默认转码。

任务状态需要覆盖：

- `pending`
- `fetching_metadata`
- `waiting_download`
- `downloading`
- `merging`
- `uploading`
- `imported`
- `failed`
- `canceled`
- `recoverable`

关键验收：

- 新账号能扫码登录，二维码过期能重新生成，退出登录能清除后端凭据。
- 单视频能完成元数据预览、DASH 下载、ffmpeg 合并、MinIO 上传、课程资源入库。
- 多 P 能选择当前 P 或全部 P，资源顺序、标题、时长、封面正确。
- 合集和番剧能分页预览并导入可访问条目；会员、付费、地区限制、不可观看内容返回明确失败原因。
- 下载、合并、上传三段进度可见；取消能停止 HTTP 下载和 ffmpeg 子进程。
- DASH URL 过期后能重新获取；MinIO 上传失败能单独重试或标记可恢复。
- 默认并发限制为每账号 1 到 2 个下载任务，并有用户确认提示。

参考资料：

- `iuroc/bilidown`：https://github.com/iuroc/bilidown
- B站二维码登录接口整理：https://socialsisteryi.github.io/bilibili-API-collect/docs/login/login_action/QR.html
- B站视频播放地址接口整理：https://socialsisteryi.github.io/bilibili-API-collect/docs/video/videostream_url.html
- B站番剧接口整理：https://socialsisteryi.github.io/bilibili-API-collect/docs/bangumi/info.html
- `yt-dlp` Bilibili extractor：https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/bilibili.py
- FFmpeg 文档：https://ffmpeg.org/ffmpeg.html

### 3.2 课程库与智能推荐基础版

第一阶段补齐课程库和推荐的可演示产品闭环：

- 扩展课程库字段：学科、课程代码、目标人群、难度、先修要求、知识点标签、课程大纲、资源导入提示、推荐理由素材、封面和亮点。
- 增加课程详情页语义：用户能在确认入课前理解课程目标、适合人群、预计投入和推荐原因。
- 推荐先用规则排序：学习目标、基础水平、时间预算、考试/项目紧迫度、标签匹配、资源可解析性。
- 推荐结果必须可解释，展示“为什么推荐”和“下一步建议”。

第一阶段不做复杂个性化模型，不依赖大规模学习行为日志。

关键验收：

- 至少有一组覆盖演示场景的课程库 seed。
- 用户从推荐页能进入课程详情并确认创建课程。
- 推荐理由能解释目标、基础、时间和资源匹配，而不是只展示分数。
- 创建课程后能继续进入 B站导入、解析、讲义、测验链路。

### 3.3 多课程基础管理

第一阶段只做基础多课程，不做多用户：

- 支持课程创建、最近课程、课程切换。
- 首页和学习流必须明确当前课程。
- 资源、解析、讲义、测验、复习状态都以课程隔离。

归档、删除、批量管理、复杂搜索放到第二阶段。

### 3.4 Android 运行

第一阶段采用模拟器和真机双轨验收：

- 模拟器访问本地后端使用 `10.0.2.2`。
- 真机 USB 调试优先使用 `adb reverse tcp:8000 tcp:8000` 访问 FastAPI；若本地 MinIO public endpoint 仍是 `127.0.0.1:9000`，必须同步执行 `adb reverse tcp:9000 tcp:9000`，否则上传初始化成功后文件 PUT 到预签名对象存储 URL 会连接到平板自身的 `127.0.0.1:9000` 并失败。
- 真机 Wi-Fi 方案使用宿主机局域网 IP，并要求 Flutter `KNOWLINK_API_BASE_URL` 与后端 `KNOWLINK_MINIO_PUBLIC_ENDPOINT` 都使用平板可访问的宿主机地址。
- Android 9/API 28+ 的明文 HTTP 只能作为 debug/local 例外；测试分发前需要明确 HTTPS 或 debug-only network security config。
- 后端返回给 Android 的 MinIO 预签名 URL 必须是设备可达地址，不能返回 `minio:9000` 等容器内部 host，也不能在非 USB reverse 场景返回只对开发机本机有效的 `127.0.0.1:9000`。
- 视频播放使用现有 Flutter `video_player` 能力，后端视频 URL 需要 MIME 正确，并支持长视频 seek 所需的 range request。

关键验收：

- `flutter doctor` 无 Android toolchain 阻断项。
- 模拟器和至少一台 Android 真机能启动 App。
- Android 客户端能访问 FastAPI 健康检查、课程、资源、讲义和问答主流程。
- B站导入后的视频能在 Android 真机播放、暂停、seek。
- 权限最小化，只申请网络、文件选择和视频播放实际需要的权限。

参考资料：

- Flutter Android setup：https://docs.flutter.dev/platform-integration/android/setup
- Android emulator networking：https://developer.android.com/studio/run/emulator-networking-address
- adb reverse：https://developer.android.com/develop/ui/views/layout/webapps/access-local-server
- Android Network Security Config：https://developer.android.com/privacy-and-security/security-config
- Flutter video_player：https://docs.flutter.dev/cookbook/plugins/play-video

### 3.5 页面设计优化

页面优化进入第一阶段，不推迟到用户测试后。

优化范围：

- 首页：课程切换、最近课程、推荐入口、当前学习状态更清楚。
- 导入页：上传、本地资料、B站导入的入口和状态统一。
- 解析进度页：展示当前阶段、耗时、失败原因和重试入口。
- 讲义页：目录、当前块、引用、跳转视频/页码、块级问答更顺。
- 测验与复习页：从做题到错因、知识点、复习任务的路径更清楚。
- 推荐页：课程详情和推荐理由更像真实选课流程。

页面优化不新增多用户、社区、排行榜等非核心功能。

### 3.6 复杂版面增强最低门槛

第一阶段只补复杂版面增强的最低门槛：

- 对 PDF/PPTX/DOCX 中表格、公式、图片、复杂布局保留更稳定的结构信息。
- 继续沿用现有高保真解析策略，必要时融合 MinerU 或外部解析结果，但不替换当前主链路。
- 解析产物必须能继续支撑讲义、引用、问答和测验，不追求孤立的版面还原。

关键验收：

- 固定真实资料集上无明显乱码、重复 OCR 噪声和丢页。
- 复杂图片、公式或表格能产出可引用的结构化描述。
- 解析结果能继续进入讲义和问答链路。

## 4. 阶段二：AI 和图谱重能力

### 4.1 复杂知识图谱

复杂知识图谱按“可复用学习图谱”定位，不只是可视化展示。

推荐架构：

- Postgres 规范表作为主事实源。
- JSONB 保存扩展字段。
- 预计算 read model 供 Flutter 图谱页、学习路径、推荐和判卷使用。
- 后续如需复杂多跳遍历、图算法、教师探索，再将发布版本导出到 Neo4j / GDS，Neo4j 不作为第二阶段唯一事实源。

核心节点：

- `KnowledgePoint`
- `Course`
- `Chapter`
- `Resource`
- `HandoutBlock`
- `Question`
- `RubricCriterion`
- `AtomicFact`

核心边：

- `PART_OF`
- `CONTAINS`
- `PREREQUISITE_OF`
- `RELATED_TO`
- `CONFUSES_WITH`
- `TEACHES`
- `COVERS`
- `ASSESSES`
- `EVIDENCED_BY`
- `CITES`

所有核心节点和边必须带：

- 来源引用。
- 置信度。
- 版本。
- 生成方式。
- 审核状态。

阶段二最小闭环：

- 一门课内生成知识点与资源引用图。
- 图谱页按章节或知识点查看 1 到 2 跳子图。
- 从目标知识点反推出缺失先修、推荐讲义块和推荐题目。
- 从错题或薄弱点反推出复习路径。
- 主观题判卷结果可追溯到 rubric、atomic facts 和来源讲义块。

参考资料：

- 1EdTech CASE：https://www.1edtech.org/standards/case
- Schema.org LearningResource：https://schema.org/LearningResource
- Microsoft GraphRAG：https://microsoft.github.io/graphrag/query/overview/
- Neo4j GraphRAG：https://neo4j.com/docs/neo4j-graphrag-python/current/index.html
- Cytoscape.js：https://js.cytoscape.org/

### 4.2 实时流式输出

实时输出优先使用 SSE，WebSocket 作为后续双向场景保留。

推荐接口形态：

- V2 默认复用现有 `async_tasks.id` 作为 `taskId`，不另起第二套任务真相源。
- `GET /api/v1/async-tasks/{taskId}/events` 订阅 SSE。
- `GET /api/v1/async-tasks/{taskId}` 查询当前状态和最终结果。
- 若后续增加 `/api/v1/tasks` 聚合层，它只能作为 `async_tasks` 的只读适配层，不能产生另一套状态枚举。

事件协议至少包含：

- `eventId`
- `taskId`
- `seq`
- `type`
- `payload`
- `createdAt`

事件类型至少包含：

- `task.created`
- `stage.started`
- `llm.delta`
- `artifact.updated`
- `grading.dimension_scored`
- `task.completed`
- `task.failed`
- `task.canceled`

恢复策略：

- 客户端保存最后一个 `eventId`。
- 重连时通过 `Last-Event-ID` 或 `?after=` 续传。
- 服务端从持久事件表或 Redis Stream 回放。
- REST 状态查询作为兜底。

关键验收：

- Flutter 首 token 展示 p95 小于等于 2 秒。
- 事件单调递增，重复事件幂等处理。
- 随机断线重连后最终文本和任务状态一致。
- 用户取消后 3 秒内停止继续产出事件。

参考资料：

- FastAPI SSE：https://fastapi.tiangolo.com/tutorial/server-sent-events/
- MDN SSE：https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
- Redis Streams：https://redis.io/docs/latest/develop/data-types/streams/

### 4.3 主观题自动判卷

主观题判卷采用 `rubric + RAG 证据 + LLM judge + 结构化输出 + 人审兜底`。

第二版试点题型限定：

- 简答题。
- 概念解释题。

评分输入：

- 题目。
- 学生答案。
- 参考答案。
- rubric 维度、权重和满分。
- 课程材料引用块。
- 相关知识点和 atomic facts。

评分输出必须结构化：

- `totalScore`
- `dimensionScores`
- `feedback`
- `deductions`
- `evidenceRefs`
- `confidence`
- `needsHumanReview`
- `judgeVersion`

低置信度、证据不足、judge 分歧大、接近及格线或高风险答案必须进入人审兜底。

关键验收：

- 每个分项分数都能追溯到 rubric 和证据。
- 无证据评分率为 0。
- 与教师 gold set 的一致性达到试点门槛后才扩大使用。
- MVP 期允许 15% 到 30% 人审率，稳定后再降低。

参考资料：

- OpenAI Structured Outputs：https://platform.openai.com/docs/guides/structured-outputs
- OpenAI graders：https://platform.openai.com/docs/guides/graders
- G-Eval：https://arxiv.org/abs/2303.16634
- Ragas metrics：https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/

### 4.4 多课程管理增强

阶段二补齐多课程管理：

- 课程列表。
- 课程详情。
- 课程重命名。
- 归档。
- 删除。
- 搜索和筛选。
- 每门课程独立进度、资源、图谱、测验和复习状态。

仍不做多用户、班级、权限协作。

### 4.5 个性化推荐增强

阶段二在第一阶段规则推荐基础上接入图谱和学习行为：

- 根据目标知识点、缺失先修、错题、薄弱点推荐课程内学习路径。
- 课程推荐理由从静态标签扩展为“目标匹配 + 图谱路径 + 学习进度”。
- 学习日志不足时不引入复杂知识追踪模型。

## 5. 阶段三：真实用户测试和体验优化

阶段三不新增大功能，核心是用真实用户证据排序体验修复。

测试建议：

- 两轮轻量可用性测试。
- 每轮约 5 名目标用户。
- 如果区分学生/教师或重度/轻度学习者，每组 3 到 5 人。

测试任务：

- 首次进入产品并选择或创建课程。
- 根据推荐选择课程。
- 导入 B站课程资源。
- 等待解析并理解当前进度。
- 浏览目录、讲义块、引用和知识点。
- 对当前资料提问并判断回答是否可信。
- 跳转视频时间点或资料页码。
- 完成客观题和主观题反馈。
- 根据错题或薄弱点进入复习。
- 遇到导入、解析、网络或视频失败时尝试恢复。

核心指标：

- 任务成功率。
- 完成时间。
- 错误次数。
- 求助次数。
- SUS。
- SEQ。
- 视频播放成功率、首帧时间和 seek 成功率。
- 用户是否理解 AI 讲义和引用来源。
- 用户是否愿意继续用它复习。

验收标准：

- 完成至少两轮用户测试和修复闭环。
- 无 P0/P1 可用性阻断问题。
- 核心学习任务成功率试点阶段达到 80% 以上。
- SUS 低于 68 时优先做体验整改。
- 输出问题清单，包含严重级别、复现路径、证据截图或录屏、修复建议和下一版归属。

参考资料：

- NN/g 5 users：https://www.nngroup.com/articles/how-many-test-users/
- NN/g usability metrics：https://www.nngroup.com/articles/usability-metrics/

## 6. 不做事项

V2 当前三阶段明确不做：

- 多用户、班级、权限协作。
- B站付费、DRM、地区限制内容绕过。
- 收藏夹、热门列表、大规模批量下载。
- 公开分享下载后的视频文件。
- 一开始把 Neo4j 作为唯一主库。
- 没有 gold set 的高风险正式成绩自动判卷。
- 用户测试阶段继续新增大功能。

## 7. 风险

主要风险和处理原则：

- B站接口不稳定：适配层独立封装，错误分类清楚，保留重新扫码和重新获取 playurl 的恢复路径。
- 账号风控：低并发、指数退避、真实 UA、必要 Referer，不做代理池、验证码绕过或高频批量。
- 版权和平台协议风险：产品文案限定为用户授权导入个人可访问学习资料，禁止公开分享，保留来源信息。
- Android 本地联调不稳定：明确模拟器、USB 真机和 Wi-Fi 三套连接方式，预签名 URL 必须设备可达。
- 图谱噪声：先修和易混淆边必须有来源、置信度和审核状态。
- 流式输出断线：SSE 事件必须持久化或可回放，REST 状态查询作为兜底。
- 自动判卷误判：评分必须可追溯，有低置信度人审兜底。
- 用户测试样本小：定性测试用于发现问题，不作为统计结论。

## 8. 成功标准

阶段一完成时：

- Android 真机上能完成选课、B站导入、解析、讲义、问答、测验的主流程。
- B站单视频、多 P、合集/番剧导入可真实运行，失败原因可解释。
- 课程库和推荐能支撑真实选课式演示。
- 页面体验达到可被真实用户测试的状态。

阶段二完成时：

- 学习图谱能支撑图谱页、学习路径、复习推荐和主观题判卷证据链。
- SSE 事件流能支撑 LLM token、任务进度和判卷状态实时输出。
- 主观题判卷可结构化、可追溯、可人审兜底。

阶段三完成时：

- 有真实用户测试记录、指标和问题清单。
- P0/P1 可用性问题关闭。
- 下一版优先级来自用户证据，而不是主观猜测。
