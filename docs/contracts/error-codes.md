# KnowLink Error Codes

## Auth

- `auth.token_missing`: 缺少 Bearer token
- `auth.token_invalid`: Bearer token 不匹配 demo token

## Common

- `common.validation_error`: 请求体字段校验失败
- `common.not_found`: 资源不存在
- `common.idempotency_replay`: 命中幂等回放
- `idempotency.body_mismatch`: 相同幂等键重放时请求体与首次提交不一致

## Recommendation

- `recommendation.catalog_not_found`: 推荐目录项不存在
- `recommendation.no_match`: 当前筛选条件下没有推荐结果

## Course And Resource

- `course.not_found`: 课程不存在
- `resource.not_found`: 资源不存在
- `resource.has_dependents`: 资源已被后端解析产物、引用或学习进度依赖，当前不能安全删除
- `resource.invalid_payload`: 上传完成回调字段不完整
- `resource.not_video`: 资源不是可播放视频
- `resource.playback_unavailable`: 播放地址生成失败

## Bilibili

- `bilibili.not_implemented`: V1 B 站导入与扫码登录接口已预留，但当前服务尚未接通
- `bilibili.auth_required`: V2 B站导入需要扫码登录后才能继续
- `bilibili.auth_expired`: V2 B站登录态过期或服务端凭据失效
- `bilibili.unsupported_url`: V2 B站链接不属于单视频、多 P、合集或番剧支持范围
- `bilibili.access_denied`: B站内容不可访问，包含付费、会员、DRM、地区限制或账号无权限
- `bilibili.metadata_failed`: B站元数据、分 P、合集或番剧条目获取失败
- `bilibili.playurl_failed`: B站播放地址获取失败或没有可用音视频流
- `bilibili.download_failed`: B站音视频流下载失败
- `bilibili.merge_failed`: ffmpeg 合并音视频失败
- `bilibili.upload_failed`: 合并产物上传对象存储失败
- `bilibili.import_failed`: 上传后创建课程资源失败
- `bilibili.cancel_failed`: 取消导入任务或清理副作用失败
- `bilibili.run_not_found`: B站导入 run 不存在或不属于当前用户
- `bilibili.selection_invalid`: B站导入选择模式或分 P 选择项不合法
- `bilibili.preview_not_found`: B站导入预览结果不存在或已失效

## V2 Knowledge Graph

- V2 知识图谱接通前，需要补充并冻结以下错误码类别：
  - `graph.not_ready`: 当前课程图谱尚未生成或不可读
  - `graph.node_not_found`: 图谱节点不存在或不属于当前课程
  - `graph.edge_not_found`: 图谱关系不存在或不属于当前课程
  - `graph.evidence_missing`: 图谱节点或边缺少必要证据引用
  - `graph.generation_failed`: 图谱生成失败

## V2 Streaming

- V2 实时流式输出接通前，需要补充并冻结以下错误码类别：
  - `stream.task_not_found`: 流式任务不存在或不属于当前用户
  - `stream.unsupported_task`: 当前任务类型不支持事件流
  - `stream.event_replay_unavailable`: 无法按 `Last-Event-ID` 或 `after` 回放事件
  - `stream.connection_closed`: 服务端主动关闭事件流
  - `stream.cancel_failed`: 取消流式任务失败

## V2 Subjective Grading

- V2 主观题判卷接通前，需要补充并冻结以下错误码类别：
  - `grading.question_not_supported`: 当前题目类型不支持自动判卷
  - `grading.rubric_missing`: 缺少 rubric 或评分维度
  - `grading.evidence_missing`: 判卷缺少课程材料证据
  - `grading.judge_failed`: LLM judge 调用或结构化输出失败
  - `grading.low_confidence`: 判卷结果置信度过低，需要人审
  - `grading.result_not_found`: 判卷结果不存在或不属于当前提交

## Pipeline

- `async_task.enqueue_failed`: 异步任务记录已创建或准备重试，但派发到 dispatcher / broker 失败
- `pipeline.not_ready`: 当前课程状态不允许发起解析
- `pipeline.parse_run_not_found`: 解析版本不存在
- `pipeline.task_not_found`: 异步任务不存在
- `pipeline.task_not_retryable`: 异步任务当前状态不可重试
- `pipeline.task_retry_unsupported`: 异步任务类型不支持 retry 接口
- `pipeline.task_retry_stale`: 异步任务重试前状态更新失败，通常表示记录已变化或不可写

## Inquiry And Handout

- `inquiry.course_not_ready`: 课程尚未进入问询阶段
- `handout.not_found`: 讲义版本不存在
- `handout.no_active_version`: 当前课程没有可用讲义

## QA / Quiz / Review

- `qa.block_not_found`: 讲义块不存在
- `quiz.not_found`: 测验不存在
- `review.run_not_found`: 复习任务重算记录不存在
